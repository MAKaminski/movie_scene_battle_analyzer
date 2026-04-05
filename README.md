# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes posts, and generates snapshot artifacts used by analytics and the hosted stats page.

## Quick start

### Prerequisites

- Python 3.12+ (used in CI workflows)
- No third-party Python dependencies

### Build and verify snapshot artifacts

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

This refreshes and validates:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

## Architecture overview

### Core codepaths

- `movie_scene_battle_analyzer/crawler.py`
  - Fetches Blogspot feed pages (`start-index`, `max-results`)
  - Converts feed entries into `BattlePost`
  - Builds aggregate `SiteStats`
- `movie_scene_battle_analyzer/models.py`
  - Dataclasses for `BattlePost`, `SiteStats`, `CrawlDataset`
- `movie_scene_battle_analyzer/cli.py`
  - CLI wrapper around `crawl_moviescenebattles(...)` + `save_dataset(...)`
- `scripts/build_site_snapshot.py`
  - Generates both dataset and stats payload used by the site
- `scripts/verify_site_snapshot.py`
  - Validates required shape and strict consistency between both JSON artifacts
- `index.html`
  - Reads `data/site_stats.json` at runtime and renders dashboard cards/lists

### Data flow

1. Crawl posts from Blogspot feed into in-memory `CrawlDataset`
2. Save full dataset to `data/moviescenebattles_dataset.json`
3. Derive site payload (`generated_from_posts` + `stats`) to `data/site_stats.json`
4. Verify `site_stats.json` exactly matches expected payload from dataset
5. Serve `index.html`, which fetches `data/site_stats.json`

## Public interfaces

### CLI

```bash
python3 -m movie_scene_battle_analyzer \
  --max-posts 500 \
  --output data/moviescenebattles_dataset.json
```

Options:

- `--max-posts` (int, default `500`): maximum posts to crawl
- `--include-content` (flag): include normalized `content_text` in each post
- `--output` (path, default `data/moviescenebattles_dataset.json`): output dataset path

### Python API

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(
    max_posts=300,
    include_content=False,
    page_size=150,
    timeout=30,
)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Constraints enforced by code:

- `max_posts > 0`
- `page_size > 0`

### Snapshot payload contract

`scripts/verify_site_snapshot.py` expects:

- Dataset keys: `site_title`, `site_url`, `posts`, `stats`
- Site stats keys: `site_title`, `site_url`, `generated_from_posts`, `stats`
- `site_stats.json` content to exactly equal:
  - `site_title`: dataset title
  - `site_url`: dataset URL
  - `generated_from_posts`: `len(dataset["posts"])`
  - `stats`: `dataset["stats"]`

## Operational runbooks

### Local refresh runbook

1. Rebuild artifacts:
   ```bash
   python3 scripts/build_site_snapshot.py
   ```
2. Verify consistency:
   ```bash
   python3 scripts/verify_site_snapshot.py
   ```
3. If publishing the dashboard, commit both JSON files together.

### Local dashboard preview runbook

`index.html` fetches `data/site_stats.json`, so run a local HTTP server from repo root:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html`.

### CI runbook

- `.github/workflows/verify-site-snapshot.yml`
  - Runs on PRs targeting `main` (and manual dispatch)
  - Executes `python3 scripts/verify_site_snapshot.py`
- `.github/workflows/refresh-site-snapshot.yml`
  - Runs on schedule (`20 6 * * *`) and manual dispatch
  - Rebuilds artifacts, verifies them, and opens/updates refresh PRs

## Troubleshooting and common pitfalls

### `site_stats.json is out of sync...`

Cause: `data/moviescenebattles_dataset.json` changed without regenerating `data/site_stats.json`.

Fix:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

### `Missing required file: data/...`

Cause: snapshot artifacts do not exist in your working copy.

Fix: run `python3 scripts/build_site_snapshot.py`.

### Dashboard shows "Could not load stats snapshot."

Common causes:

- `data/site_stats.json` is missing
- Repository opened directly via `file://` instead of an HTTP server
- Invalid JSON structure in `data/site_stats.json`

Fixes:

- Rebuild and verify snapshot files
- Serve with `python3 -m http.server`

## Notes

- Crawler user-agent: `movie-scene-battle-analyzer/1.0`
- Feed endpoint: `https://moviescenebattles.blogspot.com/feeds/posts/default`
