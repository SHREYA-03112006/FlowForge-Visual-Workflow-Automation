"""Email sender used by the `send_email` node.

Contract expected by backend/app/nodes/actions/send_email.py:
    send_email(to, subject, body) -> dict

Modes (EMAIL_MODE):
  simulated (default) - nothing is sent; the message is appended to outputs/emails/outbox.jsonl
                        so you can show it in a demo.
  smtp                - real delivery through SMTP.
        SMTP_HOST (required), SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD,
        SMTP_STARTTLS (true), SMTP_SSL (false, use with port 465), EMAIL_FROM (defaults to SMTP_USER)

`to` may contain several addresses separated by commas/semicolons.
"""
from __future__ import annotations

import json
import re
import smtplib
import ssl
import threading
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

from . import config

_EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_lock = threading.Lock()
MAX_BODY = 200_000


class EmailError(Exception):
    pass


def _parse_recipients(to: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[;,]", to or "") if p.strip()]
    if not parts:
        raise EmailError("No recipient given")
    if len(parts) > 50:
        raise EmailError("Too many recipients (max 50)")
    for p in parts:
        if not _EMAIL_RE.match(p):
            raise EmailError(f"Invalid email address: {p!r}")
    return parts


def _outbox_path():
    return config.output_dir() / "emails" / "outbox.jsonl"


def send_email(to: str, subject: str, body: str = "", from_addr: str | None = None) -> dict:
    # header-injection guard
    if any(c in (subject or "") for c in "\r\n") or any(c in (to or "") for c in "\r\n"):
        raise EmailError("Line breaks are not allowed in the recipient or subject")
    recipients = _parse_recipients(to)
    subject = (subject or "").strip() or "(no subject)"
    body = (body or "")[:MAX_BODY]
    mode = config.env("EMAIL_MODE", "simulated").lower()
    message_id = f"<{uuid.uuid4().hex}@workflow.local>"
    sender = from_addr or config.env("EMAIL_FROM") or config.env("SMTP_USER") or "workflow@localhost"

    if mode == "smtp":
        _send_smtp(sender, recipients, subject, body, message_id)
        return {"sent": True, "simulated": False, "message_id": message_id, "to": to, "recipients": recipients}
    if mode != "simulated":
        raise EmailError(f"Unknown EMAIL_MODE '{mode}' (use 'simulated' or 'smtp')")

    record = {"id": message_id, "timestamp": datetime.now(timezone.utc).isoformat(), "from": sender,
              "to": recipients, "subject": subject, "body": body, "mode": "simulated"}
    path = _outbox_path()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return {"sent": True, "simulated": True, "message_id": message_id, "to": to, "recipients": recipients,
            "outbox": str(path.relative_to(config.PROJECT_ROOT)) if path.is_relative_to(config.PROJECT_ROOT) else str(path)}


def _send_smtp(sender, recipients, subject, body, message_id) -> None:
    host = config.env("SMTP_HOST")
    if not host:
        raise EmailError("EMAIL_MODE=smtp but SMTP_HOST is not set")
    port = config.env_int("SMTP_PORT", 587)
    user, password = config.env("SMTP_USER"), config.env("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"], msg["Message-ID"] = sender, ", ".join(recipients), subject, message_id
    msg.set_content(body)
    ctx = ssl.create_default_context()
    try:
        if config.env_bool("SMTP_SSL", False):
            server = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
        with server:
            if not config.env_bool("SMTP_SSL", False) and config.env_bool("SMTP_STARTTLS", True):
                server.starttls(context=ctx)
            if user:
                server.login(user, password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise EmailError(f"SMTP delivery failed: {e}") from None
