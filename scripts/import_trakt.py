#!/usr/bin/env python3
"""Turn a Trakt data export (.zip or unzipped folder) into the CSVs this app reads.

    python scripts/import_trakt.py ~/Downloads/trakt-export-XXXX.zip

Writes:
  data/watch_history.csv  one row per play (episode or movie)
  data/shows.csv          one row per show (aired episode count, for "pick up where you left off")
  data/my_ratings.csv     your own Trakt ratings (1-10)

Titles listed in exclude.txt (one "Title (Year)" per line, kept out of git) are dropped.
Only the standard library is needed.
"""
import argparse
import collections
import csv
import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def open_export(path: Path):
    """Return a function name -> parsed JSON (or None) for a zip or a folder."""
    if path.is_dir():
        def read(name):
            p = path / name
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        names = [p.name for p in path.iterdir()]
    else:
        zf = zipfile.ZipFile(path)
        index = {Path(n).name: n for n in zf.namelist()}
        names = list(index)

        def read(name):
            if name not in index:
                return None
            return json.loads(zf.read(index[name]).decode("utf-8"))
    return read, names


def load_excludes(path: Path):
    keys = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keys.add(line.casefold())
    return keys


def key(title, year):
    return f"{title} ({year})".casefold() if year else str(title).casefold()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=Path, help="Trakt export .zip or unzipped folder")
    ap.add_argument("--exclude", type=Path, default=ROOT / "exclude.txt")
    ap.add_argument("--tz", default="America/Los_Angeles", help="time zone for watch dates")
    args = ap.parse_args()

    read, names = open_export(args.export)
    tz = ZoneInfo(args.tz)
    excludes = load_excludes(args.exclude)

    history = []
    for n in sorted(names, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]):
        if re.fullmatch(r"watched-history(-\d+)?\.json", n):
            history += read(n) or []
    if not history:
        sys.exit("No watched-history*.json found in the export.")

    # Trakt stamps plays that arrive without a real date (e.g. Hulu, Disney+) with the
    # sync time, so dozens share one exact timestamp. Flag those as undated.
    stamp_counts = collections.Counter(e["watched_at"] for e in history)
    undated_stamps = {s for s, c in stamp_counts.items() if c >= 20}

    rows, shows, dropped = [], {}, collections.Counter()
    for e in history:
        if e["type"] == "movie":
            m = e["movie"]
            title, year = m["title"], m.get("year")
            ids, show_ids, ep = m["ids"], {}, {}
        else:
            s, ep = e["show"], e["episode"]
            title, year = s["title"], s.get("year")
            ids, show_ids = ep["ids"], s["ids"]
        if key(title, year) in excludes:
            dropped[f"{title} ({year})"] += 1
            continue
        dated = e["watched_at"] not in undated_stamps
        when = datetime.fromisoformat(e["watched_at"].replace("Z", "+00:00")).astimezone(tz)
        rows.append({
            "watched_at": when.strftime("%Y-%m-%dT%H:%M") if dated else "",
            "type": e["type"],
            "title": title,
            "year": year or "",
            "season": ep.get("season", ""),
            "episode": ep.get("number", ""),
            "episode_title": ep.get("title") or "",
            "imdb_id": ids.get("imdb") or "",
            "show_imdb_id": show_ids.get("imdb") or "",
            "tmdb_id": (show_ids or ids).get("tmdb") or "",
            "trakt_id": (show_ids or ids).get("trakt") or "",
        })
        if e["type"] == "episode":
            shows[s["ids"]["trakt"]] = {
                "title": title, "year": year or "", "imdb_id": show_ids.get("imdb") or "",
                "tmdb_id": show_ids.get("tmdb") or "", "trakt_id": show_ids.get("trakt"),
                "aired_episodes": s.get("aired_episodes") or "",
            }

    rows.sort(key=lambda r: (r["watched_at"] or "0000", r["title"], str(r["season"]).zfill(3), str(r["episode"]).zfill(4)), reverse=True)

    DATA.mkdir(exist_ok=True)
    with open(DATA / "watch_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with open(DATA / "shows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "year", "imdb_id", "tmdb_id", "trakt_id", "aired_episodes"])
        w.writeheader()
        w.writerows(sorted(shows.values(), key=lambda s: s["title"].casefold()))

    ratings = []
    for fname, kind in (("ratings-shows.json", "show"), ("ratings-movies.json", "movie")):
        for r in read(fname) or []:
            item = r[kind]
            if key(item["title"], item.get("year")) in excludes:
                continue
            ratings.append({"type": kind, "title": item["title"], "year": item.get("year") or "",
                            "imdb_id": item["ids"].get("imdb") or "", "rating": r["rating"],
                            "rated_at": r.get("rated_at", "")[:10]})
    with open(DATA / "my_ratings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["type", "title", "year", "imdb_id", "rating", "rated_at"])
        w.writeheader()
        w.writerows(sorted(ratings, key=lambda r: (-int(r["rating"]), r["title"].casefold())))

    undated = sum(1 for r in rows if not r["watched_at"])
    print(f"Wrote {len(rows)} plays ({undated} without a watch date), {len(shows)} shows, {len(ratings)} ratings.")
    print(f"Left out {sum(dropped.values())} plays from {len(dropped)} excluded titles.")


if __name__ == "__main__":
    main()
