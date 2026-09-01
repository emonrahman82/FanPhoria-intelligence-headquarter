"""
app.py
------
FanPhoria Anime Intelligence Platform - backend API.

Run locally with:
    pip install -r requirements.txt
    python app.py

Then open frontend/index.html in your browser (it calls this API at
http://localhost:5000 by default).

Endpoints:
    GET  /api/watchlist                 -> list tracked anime + stock/price
    POST /api/watchlist                 -> add a new anime to track
    DELETE /api/watchlist/<anime_name>  -> stop tracking an anime
    GET  /api/recommendations           -> full scored + ranked list
    GET  /api/trends/<anime_name>       -> raw Google Trends time series (for charting)
    GET  /api/discover                  -> AniList's global trending list
                                            (titles you aren't tracking yet)
"""

import csv
import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

from trends_service import get_interest_over_time
from anilist_service import get_trending_list
from recommender import score_anime, rank_recommendations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = Flask(__name__)
CORS(app)  # allow the frontend (served from file:// or a different port) to call this API

WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "watchlist.csv")


def _read_watchlist():
    if not os.path.exists(WATCHLIST_PATH):
        return []
    with open(WATCHLIST_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append({
                "anime_name": row["anime_name"],
                "current_stock": int(row["current_stock"]) if row.get("current_stock") else None,
                "price": float(row["price"]) if row.get("price") else None,
            })
        return rows


def _write_watchlist(rows):
    with open(WATCHLIST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["anime_name", "current_stock", "price"])
        writer.writeheader()
        writer.writerows(rows)


@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    return jsonify(_read_watchlist())


@app.route("/api/watchlist", methods=["POST"])
def add_to_watchlist():
    body = request.get_json(force=True) or {}
    anime_name = (body.get("anime_name") or "").strip()
    if not anime_name:
        return jsonify({"error": "anime_name is required"}), 400

    rows = _read_watchlist()
    if any(r["anime_name"].lower() == anime_name.lower() for r in rows):
        return jsonify({"error": "already tracked"}), 409

    rows.append({
        "anime_name": anime_name,
        "current_stock": body.get("current_stock"),
        "price": body.get("price"),
    })
    _write_watchlist(rows)
    return jsonify({"status": "added", "anime_name": anime_name}), 201


@app.route("/api/watchlist/<anime_name>", methods=["DELETE"])
def remove_from_watchlist(anime_name):
    rows = _read_watchlist()
    filtered = [r for r in rows if r["anime_name"].lower() != anime_name.lower()]
    if len(filtered) == len(rows):
        return jsonify({"error": "not found"}), 404
    _write_watchlist(filtered)
    return jsonify({"status": "removed", "anime_name": anime_name})


@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    geo = request.args.get("geo", "")
    timeframe = request.args.get("timeframe", "today 3-m")

    watchlist = _read_watchlist()
    results = []
    for item in watchlist:
        try:
            scored = score_anime(
                item["anime_name"],
                current_stock=item.get("current_stock"),
                price=item.get("price"),
                geo=geo,
                timeframe=timeframe,
            )
            results.append(scored)
        except Exception as exc:
            logger.warning("Failed to score %s: %s", item["anime_name"], exc)

    return jsonify(rank_recommendations(results))


@app.route("/api/trends/<anime_name>", methods=["GET"])
def get_trend_series(anime_name):
    geo = request.args.get("geo", "")
    timeframe = request.args.get("timeframe", "today 3-m")
    series = get_interest_over_time(anime_name, timeframe=timeframe, geo=geo)
    return jsonify(series)


@app.route("/api/discover", methods=["GET"])
def discover():
    per_page = int(request.args.get("limit", 20))
    trending = get_trending_list(per_page=per_page)
    watchlist_names = {w["anime_name"].lower() for w in _read_watchlist()}
    for item in trending:
        item["already_tracked"] = item["title"].lower() in watchlist_names
    return jsonify(trending)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
