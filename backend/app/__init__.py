"""Visual Workflow Automation backend (ALG-AUTO-01)."""
import sys
from pathlib import Path

# Make sibling top-level packages (database/, api_integrations/, ml_model_train/)
# importable no matter where uvicorn is launched from.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
