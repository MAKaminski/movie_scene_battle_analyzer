# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes Blogspot feed entries, and emits JSON snapshots used by both analytics and the deployable stats page (`index.html`).

## Quick start

Requirements:
- Python 3.12+ (CI uses 3.12)
- No third-party Python dependencies

Generate fresh snapshot artifacts:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Run the CLI directly:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

## Project layout

```text
movie_scene_battle_analyzer/
  __init__.py               # Public package exports
  __main__.py               # python -m entrypoint
  cli.py                    # CLI argument parsing + dataset write
  crawler.py                # Feed fetch, normalization, stats build
  models.py                 # Dataclasses for posts and stats
scripts/
  build_site_snapshot.py    # Builds dataset + site_stats payload
  verify_site_snapshot.py   # Validates snapshot shape and consistency
data/
  moviescenebattles_dataset.json
  site_stats.json
index.html                  # Static stats dashboard
```

## Public interfaces

### Python API

Exported from `movie_scene_battle_analyzer.__init__`:

- `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30) -> CrawlDataset`
- `save_dataset(dataset, output_path) -> None`
- Dataclasses: `BattlePost`, `CategoryCount`, `PostHighlight`, `SiteStats`, `CrawlDataset`

Important constraints from `crawler.py`:
- `max_posts` must be `> 0` (`ValueError` otherwise)
- `page_size` must be `> 0` (`ValueError` otherwise)
- Blogspot pagination uses `start-index` and `max-results`
- `include_content=False` stores `content_text=None` for each post

Example:

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

### CLI

`python3 -m movie_scene_battle_analyzer` supports:

- `--max-posts` (default: `500`)
- `--include-content` (stores extracted plain text per post)
- `--output` (default: `data/moviescenebattles_dataset.json`)

Example with full content capture:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 200 --include-content --output data/custom_snapshot.json
```

## Snapshot artifacts and contracts

### `data/moviescenebattles_dataset.json`

Produced by:
- CLI (`save_dataset`)
- `scripts/build_site_snapshot.py`

Top-level keys enforced by `scripts/verify_site_snapshot.py`:
- `site_title`
- `site_url`
- `posts` (list)
- `stats` (object)

### `data/site_stats.json`

Produced only by `scripts/build_site_snapshot.py`. Payload shape:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats` (exact copy of `dataset["stats"]`)

`scripts/verify_site_snapshot.py` compares this file against a reconstructed expected payload and fails if any value differs.

## Stats page behavior (`index.html`)

`index.html` fetches `data/site_stats.json` and renders:
- headline (`site_title`, `generated_from_posts`)
- summary cards (`total_posts`, `posts_with_explicit_matchup`, averages)
- top categories (up to 10)
- most-commented post links (up to 5)

Link handling is guarded by `safeUrl`:
- only `http` / `https` URLs are rendered as clickable links
- invalid or unsupported URLs are rendered as plain text

## Operations runbook

### Refresh snapshots manually

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Expected success output:
- build: `Wrote data/moviescenebattles_dataset.json and data/site_stats.json`
- verify: `Snapshot validation passed.`

### Validate deployable page locally

Serve from repository root and open the printed URL:

```bash
python3 -m http.server 8000
```

Then load `http://localhost:8000/index.html`.

## CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - triggers: PRs to `main`, manual dispatch
  - runs: `python3 scripts/verify_site_snapshot.py`

- `.github/workflows/refresh-site-snapshot.yml`
  - triggers: daily schedule (`20 6 * * *`), manual dispatch
  - runs build + verify
  - opens/updates PR branch `ci/refresh-site-snapshot` via `peter-evans/create-pull-request`

## Troubleshooting and common pitfalls

- `ValueError: max_posts must be greater than 0`
  - Cause: invalid crawler input
  - Fix: pass a positive `--max-posts` (CLI) or `max_posts` (API)

- `Missing required file: data/...json`
  - Cause: verification ran before build
  - Fix: run `python3 scripts/build_site_snapshot.py` first

- `site_stats.json is out of sync with moviescenebattles_dataset.json`
  - Cause: one artifact changed without regenerating the other
  - Fix: rebuild both artifacts with `scripts/build_site_snapshot.py`

- Stats page shows `Could not load stats snapshot.`
  - Cause: `data/site_stats.json` unavailable at runtime path
  - Fix: ensure the deployed/static server includes `data/site_stats.json` at `data/site_stats.json` relative to `index.html`
