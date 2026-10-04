"""Central settings, read from environment variables (all optional)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Visual Workflow Automation API"
    project_root: Path = PROJECT_ROOT
    # write_file nodes may only write inside this directory
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "outputs")))
    cors_origins: list = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    ])
    node_timeout: float = float(os.getenv("NODE_TIMEOUT_SECONDS", "60"))
    max_parallel_nodes: int = int(os.getenv("MAX_PARALLEL_NODES", "8"))
    allow_python_snippet: bool = _bool("ALLOW_PYTHON_SNIPPET", True)
    snippet_timeout: float = float(os.getenv("SNIPPET_TIMEOUT_SECONDS", "10"))
    max_log_string: int = int(os.getenv("MAX_LOG_STRING", "10000"))


settings = Settings()
