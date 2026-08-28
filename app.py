"""
NewsAct API + dashboard.

Run it:  uvicorn app:app --reload
Then open http://localhost:8000

Run monitor.py in a second terminal to keep events flowing in.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import storage

app = FastAPI(title="NewsAct", description="Real-time AI market intelligence")
storage.init_db()

DASHBOARD = Path(__file__).parent / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD.read_text()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", **storage.stats()}


@app.get("/api/events")
def events(min_score: int = 0, ticker: str = "", source_type: str = "",
           limit: int = 100) -> list[dict]:
    return storage.get_events(min_score, ticker, source_type, min(limit, 500))


@app.get("/api/signals")
def signals(min_score: int = 60, limit: int = 50) -> list[dict]:
    """High-scoring events only."""
    return storage.get_events(min_score=min_score, limit=min(limit, 200))


@app.get("/api/stats")
def stats() -> dict:
    return storage.stats()
