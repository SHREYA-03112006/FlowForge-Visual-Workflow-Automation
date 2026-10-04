"""Thin API around ml_model_train/predict.py (the same model the ml_classifier node uses)."""
from __future__ import annotations

import asyncio
import importlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/ml", tags=["ml"])


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


def _predict_module():
    try:
        return importlib.import_module("ml_model_train.predict")
    except ImportError:
        raise HTTPException(503, "ml_model_train/predict.py not found yet") from None


@router.get("/status")
def ml_status():
    try:
        mod = importlib.import_module("ml_model_train.predict")
    except ImportError:
        return {"available": False, "reason": "ml_model_train package not found"}
    check = getattr(mod, "is_model_available", None)
    return {"available": bool(check()) if callable(check) else True}


@router.post("/classify")
async def classify(body: ClassifyRequest):
    mod = _predict_module()
    try:
        return await asyncio.to_thread(mod.predict, body.text)
    except FileNotFoundError:
        raise HTTPException(503, "Model not trained yet. Run: python -m ml_model_train.train") from None
