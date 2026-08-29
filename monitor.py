
from __future__ import annotations
import json
import os
import sys
import time
import political

from dotenv import load_dotenv


import analysis
import storage
from sources import get_sources, now_iso, DataSource, RawEvent


load_dotenv()

ALERT_MINIMUM_SCORE = int(os.getenv("ALERT_MINIMUM_SCORE", "70"))
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"


def process_event(event: RawEvent) -> dict | None:
    """Run one raw event through the full pipeline. Returns the saved record or None."""
    h = storage.content_hash(event.title, event.url)
    if storage.is_duplicate(h):
        return None

    matched = analysis.check_relevance(event)
    tickers = analysis.extract_tickers(event)

    llm = analysis.analyze_with_llm(event, tickers) if (matched and tickers) else None
    if llm and llm.get("tickers"):
        tickers = sorted(set(tickers) | set(llm["tickers"]))

    score = analysis.compute_signal(event, llm, matched) if matched else 0

    record = {
        "hash": h,
        "source_name": event.source_name,
        "source_type": event.source_type,
        "url": event.url,
        "title": event.title,
        "content": event.content[:3000],
        "published_at": event.published_at,
        "detected_at": now_iso(),
        "event_type": analysis.guess_event_type(matched),
        "tickers": json.dumps(tickers),
        "direction": llm["direction"] if llm else None,
        "relevance_keywords": json.dumps(matched),
        "summary": llm["summary"] if llm else None,
        "confidence": llm["confidence"] if llm else None,
        "impact": llm["impact"] if llm else None,
        "source_quality": event.source_quality,
        "signal_score": score,
    }
    event_id = storage.save_event(record)
    if event_id is None:
        return None
    record["id"] = event_id

    # Political insight agent
    figures = political.should_run(score, event.title, event.content)
    if figures:
        print(f"  🏛  political agent running ({', '.join(figures)})…")
        insight = political.research_insight(
            event.title, event.content, event.source_name, figures, tickers)
        if insight:
            storage.save_insight(event_id, figures, insight)
            print(f"     💡 {insight['headline']}")

    if score >= ALERT_MINIMUM_SCORE:
        send_alert(record)
    return record


def send_alert(record: dict) -> None:
    tickers = ", ".join(json.loads(record["tickers"])) or "market-wide"
    line = (f"NEWSACT ALERT [{record['signal_score']}/100] "
            f"{record['direction'] or 'unknown'} | {tickers} | {record['title']}")
    print(f"\n  🚨 {line}")
    if EMAIL_ENABLED:
        try:
            from utils.email_alert import send_alert_email  # reuses existing util
            body = (f"{record['title']}\n\nScore: {record['signal_score']}/100\n"
                    f"Direction: {record['direction']}\nTickers: {tickers}\n"
                    f"Summary: {record['summary'] or 'n/a'}\n\n{record['url']}\n\n"
                    "Estimated signal only — not investment advice.")
            send_alert_email(f"[NewsAct] {record['signal_score']}/100 {tickers}", body)
        except Exception as e:
            print(f"  Email alert failed: {e}")
    storage.mark_alerted(record["id"])


def poll_source(source: DataSource) -> int:
    """Fetch and process one source. Errors are logged, never fatal."""
    try:
        events = source.fetch_events()
    except Exception as e:
        print(f"  [{source.name}] fetch failed: {e}")
        return 0
    saved = sum(1 for ev in events if process_event(ev))
    print(f"  [{source.name}] {len(events)} fetched, {saved} new")
    return saved


def run(once: bool = False) -> None:
    storage.init_db()
    sources = get_sources()
    next_run = {s.name: 0.0 for s in sources}
    print(f"NewsAct monitor started — {len(sources)} sources, "
          f"alert threshold {ALERT_MINIMUM_SCORE}. Ctrl+C to stop.")
    while True:
        now = time.time()
        for source in sources:
            if now >= next_run[source.name]:
                poll_source(source)
                next_run[source.name] = now + source.poll_seconds
        if once:
            break
        time.sleep(5)


if __name__ == "__main__":
    run(once="--once" in sys.argv)
