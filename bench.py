"""Verify the C++ matcher agrees with Python, then time both."""
import re, sqlite3, time

import analysis
import fastmatch
from storage import DB_PATH

rows = sqlite3.connect(DB_PATH).execute(
    "SELECT title, content FROM events WHERE content IS NOT NULL LIMIT 2000"
).fetchall()
texts = [f"{t or ''} {c or ''}" for t, c in rows]
print(f"{len(texts)} events, {sum(len(t) for t in texts)/1e6:.1f} MB of text")

PATTERNS = [(re.compile(rf"\b{re.escape(n)}\b"), tk)
            for n, tk in analysis.TICKER_MAP.items()]

def py_scan(text):
    low = text.lower()
    return sorted({tk for rx, tk in PATTERNS if rx.search(low)})

matcher = fastmatch.TickerMatcher(list(analysis.TICKER_MAP.items()))

bad = sum(1 for t in texts if py_scan(t) != matcher.scan(t))
print(f"mismatches: {bad}")

t = time.perf_counter()
for x in texts: py_scan(x)
py = time.perf_counter() - t

t = time.perf_counter()
for x in texts: matcher.scan(x)
cpp = time.perf_counter() - t

print(f"python {py*1000:7.1f} ms")
print(f"c++    {cpp*1000:7.1f} ms")
print(f"speedup {py/cpp:.1f}x")
