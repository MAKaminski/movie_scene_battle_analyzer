"""
Tournament insights rebuilt from the crawl dataset.

Movie Scene Battles runs as a king-of-the-hill ladder: two scenes are posted,
readers vote, the winner returns the next day as champion and keeps defending
until it loses or reaches seven wins, at which point it retires to the Hall of
Fame. The blog never publishes the vote totals, but the succession of posts
leaks the result of every battle except the one currently open.

This module *re-joins* each post to its successor to recover winners, reigns,
retirements, upsets and posting cadence. Everything here is a pure function of
the dataset so the output can be regenerated and verified offline.
"""
from __future__ import annotations

import calendar
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

RETIREMENT_WINS = 7
TRAILING_WINDOW_MONTHS = 3
MOMENTUM_WINDOW_DAYS = 30
FUZZY_NAME_THRESHOLD = 0.6
POSTING_DAY_MIN_SHARE = 0.05
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_YEAR_SUFFIX = re.compile(r"\s+(\d{4})$")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _slug(value: str) -> str:
    return _NON_WORD.sub(" ", value.lower()).strip()


def _scene_key(name: str, movie: str) -> str:
    return f"{_slug(name)}|{_slug(movie)}"


def _same_scene(name_a: str, movie_a: str, name_b: str, movie_b: str) -> bool:
    """
    Match a scene across consecutive posts, tolerating the author's typos.

    Exact name+movie is the normal case. When the movie matches but the name
    drifts ("Pie in Your Facec", "Subway Fight" -> "Subway Battle") the movie
    anchors identity and a loose string similarity confirms it.
    """
    if _scene_key(name_a, movie_a) == _scene_key(name_b, movie_b):
        return True
    if _slug(movie_a) != _slug(movie_b):
        return False
    return SequenceMatcher(None, _slug(name_a), _slug(name_b)).ratio() >= FUZZY_NAME_THRESHOLD


