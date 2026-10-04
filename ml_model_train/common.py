"""Shared paths and constants for training, evaluation and inference."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "data" / "tickets.csv"
MODEL_DIR = BASE_DIR / "saved_model"
MODEL_PATH = MODEL_DIR / "model.joblib"
METADATA_PATH = MODEL_DIR / "metadata.json"
METRICS_PATH = MODEL_DIR / "metrics.json"

# Keep these identical in train.py and evaluate.py so the held-out split matches.
RANDOM_STATE = 42
TEST_SIZE = 0.2

# Classes the model predicts (alphabetical, matches sklearn's classes_ order).
LABELS = ["account", "billing", "general", "technical"]
