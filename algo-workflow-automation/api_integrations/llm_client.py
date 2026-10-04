"""Optional LLM helper (Anthropic Messages API over plain HTTPS).

    complete(prompt, system=None, model=None, max_tokens=1024, temperature=0.2) -> dict
        {"text": str, "model": str, "usage": {...}, "simulated": bool}

LLM_MODE:
  auto (default) - real call if ANTHROPIC_API_KEY is set, otherwise a clearly-labelled mock reply
  anthropic      - always real (fails if no key)
  mock           - always mock (offline demos / tests)
Env: ANTHROPIC_API_KEY, LLM_MODEL (default claude-sonnet-5-5), LLM_API_URL.
"""
from __future__ import annotations

from . import config, http_client

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_URL = "https://api.anthropic.com/v1/messages"
MAX_PROMPT_CHARS = 100_000


class LLMError(Exception):
    pass


def complete(prompt: str, system: str | None = None, model: str | None = None,
             max_tokens: int = 1024, temperature: float = 0.2, timeout: float = 60.0) -> dict:
    if not prompt or not str(prompt).strip():
        raise LLMError("Prompt is empty")
    prompt = str(prompt)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise LLMError(f"Prompt too long (max {MAX_PROMPT_CHARS} characters)")
    model = model or config.env("LLM_MODEL", DEFAULT_MODEL)
    key = config.env("ANTHROPIC_API_KEY")
    mode = config.env("LLM_MODE", "auto").lower()

    if mode == "mock" or (mode == "auto" and not key):
        return {"text": f"[mock LLM] {prompt[:200]}", "model": "mock", "usage": {}, "simulated": True}
    if mode not in ("auto", "anthropic"):
        raise LLMError(f"Unknown LLM_MODE '{mode}'")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set")

    payload = {"model": model, "max_tokens": int(max_tokens), "temperature": float(temperature),
               "messages": [{"role": "user", "content": prompt}]}
    if system:
        payload["system"] = system
    resp = http_client.request(
        "POST", config.env("LLM_API_URL", DEFAULT_URL),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json_body=payload, timeout=timeout)
    body = resp["body"]
    if resp["status_code"] >= 400:
        detail = body.get("error", {}).get("message") if isinstance(body, dict) and isinstance(body.get("error"), dict) else body
        raise LLMError(f"LLM API returned HTTP {resp['status_code']}: {str(detail)[:300]}")
    if not isinstance(body, dict):
        raise LLMError("Unexpected LLM response format")
    text = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
    return {"text": text, "model": body.get("model", model), "usage": body.get("usage", {}), "simulated": False}
