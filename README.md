# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes Blogspot feed entries, and produces JSON artifacts used by downstream ranking and stats workflows.

## Scope

The current repository supports three operational paths:

1. Crawl Blogspot feed data into a normalized dataset.
2. Build a compact site-stats snapshot for the static UI.
3. Verify snapshot integrity locally and in CI.

No third-party Python dependencies are required.

## Architecture at a glance

```text
movie_scene_battle_analyzer/
  __main__.py         # python -m entrypoint
  cli.py              # CLI argument parsing + execution
  crawler.py          # feed fetch, parsing, normalization, aggregate stats
  models.py           # BattlePost/SiteStats/CrawlDataset dataclasses
scripts/
  build_site_snapshot.py   # writes dataset + site_stats payload
  verify_site_snapshot.py  # validates shape + strict payload consistency
index.html                 # static page reading data/site_stats.json
```

## Public interfaces

### CLI interface

Run a crawl and export a dataset:

```bash
python3 -m movie_scene_battle_analyzer \
  --max-posts 500 \
  --output data/moviescenebattles_dataset.json
```

Include extracted post body text:

```bash
python3 -m movie_scene_battle_analyzer --include-content
```

CLI flags (from `movie_scene_battle_analyzer/cli.py`):

- `--max-posts` (default `500`)
- `--include-content` (default off)
- `--output` (default `data/moviescenebattles_dataset.json`)

### Python interface

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

`crawl_moviescenebattles(...)` supports:

- `max_posts` (default `500`)
- `include_content` (default `False`)
- `page_size` (default `150`)
- `timeout` in seconds (default `30`)

### Data contract

Core dataclasses are defined in `movie_scene_battle_analyzer/models.py`:

- `BattlePost`
- `SiteStats`
- `CrawlDataset`

Key behavior from `crawler.py`:

- Feed pagination uses Blogspot `start-index` + `max-results`.
- Crawl stops when an empty page is returned or a page returns fewer entries than requested.
- `posts_with_explicit_matchup` counts titles matching `vs`, `vs.`, `versus`, or `v` (case-insensitive).
- `top_categories` is capped at 10 entries.
- `most_commented_posts` is capped at 5 entries.
- JSON output uses `json.dumps(..., default=str)`, so datetime values are serialized as strings.

## Snapshot runbook

### Build artifacts

```bash
python3 scripts/build_site_snapshot.py
```

This script:

- crawls with `max_posts=1000` and `include_content=False`
- writes `data/moviescenebattles_dataset.json`
- writes `data/site_stats.json` as:
  - `site_title`
  - `site_url`
  - `generated_from_posts`
  - `stats` (from `dataset.stats`)

### Verify artifacts

```bash
python3 scripts/verify_site_snapshot.py
```

Verification checks:

1. Both JSON files exist.
2. Required keys exist and have expected container types.
3. `data/site_stats.json` exactly matches the payload derived from `data/moviescenebattles_dataset.json`.

If out of sync, verification fails with:

```text
site_stats.json is out of sync with moviescenebattles_dataset.json.
Run: python3 scripts/build_site_snapshot.py
```

### CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - runs on PRs to `main` and manual dispatch
  - executes `python3 scripts/verify_site_snapshot.py`
- `.github/workflows/refresh-site-snapshot.yml`
  - runs on schedule (`20 6 * * *`) and manual dispatch
  - rebuilds artifacts, verifies them, then opens/updates an automated refresh PR

## Static stats page behavior

`index.html` fetches `data/site_stats.json` (`cache: "no-store"`) and renders:

- total posts
- matchup-style post count
- average comments/words per post
- top categories
- most-commented post highlights

Link rendering is protocol-restricted to `http`/`https` before opening in a new tab.

## Troubleshooting and common pitfalls

- `ValueError: max_posts must be greater than 0`  
  Use `max_posts > 0` when calling `crawl_moviescenebattles(...)`.

- `ValueError: page_size must be greater than 0`  
  Applies when using the Python API and overriding `page_size`.

- Snapshot verification fails as out-of-sync  
  Rebuild artifacts, then re-run verification:
  ```bash
  python3 scripts/build_site_snapshot.py
  python3 scripts/verify_site_snapshot.py
  ```

- Static page shows "Could not load stats snapshot."  
  Confirm `data/site_stats.json` exists in the served output path and is valid JSON.

- Large dataset artifacts unexpectedly  
  `--include-content` stores full extracted body text and increases output size; keep it off for routine snapshot refreshes.
