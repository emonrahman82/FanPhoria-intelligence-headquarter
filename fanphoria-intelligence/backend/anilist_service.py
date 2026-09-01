"""
anilist_service.py
-------------------
Wraps AniList's free, public GraphQL API (https://graphql.anilist.co).
No API key required. Docs: https://docs.anilist.co/

We pull popularity, trending rank, average score, and favourites for a
given anime title -- these act as a proxy for "how big is the fandom
right now", independent of Google Trends.
"""

import time
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anilist_service")

ANILIST_URL = "https://graphql.anilist.co"

_CACHE = {}
_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours

_SEARCH_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    title {
      romaji
      english
    }
    popularity
    favourites
    averageScore
    trending
    status
    format
    genres
    coverImage {
      medium
    }
    siteUrl
  }
}
"""

# The general "Trending" list, useful as a sanity check / discovery feed
# separate from any single title lookup.
_TRENDING_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(sort: TRENDING_DESC, type: ANIME) {
      id
      title {
        romaji
        english
      }
      trending
      popularity
      averageScore
      genres
    }
  }
}
"""


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


def get_anime_metadata(title: str):
    """
    Looks up a single anime by (fuzzy) title match and returns its
    popularity/trending metadata, or None if not found / on error.
    """
    cache_key = f"meta::{title.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.post(
            ANILIST_URL,
            json={"query": _SEARCH_QUERY, "variables": {"search": title}},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        media = data.get("data", {}).get("Media")
        if not media:
            return None

        result = {
            "id": media["id"],
            "title": media["title"]["english"] or media["title"]["romaji"],
            "popularity": media.get("popularity", 0),
            "favourites": media.get("favourites", 0),
            "average_score": media.get("averageScore") or 0,
            "trending": media.get("trending", 0),
            "status": media.get("status"),
            "format": media.get("format"),
            "genres": media.get("genres", []),
            "cover_image": (media.get("coverImage") or {}).get("medium"),
            "site_url": media.get("siteUrl"),
        }
        _cache_set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("AniList lookup failed for '%s': %s", title, exc)
        return None


def get_trending_list(per_page: int = 20):
    """Returns AniList's own global trending anime list, for discovery of
    titles you might not be tracking yet but should consider stocking."""
    cache_key = f"trending::{per_page}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.post(
            ANILIST_URL,
            json={"query": _TRENDING_QUERY, "variables": {"page": 1, "perPage": per_page}},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        media_list = data.get("data", {}).get("Page", {}).get("media", [])
        result = [
            {
                "id": m["id"],
                "title": m["title"]["english"] or m["title"]["romaji"],
                "trending": m.get("trending", 0),
                "popularity": m.get("popularity", 0),
                "average_score": m.get("averageScore") or 0,
                "genres": m.get("genres", []),
            }
            for m in media_list
        ]
        _cache_set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("AniList trending list fetch failed: %s", exc)
        return []
