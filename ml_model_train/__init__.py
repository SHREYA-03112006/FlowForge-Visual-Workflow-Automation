"""Support-ticket classifier used by the workflow engine's ML node.

Typical use from the backend:

    from ml_model_train.predict import predict
    result = predict("I was charged twice this month")
    # {"label": "billing", "confidence": 0.71, "scores": {...}, "low_confidence": False}
"""
