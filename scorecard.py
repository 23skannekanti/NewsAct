import sqlite3
from datetime import datetime, timedelta, timezone

import yfinance as yf

from storage import DB_PATH

# yfinance needs crypto spelled out
CRYPTO = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "DOGE": "DOGE-USD",
    "XRP": "XRP-USD", "ADA": "ADA-USD", "AVAX": "AVAX-USD", "LINK": "LINK-USD",
    "DOT": "DOT-USD", "MATIC": "MATIC-USD", "LTC": "LTC-USD", "BNB": "BNB-USD",
}

SKIP = {"USDT", "USDC", "DAI", "BUSD"}


def get_price(ticker):
    if ticker in SKIP:
        return None
    symbol = CRYPTO.get(ticker, ticker)
    try:
        return float(yf.Ticker(symbol).fast_info["last_price"])
    except Exception:
        return None


def log_prediction(event_id, tickers, source, score):
    """Write down the price at the moment we saw the news."""
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    for ticker in tickers:
        price = get_price(ticker)
        if price is None:
            continue         
        conn.execute(
            "INSERT INTO scorecard (event_id, ticker, source, score, price_then, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, ticker, source, score, price, now),
        )
    conn.commit()
    conn.close()

def grade_old_predictions(hours=24):
    """Fill in price_later for anything old enough to grade."""
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT id, ticker, price_then FROM scorecard"
        " WHERE price_later IS NULL AND created_at < ?", (cutoff,)
    ).fetchall()

    graded = 0
    for row_id, ticker, price_then in rows:
        price_now = get_price(ticker)
        if price_now is None or not price_then:
            continue
        pct = (price_now - price_then) / price_then * 100
        conn.execute(
            "UPDATE scorecard SET price_later = ?, pct_move = ? WHERE id = ?",
            (price_now, round(pct, 3), row_id),
        )
        graded += 1

    conn.commit()
    conn.close()
    return graded