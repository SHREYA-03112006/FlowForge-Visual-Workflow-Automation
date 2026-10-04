"""Settings for all integrations, read from environment variables at call time
(so changing an env var takes effect without a restart of the module)."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def output_dir() -> Path:
    return Path(env("OUTPUT_DIR") or PROJECT_ROOT / "outputs")


# ---- HTTP ----
def allow_private_network() -> bool:
    """Allow requests to localhost / private IPs. OFF by default (SSRF protection)."""
    return env_bool("ALLOW_PRIVATE_NETWORK", False)


MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = "WorkflowAutomation/1.0"
