"""Evaluate the saved model on the held-out split and write saved_model/metrics.json.

Run from the repo root:   python -m ml_model_train.evaluate
or from this folder:      python evaluate.py
"""
import json

import joblib
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

try:
    from . import common
    from .train import load_dataset, split
except ImportError:  # executed as a plain script
    import common
    from train import load_dataset, split


def main() -> None:
    if not common.MODEL_PATH.exists():
        raise SystemExit(f"No model at {common.MODEL_PATH}. Run train.py first.")

    model = joblib.load(common.MODEL_PATH)
    _, X_test, _, y_test = split(load_dataset())
    y_pred = model.predict(X_test)
    labels = [str(c) for c in model.classes_]

    accuracy = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    print(f"Test samples: {len(y_test)}")
    print(f"Accuracy:     {accuracy:.3f}")
    print(f"Macro F1:     {macro_f1:.3f}\n")
    print(classification_report(y_test, y_pred, labels=labels, zero_division=0))

    width = max(len(l) for l in labels) + 2
    print("Confusion matrix (rows = true, cols = predicted):")
    print(" " * width + "".join(f"{l:>{width}}" for l in labels))
    for label, row in zip(labels, cm):
        print(f"{label:<{width}}" + "".join(f"{int(v):>{width}}" for v in row))

    metrics = {
        "n_test": int(len(y_test)),
        "accuracy": round(float(accuracy), 4),
        "macro_f1": round(float(macro_f1), 4),
        "per_class": {l: {k: round(float(v), 4) for k, v in report[l].items()} for l in labels},
        "confusion_matrix": {"labels": labels, "matrix": cm.tolist()},
        "note": "Synthetic, template-based data: scores overstate real-world accuracy.",
    }
    common.METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nSaved metrics -> {common.METRICS_PATH}")


if __name__ == "__main__":
    main()
