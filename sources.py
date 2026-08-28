"""
All information sources for NewsAct.

Every source implements the same tiny interface: fetch_events() -> list[RawEvent].
Sources are free/official first (SEC, Fed, gov/news RSS). NewsAPI is optional.
Add a new source by subclassing DataSource and appending it in get_sources().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

def to_iso(entry) -> str: 
    """Normalize any feed's publish date into a sortable UTC ISO string."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    return ""

# SEC requires a descriptive User-Agent on all requests.
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "NewsAct research tool contact@example.com")


@dataclass
class RawEvent:
    """Normalized event — every source converts its data into this."""
    source_name: str
    source_type: str            # sec | government | news | crypto
    title: str
    content: str = ""
    url: str = ""
    published_at: str = ""      # ISO string when available
    source_quality: float = 0.5 # 0.0–1.0 weight used by the signal engine
    metadata: dict = field(default_factory=dict)


class DataSource:
    """Base class. One failing source must never crash the monitor."""
    name = "base"
    source_type = "news"
    quality = 0.5
    poll_seconds = 300

    def fetch_events(self) -> list[RawEvent]:
        raise NotImplementedError


class SECSource(DataSource):
    """Latest SEC EDGAR filings (8-K = material events) via the free atom feed."""
    name = "SEC EDGAR"
    source_type = "sec"
    quality = 1.0
    poll_seconds = 60
    FEED = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
            "&type=8-K&company=&dateb=&owner=include&count=40&output=atom")

    def fetch_events(self) -> list[RawEvent]:
        resp = requests.get(self.FEED, headers={"User-Agent": SEC_USER_AGENT}, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        events = []
        for entry in feed.entries:
            events.append(RawEvent(
                source_name=self.name,
                source_type=self.source_type,
                title=entry.get("title", ""),
                content=entry.get("summary", ""),
                url=entry.get("link", ""),
                published_at=to_iso(entry),
                source_quality=self.quality,
                metadata={"filing_type": "8-K"},
            ))
        return events


class RSSSource(DataSource):
    """Generic RSS source — used for the Fed, government and financial news feeds."""

    def __init__(self, name: str, url: str, source_type: str, quality: float,
                 poll_seconds: int = 300):
        self.name = name
        self.url = url
        self.source_type = source_type
        self.quality = quality
        self.poll_seconds = poll_seconds

    def fetch_events(self) -> list[RawEvent]:
        resp = requests.get(self.url, headers={"User-Agent": "NewsAct/1.0"}, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        return [RawEvent(
            source_name=self.name,
            source_type=self.source_type,
            title=e.get("title", ""),
            content=e.get("summary", ""),
            url=e.get("link", ""),
            published_at=to_iso(e),
            source_quality=self.quality,
        ) for e in feed.entries]


class NewsAPISource(DataSource):
    """Optional NewsAPI source (kept from the original project). Needs NEWS_API_KEY."""
    name = "NewsAPI"
    source_type = "news"
    quality = 0.7
    poll_seconds = 900  # free tier — poll gently

    def __init__(self, query: str = "stock market"):
        self.api_key = os.getenv("NEWS_API_KEY", "")
        self.query = query

    def fetch_events(self) -> list[RawEvent]:
        if not self.api_key:
            return []
        url = ("https://newsapi.org/v2/everything"
               f"?q={self.query}&sortBy=publishedAt&language=en&pageSize=20"
               f"&apiKey={self.api_key}")
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return [RawEvent(
            source_name=self.name,
            source_type=self.source_type,
            title=a.get("title") or "",
            content=a.get("description") or "",
            url=a.get("url") or "",
            published_at=a.get("publishedAt") or "",
            source_quality=self.quality,
        ) for a in resp.json().get("articles", [])]


def get_sources() -> list[DataSource]:
    """Enabled sources. Comment a line out to disable a source."""
    sources: list[DataSource] = [
        SECSource(),
        RSSSource("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml",
                  "government", 1.0, poll_seconds=120),
        RSSSource("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html",
                  "news", 0.8, poll_seconds=300),
        RSSSource("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories",
                  "news", 0.8, poll_seconds=300),
        RSSSource("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/",
                  "crypto", 0.75, poll_seconds=300),
        RSSSource("Cointelegraph", "https://cointelegraph.com/rss",
                  "crypto", 0.7, poll_seconds=300),
        NewsAPISource(),
    ]
    return sources


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
