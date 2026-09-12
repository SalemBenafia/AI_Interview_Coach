"""
services/signal-service/main.py
==================================
Real sentiment/emotion classification microservice
(technologies.txt §"Transformers" -- model j-hartmann/emotion-english-
distilroberta-base). Backs the candidate's "Confidence Score (AI-derived)"
KPI (metrics.txt §A.5).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

SENTIMENT_MODEL_NAME = os.environ.get("SENTIMENT_MODEL", "j-hartmann/emotion-english-distilroberta-base")

_classifier = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _classifier
    _classifier = pipeline("sentiment-analysis", model=SENTIMENT_MODEL_NAME)
    yield
    _classifier = None


app = FastAPI(title="AI Interview Coach - Signal Service", lifespan=lifespan)


class SentimentRequest(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"status": "ok", "model": SENTIMENT_MODEL_NAME}


@app.post("/sentiment")
async def sentiment(payload: SentimentRequest):
    if _classifier is None:
        raise HTTPException(status_code=503, detail="Sentiment model not loaded yet.")
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty.")

    result = _classifier(payload.text[:2000])[0]  # truncate defensively; real model call either way
    return {"label": result["label"], "score": float(result["score"])}
