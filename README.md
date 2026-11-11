# Watchlog 🎬

A tiny, free-forever dashboard of everything I've streamed (Netflix, Prime Video,
Hulu, Disney+, HBO Max, Apple TV), with the IMDb rating of every show, movie and
episode. Built with plain HTML/JS + [Vega-Lite](https://vega.github.io/vega-lite/)
and hosted on **GitHub Pages**, the same way as
[bukoclubo.data](https://github.com/periclesrocha/bukoclubo.data).

**Live site:** https://periclesrocha.github.io/watchlog.data/

## What's on the page

- **What to watch next**: hand-picked recommendations based on my history
  (`data/recommendations.csv`), each with its IMDb rating and the titles that led to it.
- **Pick up where you left off**: well-rated shows I haven't finished, with the next episode.
- Hours per year, most-watched shows, hours by genre, the IMDb rating of what I watch,
  my own ratings vs. IMDb, movies by decade.
- **Episode ratings**: pick any show to see a season × episode heatmap of IMDb ratings,
  with the episodes I've watched outlined, plus the best episodes I've seen.
- The full, searchable history, and a few useless charts (when I watch, binge days).

## How it works

```
Trakt export (.zip) ──► scripts/import_trakt.py ──► data/*.csv ──► GitHub Action ──► data/dashboard.json ──► index.html
                         (runs on your computer)                  (adds IMDb data)    data/episodes.json
```

- Streaming services sync into [Trakt](https://trakt.tv) (Settings → Streaming Sync).
- `scripts/import_trakt.py` turns a Trakt data export into three CSVs:
  `data/watch_history.csv` (one row per play), `data/shows.csv` and `data/my_ratings.csv`.
  Titles listed in `exclude.txt` (kids' viewing) are left out. `exclude.txt` stays on
  your computer: it's in `.gitignore`.
- A GitHub Action (`.github/workflows/build-data.yml`) runs `scripts/build_dashboard.py`
  on every push and every Monday. It downloads IMDb's public datasets,
  joins ratings, genres and runtimes to every play (including episodes Trakt had no
  IMDb ID for, matched by season and episode number), and commits
  `data/dashboard.json` and `data/episodes.json` back to the repo, then publishes the
  site to GitHub Pages.
- `index.html` loads those two files and draws everything. No server, no API keys.

## Updating the data

1. On [Trakt](https://app.trakt.tv/settings/data), export your data and download the ZIP.
2. With `exclude.txt` in the repo folder, run:
   ```bash
   python scripts/import_trakt.py ~/Downloads/trakt-export-XXXX.zip
   ```
3. Commit and push the changed `data/*.csv`. The Action rebuilds the dashboard data
   and republishes the site within a couple of minutes.

Titles watched somewhere that didn't sync (no dates) go in `data/also_watched.csv`
(`title`, `year`, `type`, `imdb_id`, `note`). They're listed under the history and
never recommended.

To change the recommendations, edit `data/recommendations.csv` (`title`, `year`,
`type` = `show` or `movie`, `because`, `why`; `imdb_id` is optional and only needed if
the title match picks the wrong one) and push. Anything already in the history is
skipped automatically.

### Running the build locally (optional)

Only the Python standard library is needed. The first run downloads about 250 MB of
IMDb data into `.imdb-cache/` (ignored by git).

```bash
python scripts/build_dashboard.py
python -m http.server   # then open http://localhost:8000
```

## Enabling GitHub Pages (one-time setup)

Settings → Pages → Build and deployment → Source: **GitHub Actions**.
The same workflow that rebuilds the data also publishes the site, on every push
and every Monday (Actions tab → "Build data and deploy site" → Run workflow to
publish on demand).

## Credits

Watch history from [Trakt](https://trakt.tv).
Information courtesy of IMDb (https://www.imdb.com). Used with permission.
IMDb data comes from the [IMDb non-commercial datasets](https://developer.imdb.com/non-commercial-datasets/)
and is used here for personal, non-commercial purposes only.
