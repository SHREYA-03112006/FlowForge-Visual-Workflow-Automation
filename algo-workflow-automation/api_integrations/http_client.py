"""HTTP client used by the `http_request` node (standard library only).

Contract expected by backend/app/nodes/actions/http_request.py:
    request(method, url, headers, params, json_body, timeout)
        -> {"status_code": int, "headers": dict, "body": Any}

Behaviour
  * 4xx/5xx responses are RETURNED, not raised (the node decides via "fail on error").
  * Network problems (DNS, refused, timeout, TLS) raise HttpClientError -> node retries.
  * JSON responses are parsed into Python objects; everything else is returned as text.
  * SSRF protection: hosts resolving to localhost/private/link-local addresses are blocked
    unless ALLOW_PRIVATE_NETWORK=true. Redirects are followed manually (max 5) and every hop is re-checked.
  * Response bodies are capped at 5 MB.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import config

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class HttpClientError(Exception):
    """Network-level failure (not an HTTP error status)."""


class BlockedAddressError(HttpClientError):
    """The target resolves to a private/loopback address."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # returning None => urllib raises HTTPError, we handle it
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def check_url(url: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise HttpClientError("Only http:// and https:// URLs are allowed")
    host = parts.hostname
    if not host:
        raise HttpClientError("URL has no host")
    if config.allow_private_network():
        return parts
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise HttpClientError(f"Could not resolve host '{host}': {e}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise BlockedAddressError(
                f"Blocked request to private/internal address ({host} -> {ip}). "
                f"Set ALLOW_PRIVATE_NETWORK=true to allow it.")
    return parts


def _decode(raw: bytes, content_type: str) -> Any:
    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    try:
        text = raw.decode(charset, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped[:1] in ("{", "["):
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


def request(method: str = "GET", url: str = "", headers: dict | None = None, params: dict | None = None,
            json_body: Any = None, timeout: float = 30.0, *, data: bytes | str | None = None) -> dict:
    """Perform one HTTP request. `data` sends a raw body (used for signed webhooks)."""
    method = (method or "GET").upper()
    if method not in METHODS:
        raise HttpClientError(f"Unsupported HTTP method '{method}'")
    headers = {str(k): str(v) for k, v in (headers or {}).items()}
    if not any(k.lower() == "user-agent" for k in headers):
        headers["User-Agent"] = config.USER_AGENT
    if not any(k.lower() == "accept" for k in headers):
        headers["Accept"] = "application/json, text/plain, */*"

    if params:
        sep = "&" if urllib.parse.urlsplit(url).query else "?"
        url = url + sep + urllib.parse.urlencode(
            {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}, doseq=True)

    body: bytes | None = None
    if data is not None:
        body = data.encode("utf-8") if isinstance(data, str) else data
    elif json_body is not None:
        if isinstance(json_body, str):
            body = json_body.encode("utf-8")
            headers.setdefault("Content-Type", "text/plain; charset=utf-8")
        else:
            body = json.dumps(json_body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

    started = time.perf_counter()
    for _hop in range(config.MAX_REDIRECTS + 1):
        check_url(url)
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:      # 3xx / 4xx / 5xx are responses, not failures
            resp = e
        except urllib.error.URLError as e:
            raise HttpClientError(f"Request failed: {e.reason}") from None
        except (TimeoutError, socket.timeout):
            raise HttpClientError(f"Request timed out after {timeout:g}s") from None
        except (ValueError, OSError) as e:       # bad header value, connection reset, ...
            raise HttpClientError(f"Request failed: {e}") from None

        status = resp.status if hasattr(resp, "status") else resp.code
        location = resp.headers.get("Location")
        if status in (301, 302, 303, 307, 308) and location:
            url = urllib.parse.urljoin(url, location)
            if status in (301, 302, 303) and method not in ("GET", "HEAD"):
                method, body = "GET", None
                headers.pop("Content-Type", None)
            resp.close()
            continue

        try:
            raw = resp.read(config.MAX_RESPONSE_BYTES + 1)
        except (TimeoutError, socket.timeout):
            raise HttpClientError(f"Response timed out after {timeout:g}s") from None
        finally:
            resp.close()
        truncated = len(raw) > config.MAX_RESPONSE_BYTES
        raw = raw[:config.MAX_RESPONSE_BYTES]
        ctype = resp.headers.get("Content-Type", "")
        out = {
            "status_code": status,
            "headers": {k.lower(): v for k, v in resp.headers.items()},
            "body": _decode(raw, ctype) if method != "HEAD" else None,
            "url": url,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
        if truncated:
            out["truncated"] = True
        return out
    raise HttpClientError(f"Too many redirects (more than {config.MAX_REDIRECTS})")
