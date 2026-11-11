#!/usr/bin/env python3
"""Join the watch history with IMDb's public datasets and write the files the page reads.

    python scripts/build_dashboard.py                 # downloads IMDb data into .imdb-cache/
    python scripts/build_dashboard.py --imdb-dir DIR  # use title.*.tsv.gz already in DIR

Reads  data/watch_history.csv, data/shows.csv, data/my_ratings.csv, data/recommendations.csv,
       data/also_watched.csv (titles seen outside the synced history, without dates)
       data/quiz_answers.csv (answers from the page's "Have I seen it?" section)
       data/finished_shows.csv (shows finished outside the synced history)
Writes data/dashboard.json  (plays, shows, movies, recommendations, pick-up-where-you-left-off)
       data/episodes.json   (every episode of every show you watched, with its IMDb rating)
       data/quiz.json       (popular IMDb titles not watched or answered yet, for the quiz)

IMDb data: https://developer.imdb.com/non-commercial-datasets/ (personal, non-commercial use).
Only the standard library is needed.
"""
import argparse
import collections
import csv
import gzip
import json
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMDB_BASE = "https://datasets.imdbws.com/"
FILES = ["title.ratings.tsv.gz", "title.episode.tsv.gz", "title.basics.tsv.gz"]
SHOW_TYPES = {"tvSeries", "tvMiniSeries"}
QUIZ_MIN_VOTES_MOVIE = 100_000
QUIZ_MIN_VOTES_SHOW = 50_000
QUIZ_POOL_MOVIES = 800
QUIZ_POOL_SHOWS = 400
MOVIE_TYPES = {"movie", "tvMovie", "video", "tvSpecial"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fetch(imdb_dir: Path):
    imdb_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = imdb_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        log(f"Downloading {name} ...")
        req = urllib.request.Request(IMDB_BASE + name, headers={"User-Agent": "watchlog.data"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)


def tsv(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        header = f.readline().rstrip("\n").split("\t")
        for line in f:
            yield dict(zip(header, line.rstrip("\n").split("\t")))


def nn(v):
    """IMDb uses \\N for missing values."""
    return None if v in ("\\N", "", None) else v


def to_int(v):
    v = nn(v)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def norm(title: str) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    t = t.casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", t)


def read_csv(name):
    p = DATA / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--imdb-dir", type=Path, default=ROOT / ".imdb-cache")
    args = ap.parse_args()
    fetch(args.imdb_dir)

    plays = read_csv("watch_history.csv")
    shows_csv = read_csv("shows.csv")
    my_ratings = read_csv("my_ratings.csv")
    recs_csv = read_csv("recommendations.csv")
    also_csv = read_csv("also_watched.csv")
    quiz_csv = read_csv("quiz_answers.csv")
    finished = {r["imdb_id"] for r in read_csv("finished_shows.csv") if nn(r.get("imdb_id"))}
    finished_titles = {norm(r["title"]) for r in read_csv("finished_shows.csv")}
    if not plays:
        sys.exit("data/watch_history.csv is empty or missing")

    show_ids = {s["imdb_id"] for s in shows_csv if s["imdb_id"]}
    show_ids |= {p["show_imdb_id"] for p in plays if p["show_imdb_id"]}
    movie_ids = {p["imdb_id"] for p in plays if p["type"] == "movie" and p["imdb_id"]}

    # Answers from the page's "Have I seen it?" section; the latest answer per title wins.
    quiz_latest = {}
    for r in quiz_csv:
        if nn(r.get("imdb_id")):
            quiz_latest[r["imdb_id"]] = r
    # An "undo" from the page withdraws the answer before it.
    quiz_latest = {k: v for k, v in quiz_latest.items() if v.get("answer") in ("seen", "not_seen")}
    quiz_seen = [r for r in quiz_latest.values() if r.get("answer") == "seen"]
    # Series seen outside the synced history: their episodes give an estimated watch time.
    seen_show_ids = {r["imdb_id"] for r in also_csv if nn(r.get("imdb_id")) and r.get("type") == "show"}
    seen_show_ids |= {r["imdb_id"] for r in quiz_seen if r.get("type") == "show"}
    seen_show_eps = collections.defaultdict(list)

    # ---- 1. every episode of every show watched ----
    log("Reading title.episode ...")
    episodes_by_show = collections.defaultdict(list)       # show tconst -> [(tconst, season, ep)]
    ep_lookup = {}                                          # (show, season, ep) -> tconst
    for row in tsv(args.imdb_dir / "title.episode.tsv.gz"):
        parent = row["parentTconst"]
        if parent in show_ids:
            s, e = to_int(row["seasonNumber"]), to_int(row["episodeNumber"])
            episodes_by_show[parent].append((row["tconst"], s, e))
            if s is not None and e is not None:
                ep_lookup[(parent, s, e)] = row["tconst"]
        elif parent in seen_show_ids:
            if (to_int(row["seasonNumber"]) or 0) > 0:
                seen_show_eps[parent].append(row["tconst"])

    # Fill in episode IDs that Trakt didn't have, by show + season + episode number.
    resolved = 0
    for p in plays:
        if p["type"] == "episode" and not p["imdb_id"] and p["show_imdb_id"]:
            t = ep_lookup.get((p["show_imdb_id"], to_int(p["season"]), to_int(p["episode"])))
            if t:
                p["imdb_id"] = t
                resolved += 1
    log(f"Resolved {resolved} missing episode IDs by season/episode number")

    all_episode_ids = {t for eps in episodes_by_show.values() for t, _, _ in eps}
    all_episode_ids |= {p["imdb_id"] for p in plays if p["type"] == "episode" and p["imdb_id"]}

    # ---- 2. ratings ----
    log("Reading title.ratings ...")
    ratings = {}
    for row in tsv(args.imdb_dir / "title.ratings.tsv.gz"):
        ratings[row["tconst"]] = (float(row["averageRating"]), int(row["numVotes"]))

    # ---- 3. titles, genres, runtimes; candidates for recommendations ----
    rec_keys = {}
    for r in recs_csv + also_csv:
        if not nn(r.get("imdb_id")):
            rec_keys.setdefault(norm(r["title"]), []).append(r)
    rec_candidates = collections.defaultdict(list)
    also_ids = {r["imdb_id"] for r in also_csv if nn(r.get("imdb_id"))}
    # Latest answer per title wins (an answer can be changed by answering again).
    also_ids |= {r["imdb_id"] for r in quiz_seen}
    wanted = show_ids | movie_ids | all_episode_ids | also_ids | {r["imdb_id"] for r in recs_csv if nn(r.get("imdb_id"))}
    basics = {}
    pool = {"movie": [], "show": []}
    log("Reading title.basics ...")
    for row in tsv(args.imdb_dir / "title.basics.tsv.gz"):
        t = row["tconst"]
        if t in wanted:
            basics[t] = row
        # Popular titles for the "Have I seen it?" quiz.
        tt = row["titleType"]
        if row.get("isAdult") == "0" and tt in ("movie", "tvSeries", "tvMiniSeries"):
            votes = ratings.get(t, (0, 0))[1]
            if votes >= (QUIZ_MIN_VOTES_MOVIE if tt == "movie" else QUIZ_MIN_VOTES_SHOW):
                pool["movie" if tt == "movie" else "show"].append(row)
        if rec_keys and row["titleType"] in SHOW_TYPES | MOVIE_TYPES:
            for k in {norm(row["primaryTitle"]), norm(row["originalTitle"])}:
                if k in rec_keys:
                    rec_candidates[k].append(row)

    def resolve(r):
        """IMDb ID for a row with title/year/type: its imdb_id, or the best title match."""
        t = nn(r.get("imdb_id"))
        if t:
            return t
        types = SHOW_TYPES if r["type"] == "show" else MOVIE_TYPES
        year = to_int(r.get("year"))
        cands = [c for c in rec_candidates.get(norm(r["title"]), []) if c["titleType"] in types]
        if year:
            close = [c for c in cands if to_int(c["startYear"]) and abs(to_int(c["startYear"]) - year) <= 1]
            cands = close or cands
        cands.sort(key=lambda c: ratings.get(c["tconst"], (0, 0))[1], reverse=True)
        if not cands:
            return None
        basics[cands[0]["tconst"]] = cands[0]
        return cands[0]["tconst"]

    def info(t):
        b = basics.get(t, {})
        rating, votes = ratings.get(t, (None, None))
        genres = nn(b.get("genres"))
        return {
            "rating": rating, "votes": votes,
            "genres": genres.split(",") if genres else [],
            "runtime": to_int(b.get("runtimeMinutes")),
            "startYear": to_int(b.get("startYear")), "endYear": to_int(b.get("endYear")),
            "imdbTitle": nn(b.get("primaryTitle")),
        }

    mine = {(r["imdb_id"] or norm(r["title"])): int(r["rating"]) for r in my_ratings}

    # ---- plays ----
    out_plays = []
    for p in plays:
        is_ep = p["type"] == "episode"
        i = info(p["imdb_id"]) if p["imdb_id"] else {"rating": None, "votes": None, "runtime": None}
        runtime = i["runtime"]
        if runtime is None:
            runtime = info(p["show_imdb_id"])["runtime"] if is_ep and p["show_imdb_id"] else None
        out_plays.append({
            "d": p["watched_at"] or None, "type": p["type"], "title": p["title"], "year": to_int(p["year"]),
            "s": to_int(p["season"]), "e": to_int(p["episode"]), "et": p["episode_title"] or None,
            "id": p["imdb_id"] or None, "sid": p["show_imdb_id"] or None,
            "r": i["rating"], "v": i["votes"], "min": runtime,
        })

    # ---- shows ----
    aired = {s["imdb_id"]: to_int(s["aired_episodes"]) for s in shows_csv if s["imdb_id"]}
    by_show = collections.defaultdict(list)
    for p in out_plays:
        if p["type"] == "episode":
            by_show[(p["title"], p["year"], p["sid"])].append(p)
    out_shows, episodes_out = [], {}
    for (title, year, sid), ps in by_show.items():
        i = info(sid) if sid else {"rating": None, "votes": None, "genres": [], "runtime": None, "startYear": None, "endYear": None}
        watched = {(p["s"], p["e"]) for p in ps}
        dates = sorted(p["d"] for p in ps if p["d"])
        ep_ratings = [p["r"] for p in ps if p["r"] is not None]
        eps = []
        if sid in episodes_by_show:
            for t, s, e in sorted(episodes_by_show[sid], key=lambda x: (x[1] if x[1] is not None else 999, x[2] if x[2] is not None else 999)):
                r, v = ratings.get(t, (None, None))
                b = basics.get(t, {})
                eps.append({"id": t, "s": s, "e": e, "title": nn(b.get("primaryTitle")), "r": r, "v": v,
                            "w": (s, e) in watched})
            episodes_out[sid] = eps
        # next unwatched episode that has aired (has a rating) after the last one you watched
        next_up = None
        if eps:
            last_watched = max(((p["s"] or 0, p["e"] or 0) for p in ps), default=(0, 0))
            for ep in eps:
                if ep["s"] and ep["s"] > 0 and ep["e"] and (ep["s"], ep["e"]) > last_watched and ep["r"] is not None:
                    next_up = {"s": ep["s"], "e": ep["e"], "title": ep["title"], "r": ep["r"]}
                    break
        aired_n = aired.get(sid) or (sum(1 for ep in eps if ep["r"] is not None and (ep["s"] or 0) > 0) or None)
        out_shows.append({
            "title": title, "year": year, "id": sid, "rating": i["rating"], "votes": i["votes"],
            "genres": i["genres"], "startYear": i["startYear"], "endYear": i["endYear"],
            "plays": len(ps), "watched": len(watched), "aired": aired_n,
            "minutes": sum(p["min"] or 0 for p in ps),
            "first": dates[0][:10] if dates else None, "last": dates[-1][:10] if dates else None,
            "avgEpisodeRating": round(sum(ep_ratings) / len(ep_ratings), 2) if ep_ratings else None,
            "myRating": mine.get(sid) or mine.get(norm(title)),
            "nextUp": next_up,
            "finished": sid in finished or norm(title) in finished_titles,
        })
    out_shows.sort(key=lambda s: -s["plays"])

    # ---- movies ----
    by_movie = collections.defaultdict(list)
    for p in out_plays:
        if p["type"] == "movie":
            by_movie[(p["title"], p["year"], p["id"])].append(p)
    out_movies = []
    for (title, year, mid), ps in by_movie.items():
        i = info(mid) if mid else {"rating": None, "votes": None, "genres": [], "runtime": None}
        dates = sorted(p["d"] for p in ps if p["d"])
        out_movies.append({
            "title": title, "year": year, "id": mid, "rating": i["rating"], "votes": i["votes"],
            "genres": i["genres"], "runtime": i["runtime"], "plays": len(ps),
            "last": dates[-1][:10] if dates else None,
            "myRating": mine.get(mid) or mine.get(norm(title)),
        })
    out_movies.sort(key=lambda m: m["last"] or "", reverse=True)

    # ---- your ratings (including titles rated but not in the history) ----
    out_my = []
    for r in my_ratings:
        i = info(r["imdb_id"]) if r["imdb_id"] else {"rating": None, "votes": None}
        out_my.append({"type": r["type"], "title": r["title"], "year": to_int(r["year"]), "id": r["imdb_id"] or None,
                       "mine": int(r["rating"]), "imdb": i["rating"]})

    def seen_minutes(t, kind, i):
        """Estimated watch time for a title seen outside the history: a movie's runtime, or every
        aired episode of a series (episodes with an IMDb rating) times the series' episode runtime."""
        if kind != "show":
            return i.get("runtime"), None
        aired_eps = [e for e in seen_show_eps.get(t, []) if e in ratings]
        if not aired_eps or not i.get("runtime"):
            return None, len(aired_eps) or None
        return len(aired_eps) * i["runtime"], len(aired_eps)

    # ---- titles watched outside the synced history (no dates) ----
    out_also = []
    for r in quiz_seen:
        t = r["imdb_id"]
        if t in show_ids | movie_ids:
            continue
        i = info(t)
        mins, eps_n = seen_minutes(t, r["type"], i)
        out_also.append({"title": r["title"], "year": to_int(r.get("year")), "type": r["type"], "id": t,
                         "note": "Marked seen on the site", "answeredAt": r.get("answered_at") or None,
                         "rating": i["rating"], "votes": i["votes"], "genres": i["genres"],
                         "minutes": mins, "episodes": eps_n})
    for r in also_csv:
        t = resolve(r)
        if t:
            also_ids.add(t)
        if t and t in show_ids | movie_ids:
            continue  # it has since shown up in the synced history
        i = info(t) if t else {"rating": None, "votes": None, "genres": [], "runtime": None}
        mins, eps_n = seen_minutes(t, r["type"], i) if t else (None, None)
        out_also.append({"title": r["title"], "year": to_int(r.get("year")), "type": r["type"], "id": t,
                         "note": r.get("note") or "", "rating": i["rating"], "votes": i["votes"], "genres": i["genres"],
                         "minutes": mins, "episodes": eps_n})

    # ---- recommendations ----
    watched_ids = show_ids | movie_ids | also_ids
    watched_titles = {norm(r["title"]) for r in also_csv}
    out_recs, problems = [], []
    for r in recs_csv:
        t = resolve(r)
        if not t:
            problems.append(f"not found on IMDb: {r['title']} ({r.get('year')})")
        if (t and t in watched_ids) or norm(r["title"]) in watched_titles:
            problems.append(f"already watched, skipped: {r['title']}")
            continue
        i = info(t) if t else {"rating": None, "votes": None, "genres": [], "runtime": None, "startYear": None, "endYear": None}
        out_recs.append({
            "title": r["title"], "year": to_int(r.get("year")), "type": r["type"], "id": t,
            "because": r.get("because") or "", "why": r.get("why") or "",
            "rating": i["rating"], "votes": i["votes"], "genres": i["genres"], "runtime": i["runtime"],
            "endYear": i.get("endYear"),
        })
    for msg in problems:
        log("recommendations:", msg)

    # ---- pick up where you left off ----
    # Unfinished, well-rated shows that are still "live": watched in the past three years,
    # or at least halfway through. Shows sampled once years ago are left out.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1095)).strftime("%Y-%m-%d")
    cont = [s for s in out_shows if s["nextUp"] and s["aired"] and s["watched"] >= 2 and not s["finished"]
            and s["watched"] < s["aired"] and (s["rating"] or 0) >= 7.0
            and ((s["last"] or "") >= cutoff or s["watched"] / s["aired"] >= 0.5)]
    cont.sort(key=lambda s: (s["last"] or ""), reverse=True)

    dashboard = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plays": out_plays, "shows": out_shows, "movies": out_movies, "myRatings": out_my,
        "recommendations": out_recs, "alsoWatched": out_also,
        "quizAnswered": len(quiz_latest),
        "continueWatching": [{"title": s["title"], "id": s["id"], "watched": s["watched"], "aired": s["aired"],
                              "last": s["last"], "rating": s["rating"], "nextUp": s["nextUp"]} for s in cont],
    }
    with open(DATA / "dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, separators=(",", ":"))
    with open(DATA / "episodes.json", "w", encoding="utf-8") as f:
        json.dump(episodes_out, f, ensure_ascii=False, separators=(",", ":"))

    # ---- "Have I seen it?" pool: most-voted titles not watched, rated or answered yet ----
    known = show_ids | movie_ids | also_ids | set(quiz_latest) | {r["imdb_id"] for r in my_ratings if r["imdb_id"]}
    known_titles = {(norm(r["title"]), to_int(r.get("year"))) for r in my_ratings + also_csv}
    def pick(rows, n):
        rows = [r for r in rows if r["tconst"] not in known
                and (norm(r["primaryTitle"]), to_int(r["startYear"])) not in known_titles]
        rows.sort(key=lambda r: ratings[r["tconst"]][1], reverse=True)
        return rows[:n]
    movies_q, shows_q = pick(pool["movie"], QUIZ_POOL_MOVIES), pick(pool["show"], QUIZ_POOL_SHOWS)
    quiz = []
    while movies_q or shows_q:          # two movies, then one show
        for src, k in ((movies_q, 2), (shows_q, 1)):
            for _ in range(k):
                if src:
                    r = src.pop(0)
                    rating, votes = ratings[r["tconst"]]
                    genres = nn(r["genres"])
                    quiz.append({"id": r["tconst"], "title": r["primaryTitle"],
                                 "type": "movie" if r["titleType"] == "movie" else "show",
                                 "year": to_int(r["startYear"]), "endYear": to_int(r["endYear"]),
                                 "rating": rating, "votes": votes,
                                 "genres": genres.split(",") if genres else [],
                                 "runtime": to_int(r["runtimeMinutes"])})
    with open(DATA / "quiz.json", "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, separators=(",", ":"))
    log(f"Quiz: {len(quiz)} titles in the pool; {len(quiz_latest)} answered ({len(quiz_seen)} seen)")

    rated = sum(1 for p in out_plays if p["r"] is not None)
    log(f"Plays with an IMDb rating: {rated}/{len(out_plays)}; shows: {len(out_shows)}; movies: {len(out_movies)}; "
        f"recommendations: {len(out_recs)}; episodes listed: {sum(len(v) for v in episodes_out.values())}")


if __name__ == "__main__":
    main()
