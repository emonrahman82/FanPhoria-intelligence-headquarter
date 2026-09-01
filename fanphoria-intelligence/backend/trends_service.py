"""
trends_service.py
------------------
Wraps the unofficial `pytrends` library to pull Google Trends interest data
for a given anime / product keyword.

Google Trends has no official public API, so pytrends scrapes the same
endpoints the trends.google.com website uses. This means:
  - It can be rate-limited or temporarily blocked (HTTP 429) if you query
    too fast. We add small delays and simple caching to reduce that risk.
  - Keyword phrasing matters a lot (e.g. "Jujutsu Kaisen" vs "JJK") --
    consider trying a couple of variants if results look empty.

If a live call fails for any reason, functions fall back to returning
`None` / empty structures rather than crashing, so the rest of the
dashboard keeps working with whatever data IS available.
"""

import time
import logging
from functools import lru_cache

from pytrends.request import TrendReq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trends_service")

# Small in-memory cache: {keyword: (timestamp, data)}
_CACHE = {}
_CACHE_TTL_SECONDS = 60 * 60 * 3  # 3 hours -- Trends data doesn't change that fast


def _get_pytrends_client():
    # hl = language, tz = timezone offset in minutes (0 = UTC)
    return TrendReq(hl="en-US", tz=360)


def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        return None
    return data


def _cache_set(key, data):
    _CACHE[key] = (time.time(), data)


def get_interest_over_time(keyword: str, timeframe: str = "today 3-m", geo: str = ""):
    """
    Returns a list of {date, interest} dicts for the last `timeframe` window.
    interest is Google's 0-100 relative popularity score.

    timeframe examples: 'today 3-m' (3 months), 'today 12-m' (12 months),
    'now 7-d' (7 days).
    geo examples: '' (worldwide), 'US', 'JP', 'BD'.
    """
    cache_key = f"iot::{keyword}::{timeframe}::{geo}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        pytrends = _get_pytrends_client()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if df.empty:
            result = []
        else:
            result = [
                {"date": str(idx.date()), "interest": int(row[keyword])}
                for idx, row in df.iterrows()
            ]
        _cache_set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Google Trends fetch failed for '%s': %s", keyword, exc)
        return []


def get_average_interest(keyword: str, timeframe: str = "today 3-m", geo: str = "") -> float:
    """Convenience helper: mean interest score over the window, 0 if unavailable."""
    series = get_interest_over_time(keyword, timeframe=timeframe, geo=geo)
    if not series:
        return 0.0
    return sum(p["interest"] for p in series) / len(series)


def get_trend_direction(keyword: str, timeframe: str = "today 3-m", geo: str = "") -> str:
    """
    Rough direction classifier comparing the first half vs second half of the
    window: 'rising', 'falling', or 'flat'. Useful for flagging overstock risk
    (high stock + falling trend) vs. restock opportunity (rising trend).
    """
    series = get_interest_over_time(keyword, timeframe=timeframe, geo=geo)
    if len(series) < 4:
        return "unknown"

    midpoint = len(series) // 2
    first_half_avg = sum(p["interest"] for p in series[:midpoint]) / midpoint
    second_half_avg = sum(p["interest"] for p in series[midpoint:]) / (len(series) - midpoint)

    if first_half_avg == 0 and second_half_avg == 0:
        return "flat"

    change = second_half_avg - first_half_avg
    if change > 5:
        return "rising"
    elif change < -5:
        return "falling"
    return "flat"


def get_regional_interest(keyword: str, timeframe: str = "today 3-m", top_n: int = 5):
    """Returns top N regions by interest for the keyword, e.g. for spotting
    where demand is concentrated (useful for shipping/marketing decisions)."""
    cache_key = f"region::{keyword}::{timeframe}::{top_n}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        pytrends = _get_pytrends_client()
        pytrends.build_payload([keyword], timeframe=timeframe)
        df = pytrends.interest_by_region(resolution="COUNTRY")
        if df.empty:
            result = []
        else:
            df = df.sort_values(by=keyword, ascending=False).head(top_n)
            result = [{"region": idx, "interest": int(row[keyword])} for idx, row in df.iterrows()]
        _cache_set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Google Trends region fetch failed for '%s': %s", keyword, exc)
        return []
