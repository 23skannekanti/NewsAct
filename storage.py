"""
SQLite storage for NewsAct. Zero-setup system of record.

One events table keeps everything: the raw normalized event, the analysis,
and the signal score. Dedup is enforced by a UNIQUE content hash.
Swap to Postgres later by porting these ~6 functions.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

DB_PATH = os.getenv("NEWSACT_DB", "newsact.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT,
    title TEXT NOT NULL,
    content TEXT,
    published_at TEXT,
    detected_at TEXT NOT NULL,
    event_type TEXT,
    tickers TEXT,            -- JSON list, e.g. ["NVDA", "BTC"]
    direction TEXT,          -- bullish | bearish | neutral | uncertain
    relevance_keywords TEXT, -- JSON list of matched keywords
    summary TEXT,            -- LLM summary (may be empty)
    confidence REAL,         -- LLM confidence 0-1 (may be null)
    impact REAL,             -- LLM impact 0-1 (may be null)
    source_quality REAL,
    signal_score INTEGER,    -- final deterministic score 0-100
    alerted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS llm_usage (
    day TEXT PRIMARY KEY,
    calls INTEGER NOT NULL DEFAULT 0,
    agent_calls INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS insights (
    event_id INTEGER PRIMARY KEY,
    figures TEXT,        -- JSON list of tracked figures named
    headline TEXT,
    mechanism TEXT,
    tickers TEXT,        -- JSON list of {ticker, direction, reasoning}
    time_horizon TEXT,
    confidence REAL,
    caveats TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_score ON events(signal_score);
CREATE INDEX IF NOT EXISTS idx_events_detected ON events(detected_at);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def content_hash(title: str, url: str) -> str:
    """Stage-1 dedup: same headline or same URL means same story."""
    key = (url or title).strip().lower()
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def is_duplicate(h: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM events WHERE hash = ?", (h,)).fetchone()
        return row is not None


def save_event(record: dict) -> int | None:
    """Insert one event dict; returns row id, or None if it was a duplicate."""
    cols = ("hash", "source_name", "source_type", "url", "title", "content",
            "published_at", "detected_at", "event_type", "tickers", "direction",
            "relevance_keywords", "summary", "confidence", "impact",
            "source_quality", "signal_score")
    values = [record.get(c) for c in cols]
    try:
        with get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO events ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                values)
            return cur.lastrowid
    except sqlite3.IntegrityError:  # duplicate hash
        return None


def get_events(min_score: int = 0, ticker: str = "", source_type: str = "",
               limit: int = 100, max_age_hours: int = 0) -> list[dict]:
    query = "SELECT * FROM events WHERE COALESCE(signal_score, 0) >= ?"
    params: list = [min_score]
    if ticker:
        query += " AND tickers LIKE ?"
        params.append(f'%"{ticker.upper()}"%')
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if max_age_hours:
        cutoff = (datetime.now(timezone.utc) -
                  timedelta(hours=max_age_hours)).isoformat()
        query += " AND published_at >= ?"
        params.append(cutoff)
    query += " ORDER BY CASE WHEN published_at = '' THEN 1 ELSE 0 END, published_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    events = []
    for row in rows:
        e = dict(row)
        e["tickers"] = json.loads(e["tickers"] or "[]")
        e["relevance_keywords"] = json.loads(e["relevance_keywords"] or "[]")
        events.append(e)
    return events


def mark_alerted(event_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE events SET alerted = 1 WHERE id = ?", (event_id,))


def stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
        signals = conn.execute(
            "SELECT COUNT(*) c FROM events WHERE signal_score >= 60").fetchone()["c"]
        llm = conn.execute("SELECT calls FROM llm_usage WHERE day = ?",
                           (date.today().isoformat(),)).fetchone()
    return {"total_events": total, "high_signals": signals,
            "llm_calls_today": llm["calls"] if llm else 0}


def llm_calls_today() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT calls FROM llm_usage WHERE day = ?",
                           (date.today().isoformat(),)).fetchone()
    return row["calls"] if row else 0


def record_llm_call() -> None:
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute("""INSERT INTO llm_usage (day, calls) VALUES (?, 1)
                        ON CONFLICT(day) DO UPDATE SET calls = calls + 1""", (today,))

def agent_calls_today() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT agent_calls FROM llm_usage WHERE day = ?",
                           (date.today().isoformat(),)).fetchone()
    return row["agent_calls"] if row else 0


def record_agent_call() -> None:
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute("""INSERT INTO llm_usage (day, calls, agent_calls) VALUES (?, 0, 1)
                        ON CONFLICT(day) DO UPDATE SET agent_calls = agent_calls + 1""",
                     (today,))


def save_insight(event_id: int, figures: list, insight: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO insights (event_id, figures, headline, mechanism,
               tickers, time_horizon, confidence, caveats, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (event_id, json.dumps(figures), insight["headline"], insight["mechanism"],
             json.dumps(insight["tickers"]), insight["time_horizon"],
             insight["confidence"], insight["caveats"],
             datetime.now(timezone.utc).isoformat()))


def get_insights(limit: int = 25) -> list[dict]:
    """Insights joined to their events, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT i.*, e.title, e.url, e.source_name, e.signal_score, e.published_at
               FROM insights i JOIN events e ON e.id = i.event_id
               ORDER BY i.created_at DESC LIMIT ?""", (limit,)).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["figures"] = json.loads(d["figures"] or "[]")
        d["tickers"] = json.loads(d["tickers"] or "[]")
        out.append(d)
    return out
