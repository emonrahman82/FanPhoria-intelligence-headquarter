"""
recommender.py
---------------
Turns raw Google Trends + AniList signals into a single "Demand Score"
per anime, plus a human-readable recommendation ("restock", "trending up",
"watch for overstock", etc.) that factors in your current stock level.

This is intentionally simple and transparent (a weighted average, not a
black box) so you can see exactly why something is recommended and tune
the weights as you learn what predicts sales for FanPhoria specifically.
"""

from trends_service import get_average_interest, get_trend_direction
from anilist_service import get_anime_metadata

# Tune these weights based on what turns out to actually predict sales.
# They must sum to 1.0.
WEIGHTS = {
    "trend_score": 0.40,      # Google Trends search interest (0-100)
    "anilist_trending": 0.25, # AniList's own trending rank signal
    "anilist_popularity": 0.20,  # How many users have it on their list
    "average_score": 0.15,    # Community rating -- quality signal
}

# Rough normalization ceilings so different scales (0-100 vs raw counts)
# combine fairly. Adjust as your dataset grows.
ANILIST_TRENDING_CEILING = 3000
ANILIST_POPULARITY_CEILING = 500000


def _normalize(value, ceiling):
    if not value:
        return 0.0
    return min(value / ceiling, 1.0) * 100


def score_anime(anime_name: str, current_stock: int = None, price: float = None,
                 geo: str = "", timeframe: str = "today 3-m"):
    """
    Computes a full recommendation record for one anime title.
    `current_stock` and `price` are optional -- pass them in from your own
    inventory data (watchlist.csv) to get stock-aware recommendations.
    """
    trend_avg = get_average_interest(anime_name, timeframe=timeframe, geo=geo)
    trend_direction = get_trend_direction(anime_name, timeframe=timeframe, geo=geo)
    anilist = get_anime_metadata(anime_name) or {}

    trend_component = trend_avg  # already 0-100
    trending_component = _normalize(anilist.get("trending", 0), ANILIST_TRENDING_CEILING)
    popularity_component = _normalize(anilist.get("popularity", 0), ANILIST_POPULARITY_CEILING)
    score_component = anilist.get("average_score", 0)  # already 0-100 on AniList

    demand_score = (
        WEIGHTS["trend_score"] * trend_component
        + WEIGHTS["anilist_trending"] * trending_component
        + WEIGHTS["anilist_popularity"] * popularity_component
        + WEIGHTS["average_score"] * score_component
    )

    recommendation, reason = _build_recommendation(
        demand_score, trend_direction, current_stock
    )

    return {
        "anime": anime_name,
        "demand_score": round(demand_score, 1),
        "trend_avg_interest": round(trend_avg, 1),
        "trend_direction": trend_direction,
        "anilist_trending": anilist.get("trending", 0),
        "anilist_popularity": anilist.get("popularity", 0),
        "average_score": anilist.get("average_score", 0),
        "genres": anilist.get("genres", []),
        "cover_image": anilist.get("cover_image"),
        "site_url": anilist.get("site_url"),
        "current_stock": current_stock,
        "price": price,
        "recommendation": recommendation,
        "reason": reason,
    }


def _build_recommendation(demand_score: float, trend_direction: str, current_stock):
    """Simple rule layer on top of the numeric score. Feel free to expand
    this with your own business rules (margin, supplier lead time, etc.)."""
    has_stock_info = current_stock is not None

    if demand_score >= 70:
        if has_stock_info and current_stock <= 5:
            return "Restock urgently", "High demand score with low/no current stock."
        return "Strong sell candidate", "High demand score across trends and fandom size."

    if demand_score >= 45:
        if trend_direction == "rising":
            return "Trending up - consider stocking", "Moderate demand and interest is climbing."
        if has_stock_info and current_stock and current_stock > 30:
            return "Monitor - possible overstock", "Moderate demand but stock level looks high."
        return "Watch closely", "Moderate demand, not yet a clear signal either way."

    if trend_direction == "falling" and has_stock_info and current_stock and current_stock > 20:
        return "Overstock risk", "Low/declining interest with meaningful stock on hand."

    return "Low priority", "Demand signals are currently weak."


def rank_recommendations(items: list) -> list:
    """Sorts a list of score_anime() results by demand score, descending."""
    return sorted(items, key=lambda x: x["demand_score"], reverse=True)
