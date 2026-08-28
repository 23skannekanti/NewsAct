# NewsAct

**Real-time AI market intelligence.** NewsAct continuously monitors free, official
public sources — SEC EDGAR filings, Federal Reserve press releases, financial and
crypto news feeds — detects potentially market-moving events, identifies affected
stocks and cryptocurrencies, optionally analyzes them with an LLM, computes a
deterministic 0–100 signal score, and streams everything to a live dashboard.

> NewsAct is a research and market-intelligence tool. It **never places trades**,
> has no brokerage access, and its output is not investment advice.

## How it works

```
Sources (SEC · Fed · RSS · crypto · NewsAPI)
   ↓  normalize into RawEvent
Dedup (content hash)
   ↓
Keyword relevance filter        ← cheap, deterministic
   ↓  only if relevant
Ticker extraction (local map)   ← no LLM tokens wasted
   ↓  only if relevant + tickers found
LLM structured analysis         ← Claude Haiku, daily call budget
   ↓
Deterministic signal score      ← Python math, never the LLM
   ↓
SQLite → dashboard + alerts
```

The LLM is one component, not the system: with no API key configured, NewsAct
still runs end-to-end using deterministic scoring.

## Files

| File | Purpose |
|---|---|
| `sources.py` | All data sources behind one `DataSource` interface |
| `storage.py` | SQLite persistence, dedup hashes, LLM usage tracking |
| `analysis.py` | Relevance keywords, ticker map, LLM analysis, signal engine |
| `monitor.py` | The continuous ingestion loop + alerts |
| `app.py` | FastAPI API + serves the dashboard |
| `dashboard.html` | Live dashboard (vanilla HTML/JS, auto-refreshes) |
| `utils/email_alert.py` | Email alerts (from v1, reused) |
| `v1_legacy/` | Original CrewAI prototype, archived for reference |

New here? Read **[QUICKSTART.md](QUICKSTART.md)** instead — it has the 3-step setup.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in keys — all optional
```

## Run

Terminal 1 — the monitor (ingestion loop):
```bash
python monitor.py           # or: python monitor.py --once  (single test pass)
```

Terminal 2 — the API + dashboard:
```bash
uvicorn app:app --reload
```

Open http://localhost:8000

## API

```
GET /api/health
GET /api/events?min_score=&ticker=&source_type=&limit=
GET /api/signals?min_score=60
GET /api/stats
```

## Signal scoring

```
score = impact·0.35 + source_quality·0.30 + llm_confidence·0.20 + recency·0.15
```

Weights live at the top of `analysis.py`. Source quality is configured per
source (SEC/Fed = 1.0, major news ≈ 0.8, crypto media ≈ 0.7). Score bands:
0–39 low · 40–59 medium · 60–79 high · 80+ very high (alert threshold
defaults to 70 via `ALERT_MINIMUM_SCORE`).

## Cost controls

- Free official sources only; no paid data feeds required
- LLM called only after keyword relevance + ticker checks pass
- Hard daily LLM call cap (`MAX_LLM_CALLS_PER_DAY`, default 50)
- Dedup ensures no content is ever analyzed twice
- Cheap model by default (`claude-haiku-4-5`)
- Runs on SQLite — $0 infrastructure

## Roadmap

Corroboration across sources · price-reaction tracking · congressional
disclosures · WebSocket push · Postgres option · historical accuracy analytics.