def _month_label(day: date) -> str:
    return day.strftime("%Y-%m")


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _pct(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    # math.fsum is correctly rounded on every Python version; plain sum() changed
    # to compensated summation in 3.12, which can flip a value sitting on a
    # rounding boundary and make the committed snapshot fail verification.
    return round(math.fsum(values) / len(values), 2)


def _split_category(category: str) -> tuple[str, int | None]:
    match = _YEAR_SUFFIX.search(category)
    if not match:
        return category, None
    return category[: match.start()], int(match.group(1))


def _battles_from_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    battles = []
    for post in posts:
        if not post.get("champion") or not post.get("challenger"):
            continue
        if not post.get("categories"):
            # Skips the template post, which carries the matchup scaffold but no movies.
            continue
        published = _parse_dt(post.get("published_at"))
        if published is None:
            continue
        battles.append(
            {
                "post_id": post.get("post_id"),
                "title": post.get("title", ""),
                "url": post.get("url", ""),
                "published_at": published,
                "categories": list(post.get("categories") or []),
                "champion": post["champion"],
                "champion_movie": post.get("champion_movie") or "",
                "challenger": post["challenger"],
                "challenger_movie": post.get("challenger_movie") or "",
                "champion_wins_claimed": post.get("champion_wins_claimed"),
                "battle_type": post.get("battle_type") or "defense",
                "word_count": int(post.get("word_count") or 0),
            }
        )
    battles.sort(key=lambda item: (item["published_at"], item["post_id"] or ""))
    return battles


def _resolve_movie_years(battles: list[dict[str, Any]]) -> tuple[dict[str, int | None], int]:
    """Map body movie titles to the release year carried by the Blogspot labels."""
    years: dict[str, int | None] = {}
    unmatched = 0
    for battle in battles:
        labels = [_split_category(category) for category in battle["categories"]]
        label_slugs = {_slug(name): year for name, year in labels}
        sides = [battle["champion_movie"], battle["challenger_movie"]]
        leftover = dict(label_slugs)
        pending = []
        for movie in sides:
            slug = _slug(movie)
            if slug in leftover:
                years.setdefault(slug, leftover.pop(slug))
            else:
                pending.append(slug)
        if len(pending) == 1 and len(leftover) == 1:
            years.setdefault(pending[0], next(iter(leftover.values())))
        elif pending:
            unmatched += len(pending)
            for slug in pending:
                years.setdefault(slug, None)
    return years, unmatched


def _infer_winners(battles: list[dict[str, Any]]) -> int:
    """
    Decide each battle from its successor and return how many were decided.

    The scene that reappears as champion in the next post won; if the next post
    is a fresh matchup the champion just took its seventh win and retired.
    """
    for index, battle in enumerate(battles):
        battle["winner_side"] = None
        battle["retired_champion"] = False
        if index + 1 >= len(battles):
            continue
        nxt = battles[index + 1]
        if nxt["battle_type"] == "fresh":
            battle["winner_side"] = "champion"
            battle["retired_champion"] = True
            continue
        for side in ("champion", "challenger"):
            if _same_scene(nxt["champion"], nxt["champion_movie"], battle[side], battle[f"{side}_movie"]):
                battle["winner_side"] = side
                if _slug(nxt["champion"]) != _slug(battle[side]):
                    nxt["name_drift"] = {"from": battle[side], "to": nxt["champion"], "movie": nxt["champion_movie"]}
                break
    return sum(1 for battle in battles if battle["winner_side"])


def _build_reigns(battles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    reigns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    claims = {"checked": 0, "agree": 0}

    def open_reign(scene: str, movie: str, started: datetime) -> dict[str, Any]:
        return {
            "scene": scene,
            "movie": movie,
            "wins": 0,
            "defeated": [],
            "started_at": started,
            "ended_at": None,
            "status": "reigning",
            "dethroned_by": None,
            "battle_urls": [],
        }

    for battle in battles:
        if battle["battle_type"] == "defense":
            continuing = current is not None and _same_scene(
                current["scene"], current["movie"], battle["champion"], battle["champion_movie"]
            )
            if not continuing:
                if current is not None and current["status"] == "reigning":
                    current["status"] = "unresolved"
                    current["ended_at"] = battle["published_at"]
                    reigns.append(current)
                # A champion we never saw win (crawl window starts mid-reign, or a
                # break post): trust the site's own counter for the starting streak.
                current = open_reign(battle["champion"], battle["champion_movie"], battle["published_at"])
                current["wins"] = battle.get("champion_wins_claimed") or 0
            if battle.get("champion_wins_claimed") is not None:
                claims["checked"] += 1
                if battle["champion_wins_claimed"] == current["wins"]:
                    claims["agree"] += 1
                else:
                    battle["counter_mismatch"] = {
                        "claimed": battle["champion_wins_claimed"],
                        "inferred": current["wins"],
                    }
        else:
            if current is not None and current["status"] == "reigning":
                current["status"] = "unresolved"
                current["ended_at"] = battle["published_at"]
                reigns.append(current)
            # Fresh matchup: neither side has won yet, so the left side only
            # becomes a reign if it actually wins this battle.
            current = open_reign(battle["champion"], battle["champion_movie"], battle["published_at"])
            current["provisional"] = True

        battle["champion_wins_before"] = current["wins"]
        current["battle_urls"].append(battle["url"])
        winner = battle["winner_side"]
        if winner is None:
            continue
        if winner == "champion":
            current["wins"] += 1
            current.pop("provisional", None)
            current["defeated"].append(
                {
                    "scene": battle["challenger"],
                    "movie": battle["challenger_movie"],
                    "date": battle["published_at"].date().isoformat(),
                    "url": battle["url"],
                }
            )
            if battle["retired_champion"] or current["wins"] >= RETIREMENT_WINS:
                current["status"] = "retired"
                current["ended_at"] = battle["published_at"]
                reigns.append(current)
                current = None
        else:
            if not current.get("provisional"):
                current["status"] = "dethroned"
                current["ended_at"] = battle["published_at"]
                current["dethroned_by"] = {"scene": battle["challenger"], "movie": battle["challenger_movie"]}
                reigns.append(current)
            current = open_reign(battle["challenger"], battle["challenger_movie"], battle["published_at"])
            current["wins"] = 1
            current["defeated"].append(
                {
                    "scene": battle["champion"],
                    "movie": battle["champion_movie"],
                    "date": battle["published_at"].date().isoformat(),
                    "url": battle["url"],
                }
            )

    if current is not None:
        reigns.append(current)
    return reigns, claims


def _serialize_reign(reign: dict[str, Any], years: dict[str, int | None]) -> dict[str, Any]:
    started = reign["started_at"]
    ended = reign["ended_at"] or started
    return {
        "scene": reign["scene"],
        "movie": reign["movie"],
        "movie_year": years.get(_slug(reign["movie"])),
        "wins": reign["wins"],
        "status": reign["status"],
        "started_at": started.date().isoformat(),
        "ended_at": reign["ended_at"].date().isoformat() if reign["ended_at"] else None,
        "days_on_top": max(0, (ended.date() - started.date()).days),
        "dethroned_by": reign["dethroned_by"],
        "defeated": reign["defeated"],
        "first_battle_url": reign["battle_urls"][0] if reign["battle_urls"] else None,
    }


def _cadence(battles: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    per_month: Counter[str] = Counter(_month_label(b["published_at"].date()) for b in battles)
    if not per_month:
        return {"monthly": [], "next_month": None, "weekday": [], "hour_of_day": []}

    weekday_counts = Counter(b["published_at"].weekday() for b in battles)
    # Days of the week the site actually posts on (Sun-Thu in practice); the
    # partial-month projection paces by those, not by calendar days.
    posting_weekdays = {
        weekday for weekday, count in weekday_counts.items() if count / len(battles) >= POSTING_DAY_MIN_SHARE
    } or set(range(7))

    def posting_days(start: date, end: date) -> int:
        return sum(1 for offset in range((end - start).days + 1) if (start + timedelta(days=offset)).weekday() in posting_weekdays)

    first = min(b["published_at"].date() for b in battles).replace(day=1)
    months: list[dict[str, Any]] = []
    cursor = first
    current_month = as_of.replace(day=1)
    history: list[int] = []
    while cursor <= current_month:
        label = _month_label(cursor)
        actual = per_month.get(label, 0)
        window = history[-TRAILING_WINDOW_MONTHS:]
        estimate = round(sum(window) / len(window), 1) if window else None
        is_partial = cursor == current_month
        days_in_month = calendar.monthrange(cursor.year, cursor.month)[1]
        projected = None
        if is_partial and as_of.day < days_in_month:
            elapsed = posting_days(cursor, as_of)
            total = posting_days(cursor, cursor.replace(day=days_in_month))
            projected = round(actual / elapsed * total, 1) if elapsed else None
        months.append(
            {
                "month": label,
                "actual": actual,
                "estimate": estimate,
                "delta": round(actual - estimate, 1) if estimate is not None else None,
                "is_partial": is_partial,
                "projected": projected,
            }
        )
        if not is_partial:
            history.append(actual)
        cursor = _add_months(cursor, 1)

    window = history[-TRAILING_WINDOW_MONTHS:]
    next_month = {
        "month": _month_label(_add_months(current_month, 1)),
        "estimate": round(sum(window) / len(window), 1) if window else None,
        "basis": f"trailing {len(window)}-month average of completed months",
    }

    hour_counts = Counter(b["published_at"].hour for b in battles)
    full_months = [m for m in months if not m["is_partial"]]
    errors = [abs(m["delta"]) for m in full_months if m["delta"] is not None]
    return {
        "monthly": months,
        "next_month": next_month,
        "mean_absolute_error": _mean(errors),
        "posting_weekdays": [WEEKDAY_NAMES[index] for index in sorted(posting_weekdays)],
        "weekday": [
            {"day": WEEKDAY_NAMES[index], "battles": weekday_counts.get(index, 0)} for index in range(7)
        ],
        "hour_of_day": [
            {"hour": hour, "battles": hour_counts.get(hour, 0)} for hour in range(24) if hour_counts.get(hour)
        ],
        "busiest_hour": max(hour_counts.items(), key=lambda item: (item[1], -item[0]))[0],
        "share_in_busiest_hour": _pct(max(hour_counts.values()), len(battles)),
    }


def _movie_board(
    battles: list[dict[str, Any]], reigns: list[dict[str, Any]], years: dict[str, int | None]
) -> list[dict[str, Any]]:
    board: dict[str, dict[str, Any]] = {}

    def entry(movie: str) -> dict[str, Any]:
        slug = _slug(movie)
        if slug not in board:
            board[slug] = {
                "movie": movie,
                "year": years.get(slug),
                "scenes": set(),
                "battles": 0,
                "wins": 0,
                "losses": 0,
                "retired_scenes": 0,
            }
        return board[slug]

    for battle in battles:
        for side in ("champion", "challenger"):
            record = entry(battle[f"{side}_movie"])
            record["scenes"].add(battle[side])
            record["battles"] += 1
            if battle["winner_side"] == side:
                record["wins"] += 1
            elif battle["winner_side"]:
                record["losses"] += 1
    for reign in reigns:
        if reign["status"] == "retired":
            entry(reign["movie"])["retired_scenes"] += 1

    rows = []
    for record in board.values():
        decided = record["wins"] + record["losses"]
        rows.append(
            {
                "movie": record["movie"],
                "year": record["year"],
                "scenes": len(record["scenes"]),
                "battles": record["battles"],
                "wins": record["wins"],
                "losses": record["losses"],
                "win_rate": _pct(record["wins"], decided),
                "retired_scenes": record["retired_scenes"],
            }
        )
    rows.sort(key=lambda row: (-row["wins"], -row["battles"], row["movie"]))
    return rows


def _decade_board(movie_board: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decades: dict[str, dict[str, Any]] = {}
    for row in movie_board:
        if row["year"] is None:
            label = "unknown"
        else:
            label = f"{row['year'] // 10 * 10}s"
        bucket = decades.setdefault(
            label, {"decade": label, "movies": 0, "battles": 0, "wins": 0, "losses": 0}
        )
        bucket["movies"] += 1
        bucket["battles"] += row["battles"]
        bucket["wins"] += row["wins"]
        bucket["losses"] += row["losses"]
    rows = []
    for bucket in decades.values():
        bucket["win_rate"] = _pct(bucket["wins"], bucket["wins"] + bucket["losses"])
        rows.append(bucket)
    rows.sort(key=lambda row: (row["decade"] == "unknown", row["decade"]))
    return rows


def _streak_survival(reigns: list[dict[str, Any]], battles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Champion win rate at each rung of the ladder: does momentum exist?"""
    attempts: Counter[int] = Counter()
    holds: Counter[int] = Counter()
    for battle in battles:
        if battle["battle_type"] != "defense" or battle["winner_side"] is None:
            continue
        rung = battle.get("champion_wins_before", 0)
        attempts[rung] += 1
        if battle["winner_side"] == "champion":
            holds[rung] += 1
    rows = []
    for rung in sorted(attempts):
        rows.append(
            {
                "wins_before_battle": rung,
                "defenses": attempts[rung],
                "held": holds[rung],
                "hold_rate": _pct(holds[rung], attempts[rung]),
            }
        )
    return rows


def _momentum(battles: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    recent_start = as_of - timedelta(days=MOMENTUM_WINDOW_DAYS - 1)
    prior_start = recent_start - timedelta(days=MOMENTUM_WINDOW_DAYS)

    def window(start: date, end: date) -> dict[str, Any]:
        rows = [b for b in battles if start <= b["published_at"].date() <= end]
        decided = [b for b in rows if b["winner_side"] and b["battle_type"] == "defense"]
        upsets = [b for b in decided if b["winner_side"] == "challenger"]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "battles": len(rows),
            "decided_defenses": len(decided),
            "upsets": len(upsets),
            "upset_rate": _pct(len(upsets), len(decided)),
            "avg_words": _mean([b["word_count"] for b in rows]),
        }

    recent = window(recent_start, as_of)
    prior = window(prior_start, recent_start - timedelta(days=1))
    return {
        "window_days": MOMENTUM_WINDOW_DAYS,
        "recent": recent,
        "prior": prior,
        "battles_delta": recent["battles"] - prior["battles"],
        "upset_rate_delta": (
            round(recent["upset_rate"] - prior["upset_rate"], 1)
            if recent["upset_rate"] is not None and prior["upset_rate"] is not None
            else None
        ),
    }


def build_insights(dataset: dict[str, Any]) -> dict[str, Any]:
    """Compute the full insight payload from a crawl dataset dictionary."""
    posts = list(dataset.get("posts") or [])
    battles = _battles_from_posts(posts)
    non_battle_posts = [
        {"title": post.get("title", ""), "url": post.get("url", ""), "published_at": str(post.get("published_at") or "")}
        for post in posts
        if not (post.get("champion") and post.get("challenger") and post.get("categories"))
    ]
    non_battle_posts.sort(key=lambda row: row["published_at"])

    if not battles:
        return {
            "site_title": dataset.get("site_title"),
            "site_url": dataset.get("site_url"),
            "generated_from_posts": len(posts),
            "battles": 0,
            "non_battle_posts": non_battle_posts,
        }

    years, unmatched_movies = _resolve_movie_years(battles)
    decided = _infer_winners(battles)
    reigns, claims = _build_reigns(battles)
    as_of = max(b["published_at"] for b in battles).date()

    defenses = [b for b in battles if b["battle_type"] == "defense" and b["winner_side"]]
    upsets = [b for b in defenses if b["winner_side"] == "challenger"]
    fresh = [b for b in battles if b["battle_type"] == "fresh"]
    finished = [r for r in reigns if r["status"] in ("retired", "dethroned")]
    retired = [r for r in reigns if r["status"] == "retired"]
    scene_keys = {
        _scene_key(b[side], b[f"{side}_movie"]) for b in battles for side in ("champion", "challenger")
    }
    movie_board = _movie_board(battles, reigns, years)
    decade_board = _decade_board(movie_board)

    latest = battles[-1]
    current_reign = reigns[-1] if reigns and reigns[-1]["status"] == "reigning" else None
    giant_killers = sorted(
        (
            {
                "scene": b["challenger"],
                "movie": b["challenger_movie"],
                "beat": b["champion"],
                "beat_movie": b["champion_movie"],
                "champion_wins_before": b.get("champion_wins_before", 0),
                "date": b["published_at"].date().isoformat(),
                "url": b["url"],
            }
            for b in upsets
        ),
        key=lambda row: (-row["champion_wins_before"], row["date"]),
    )[:8]

    hall_of_fame_post = next(
        (post for post in posts if _slug(post.get("title", "")) == "hall of fame"), None
    )
    hall_of_fame_labels = sorted(hall_of_fame_post.get("categories") or []) if hall_of_fame_post else []

    reign_lengths = Counter(r["wins"] for r in finished)
    serialized_reigns = [_serialize_reign(r, years) for r in reigns]

    return {
        "site_title": dataset.get("site_title"),
        "site_url": dataset.get("site_url"),
        "generated_from_posts": len(posts),
        "as_of": as_of.isoformat(),
        "first_battle_at": battles[0]["published_at"].date().isoformat(),
        "retirement_wins": RETIREMENT_WINS,
        "summary": {
            "battles": len(battles),
            "decided_battles": decided,
            "pending_battles": len(battles) - decided,
            "defenses": len(defenses),
            "fresh_matchups": len(fresh),
            "upsets": len(upsets),
            "upset_rate": _pct(len(upsets), len(defenses)),
            "unique_scenes": len(scene_keys),
            "unique_movies": len(movie_board),
            "reigns": len(reigns),
            "finished_reigns": len(finished),
            "retired_scenes": len(retired),
            "average_reign_wins": _mean([r["wins"] for r in finished]),
            "median_reign_wins": (sorted(r["wins"] for r in finished)[len(finished) // 2] if finished else None),
            "average_words_per_battle": _mean([b["word_count"] for b in battles]),
            "days_active": (as_of - battles[0]["published_at"].date()).days + 1,
        },
        "data_quality": {
            "posts_total": len(posts),
            "battle_posts": len(battles),
            "non_battle_posts": len(non_battle_posts),
            "winners_inferred": decided,
            "winner_inference_rate": _pct(decided, len(battles)),
            "win_counter_checks": claims["checked"],
            "win_counter_agreement": claims["agree"],
            "win_counter_agreement_rate": _pct(claims["agree"], claims["checked"]),
            "movies_without_label_year": unmatched_movies,
            "name_drift": [
                {**b["name_drift"], "date": b["published_at"].date().isoformat(), "url": b["url"]}
                for b in battles
                if b.get("name_drift")
            ],
            "win_counter_mismatches": [
                {
                    "title": b["title"],
                    "url": b["url"],
                    "date": b["published_at"].date().isoformat(),
                    **b["counter_mismatch"],
                }
                for b in battles
                if b.get("counter_mismatch")
            ],
            "hall_of_fame_labels": hall_of_fame_labels,
            "hall_of_fame_label_count": len(hall_of_fame_labels),
            "retired_reigns_found": len(retired),
            "hall_of_fame_matches_page": (
                len(hall_of_fame_labels) == len(retired) if hall_of_fame_labels else None
            ),
        },
        "head_to_head": {
            "title": latest["title"],
            "url": latest["url"],
            "published_at": latest["published_at"].date().isoformat(),
            "battle_type": latest["battle_type"],
            "champion": latest["champion"],
            "champion_movie": latest["champion_movie"],
            "champion_movie_year": years.get(_slug(latest["champion_movie"])),
            "champion_wins": latest.get("champion_wins_before", 0),
            "challenger": latest["challenger"],
            "challenger_movie": latest["challenger_movie"],
            "challenger_movie_year": years.get(_slug(latest["challenger_movie"])),
            "decided": latest["winner_side"] is not None,
            "wins_to_retire": max(0, RETIREMENT_WINS - latest.get("champion_wins_before", 0)),
        },
        "current_reign": _serialize_reign(current_reign, years) if current_reign else None,
        "hall_of_fame": [_serialize_reign(r, years) for r in retired],
        "longest_reigns": sorted(
            serialized_reigns, key=lambda r: (-r["wins"], -r["days_on_top"], r["started_at"])
        )[:12],
        "reign_length_distribution": [
            {"wins": wins, "reigns": reign_lengths.get(wins, 0)} for wins in range(1, RETIREMENT_WINS + 1)
        ],
        "streak_survival": _streak_survival(reigns, battles),
        "giant_killers": giant_killers,
        "movie_leaderboard": movie_board[:15],
        "movie_count": len(movie_board),
        "decades": decade_board,
        "cadence": _cadence(battles, as_of),
        "momentum": _momentum(battles, as_of),
        "recent_battles": [
            {
                "title": b["title"],
                "url": b["url"],
                "date": b["published_at"].date().isoformat(),
                "champion": b["champion"],
                "champion_movie": b["champion_movie"],
                "challenger": b["challenger"],
                "challenger_movie": b["challenger_movie"],
                "champion_wins_before": b.get("champion_wins_before", 0),
                "winner": (
                    b["champion"] if b["winner_side"] == "champion"
                    else b["challenger"] if b["winner_side"] == "challenger"
                    else None
                ),
                "retired_champion": b["retired_champion"],
            }
            for b in reversed(battles[-15:])
        ],
        "non_battle_posts": non_battle_posts,
    }
