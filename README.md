# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes feed entries, and generates snapshot artifacts consumed by both data workflows and the hosted stats page.

## What this repository provides

- A crawler for Blogspot feed pages (`movie_scene_battle_analyzer/crawler.py`)
- Structured models for posts, aggregate metrics, and crawl datasets (`movie_scene_battle_analyzer/models.py`)
- Public CLI + Python entrypoints for crawling and JSON export
- Snapshot build/verify scripts for operational consistency
- A static `index.html` dashboard backed by `data/site_stats.json`
- CI workflows that verify snapshot integrity and automate refresh PRs

## Architecture map

```text
Blogspot feed (JSON)
  -> crawl_moviescenebattles()
  -> CrawlDataset(site_title, site_url, posts, stats)
  -> data/moviescenebattles_dataset.json
  -> scripts/build_site_snapshot.py derives data/site_stats.json
  -> index.html fetches data/site_stats.json for live stats
  -> scripts/verify_site_snapshot.py enforces file parity
```

## Project structure

```text
movie_scene_battle_analyzer/
  __init__.py          # Public exports
  __main__.py          # python -m entrypoint
  cli.py               # CLI argument parsing
  crawler.py           # Feed retrieval, normalization, stats building
  models.py            # BattlePost, SiteStats, CrawlDataset dataclasses
scripts/
  build_site_snapshot.py
  verify_site_snapshot.py
.github/workflows/
  refresh-site-snapshot.yml
  verify-site-snapshot.yml
```

## Public interfaces

### CLI

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Options:

- `--max-posts` (default: `500`): max posts to crawl; must be `> 0`
- `--include-content` (default: off): include normalized post body text in output
- `--output` (default: `data/moviescenebattles_dataset.json`): dataset path

### Python API

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Behavior/constraints:

- `crawl_moviescenebattles(max_posts, include_content, page_size=150, timeout=30)`
  - raises `ValueError` if `max_posts <= 0` or `page_size <= 0`
  - paginates Blogspot feed via `start-index` + `max-results`
- `save_dataset(dataset, output_path)` creates parent directories as needed

## Snapshot artifacts

### `data/moviescenebattles_dataset.json`

Canonical crawl output with top-level keys:

- `site_title`
- `site_url`
- `posts` (`BattlePost[]`)
- `stats` (`SiteStats`)

### `data/site_stats.json`

Dashboard payload written by `scripts/build_site_snapshot.py`:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats` (must exactly match `dataset["stats"]`)

## Operational runbook

### Refresh artifacts locally

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

`build_site_snapshot.py` currently crawls with:

- `max_posts=1000`
- `include_content=False`

This updates:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

### Preview the dashboard locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

The page reads `data/site_stats.json` using `fetch("data/site_stats.json")`.

### CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - runs on PRs targeting `main` and manual dispatch
  - executes `python3 scripts/verify_site_snapshot.py`
- `.github/workflows/refresh-site-snapshot.yml`
  - runs daily (`20 6 * * *`) and manual dispatch
  - rebuilds and verifies snapshot artifacts
  - opens/updates PRs from `ci/refresh-site-snapshot`

## Troubleshooting and common pitfalls

- **`ValueError: max_posts must be greater than 0`**
  - fix CLI/API arguments to use positive values.
- **`site_stats.json is out of sync ...` during verification**
  - run `python3 scripts/build_site_snapshot.py`, then re-run verifier.
  - avoid manually editing `data/site_stats.json`; it is derived.
- **Dashboard shows "Could not load stats snapshot."**
  - confirm `data/site_stats.json` exists at repository root and server serves static files from the repo root.
- **Unexpected artifact diffs on refresh**
  - `stats.crawl_completed_at` is generated at crawl time, so each rebuild can legitimately change snapshot output.

## Notes

- No third-party dependencies are required.
- Datetime values are serialized as strings (`json.dumps(..., default=str)`), so downstream consumers should parse timestamps defensively.
