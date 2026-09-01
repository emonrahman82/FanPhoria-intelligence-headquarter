# FanPhoria Anime Intelligence Platform

A personal dashboard that turns Google Trends search interest and AniList
fandom data into a ranked "what to sell next" list for your anime merch
watchlist.

## What it does

For every anime you track, it pulls:
- **Google Trends** search interest over time (via the unofficial `pytrends` library)
- **AniList** fandom metadata — trending rank, popularity, community score (via AniList's free public GraphQL API)

...and combines them into one **Demand Score** (0–100), plus a plain-language
recommendation: *Restock urgently*, *Trending up*, *Overstock risk*, etc.,
factoring in the stock level you enter for each title.

It also shows a "Discover" strip of what's trending globally on AniList,
in case there's a title worth adding that you haven't thought of.

## Project structure

```
fanphoria-intelligence/
├── backend/
│   ├── app.py               Flask API server
│   ├── trends_service.py    Google Trends wrapper (pytrends)
│   ├── anilist_service.py   AniList GraphQL wrapper
│   ├── recommender.py       Scoring + recommendation logic
│   ├── watchlist.csv        Your tracked titles + stock/price (sample data included)
│   └── requirements.txt
└── frontend/
    └── index.html           The dashboard (open directly in a browser)
```

## Setup

1. Install Python dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```

2. Start the backend:
   ```
   python app.py
   ```
   This runs the API at `http://localhost:5000`. Leave this running.

3. Open `frontend/index.html` in your browser (just double-click it, or
   serve it with any static file server). It talks to the backend
   automatically.

That's it — no database, no build step.

## Editing your watchlist

You can add/remove titles right from the dashboard, or edit
`backend/watchlist.csv` directly:

```csv
anime_name,current_stock,price
Jujutsu Kaisen,12,24.99
```

Restart the backend (or just refresh — it re-reads the file on every
request) after manual edits.

## Things worth knowing

- **Google Trends has no official API.** `pytrends` scrapes the same data
  the trends.google.com website uses. If you query a lot of titles very
  quickly, Google may temporarily rate-limit you (you'll see empty trend
  data). The app caches results for 3 hours per title to keep this rare.
- **Keyword phrasing matters.** Google Trends is picky — "Jujutsu Kaisen"
  and "JJK" can return different results. If a title looks like it has
  suspiciously flat/zero interest, try the more common search term fans
  actually type.
- **AniList matching is fuzzy but not perfect.** It searches by title, so
  very obscure or ambiguously-named series might match the wrong anime.
  Check the "AniList trending/popularity" numbers in the detail view if a
  score looks off.
- **The scoring weights are a starting point**, not gospel. Open
  `backend/recommender.py` and adjust the `WEIGHTS` dictionary once you
  have a few weeks of real sales data to compare against — that's the
  fastest way to make this actually predictive for FanPhoria specifically.

## Extending it later

Natural next additions, in rough order of effort:
1. **Your own sales data** — swap the CSV for a read of your actual sales
   export, and feed historical sell-through into the scoring weights.
2. **Social trends** — add a service module for whatever platform you have
   API access to (X/Twitter, TikTok, Reddit) following the same pattern as
   `trends_service.py` / `anilist_service.py`.
3. **Competitor pricing** — a scraper or manually-updated CSV of competitor
   prices per title, factored into the recommendation ("high demand, but
   competitors are underpricing you").
4. **Persistence** — swap the CSV for SQLite if your watchlist grows past a
   few dozen titles.
