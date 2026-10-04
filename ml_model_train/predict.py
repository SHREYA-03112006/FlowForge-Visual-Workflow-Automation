"""Inference entry point used by the backend's ML classifier node.

    from ml_model_train.predict import predict
    predict("I was charged twice")
    # {"label": "billing", "confidence": 0.71,
    #  "scores": {"account": 0.08, "billing": 0.71, ...}, "low_confidence": False}

In a workflow, downstream nodes can branch on {{classify.output.label}}
or {{classify.output.confidence}}.

CLI:  python predict.py "my app keeps crashing"
"""
import sys
import threading

import joblib

try:
    from . import common
except ImportError:  # executed as a plain script
    import common

DEFAULT_THRESHOLD = 0.45

_model = None
_lock = threading.Lock()  # parallel workflow branches may call predict() concurrently


class ModelNotFoundError(FileNotFoundError):
    """Raised when saved_model/model.joblib is missing."""


def load_model(force: bool = False):
    """Load the model once and cache it (thread-safe)."""
    global _model
    if _model is None or force:
        with _lock:
            if _model is None or force:
                if not common.MODEL_PATH.exists():
                    raise ModelNotFoundError(
                        f"Model file not found at {common.MODEL_PATH}. "
                        "Run `python -m ml_model_train.train` first."
                    )
                _model = joblib.load(common.MODEL_PATH)
    return _model


def _validate(text) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    return text.strip()


def _format(model, probs, threshold: float) -> dict:
    labels = [str(c) for c in model.classes_]
    best = max(range(len(labels)), key=lambda i: probs[i])
    confidence = float(probs[best])
    return {
        "label": labels[best],
        "confidence": round(confidence, 4),
        "scores": {l: round(float(p), 4) for l, p in zip(labels, probs)},
        "low_confidence": confidence < threshold,
    }


def predict(text: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Classify one text. Raises ValueError on empty input."""
    model = load_model()
    probs = model.predict_proba([_validate(text)])[0]
    return _format(model, probs, threshold)


def predict_batch(texts, threshold: float = DEFAULT_THRESHOLD) -> list:
    """Classify many texts in one call."""
    model = load_model()
    cleaned = [_validate(t) for t in texts]
    if not cleaned:
        return []
    return [_format(model, row, threshold) for row in model.predict_proba(cleaned)]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python predict.py "text to classify"')
    import json
    print(json.dumps(predict(" ".join(sys.argv[1:])), indent=2))
