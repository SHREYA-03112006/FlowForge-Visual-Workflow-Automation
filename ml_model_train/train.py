"""Train the support-ticket classifier and save it to saved_model/.

Run from the repo root:   python -m ml_model_train.train
or from this folder:      python train.py
Add --full to refit on ALL data before saving (use for the final submission model).
"""
import argparse
import json
from datetime import datetime, timezone

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

try:
    from . import common
except ImportError:  # executed as a plain script
    import common


def load_dataset(path=common.DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path).dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    return df[df["text"] != ""].reset_index(drop=True)


def split(df: pd.DataFrame):
    """Stratified train/test split; evaluate.py reuses this for a matching held-out set."""
    return train_test_split(
        df["text"], df["label"],
        test_size=common.TEST_SIZE,
        random_state=common.RANDOM_STATE,
        stratify=df["label"],
    )


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
        )),
        ("clf", LogisticRegression(C=5.0, max_iter=1000, class_weight="balanced")),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true",
                        help="refit on the full dataset before saving")
    args = parser.parse_args()

    df = load_dataset()
    print(f"Loaded {len(df)} tickets. Class counts:\n{df['label'].value_counts().to_string()}\n")

    X_train, X_test, y_train, y_test = split(df)

    cv_scores = cross_val_score(build_pipeline(), X_train, y_train, cv=5)
    print(f"5-fold CV accuracy (train split): {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")

    model = build_pipeline().fit(X_train, y_train)
    test_acc = float(model.score(X_test, y_test))
    print(f"Held-out test accuracy: {test_acc:.3f}")

    if args.full:
        model = build_pipeline().fit(df["text"], df["label"])
        print("Refit on the full dataset for the saved model.")

    common.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, common.MODEL_PATH)

    metadata = {
        "labels": [str(c) for c in model.classes_],
        "n_samples": int(len(df)),
        "cv_accuracy_mean": round(float(cv_scores.mean()), 4),
        "test_accuracy": round(test_acc, 4),
        "trained_on_full_data": bool(args.full),
        "sklearn_version": sklearn.__version__,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    common.METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\nSaved model    -> {common.MODEL_PATH}")
    print(f"Saved metadata -> {common.METADATA_PATH}")


if __name__ == "__main__":
    main()
