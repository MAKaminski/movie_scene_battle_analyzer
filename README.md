# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls
[Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data,
and produces repeatable snapshot artifacts for analytics and a deployable stats page.

## Overview

The codebase has three main responsibilities:

1. **Crawl** Blogspot feed pages and normalize entries into `BattlePost` records.
2. **Aggregate** site-level metrics (comments, categories, posting history, highlights).
3. **Publish** reproducible JSON artifacts consumed by `index.html` and CI workflows.

No third-party Python dependencies are required.

## Repository layout

```text
movie_scene_battle_analyzer/
  __init__.py              # public API exports
  __main__.py              # module entrypoint
  cli.py                   # CLI argument parsing + execution
  crawler.py               # feed fetching, normalization, stats aggregation
  models.py                # dataclasses for posts/stats/dataset
scripts/
  build_site_snapshot.py   # rebuilds both snapshot artifacts
  verify_site_snapshot.py  # validates shape + strict consistency
data/
  moviescenebattles_dataset.json
  site_stats.json
index.html                 # static stats page reading data/site_stats.json
```

## Public interfaces

### CLI

Run from repository root:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Available arguments:

- `--max-posts` (default: `500`): maximum number of feed entries to crawl.
- `--include-content` (default: disabled): includes normalized post body text in output.
- `--output` (default: `data/moviescenebattles_dataset.json`): output path for dataset JSON.

### Python API

Exported by `movie_scene_battle_analyzer.__init__`:

- `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30)`
- `save_dataset(dataset, output_path)`

Example:

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

## Data contracts

### `data/moviescenebattles_dataset.json`

Produced by the CLI and `scripts/build_site_snapshot.py` with shape:

- `site_title`
- `site_url`
- `posts`: list of `BattlePost`
- `stats`: `SiteStats`

`BattlePost` contains:
`post_id`, `title`, `url`, `published_at`, `updated_at`, `comment_count`,
`categories`, `word_count`, and optional `content_text`.

`SiteStats` contains:
`total_posts`, `total_comments`, `average_comments_per_post`,
`average_words_per_post`, `posts_with_explicit_matchup`, `posts_by_year`,
`top_categories`, `most_commented_posts`, `last_post_update`,
`crawl_completed_at`.

### `data/site_stats.json`

Produced by `scripts/build_site_snapshot.py` with shape:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats` (copied from dataset `stats`)

`scripts/verify_site_snapshot.py` enforces **exact equality** between:

- `data/site_stats.json`
- expected payload derived from `data/moviescenebattles_dataset.json`

## Operational runbook

### Refresh snapshot artifacts locally

```bash
python3 scripts/build_site_snapshot.py
```

This rebuilds:

- `data/moviescenebattles_dataset.json` (crawl with `max_posts=1000`)
- `data/site_stats.json`

### Verify snapshot consistency

```bash
python3 scripts/verify_site_snapshot.py
```

Expected success output:

```text
Snapshot validation passed.
```

### Preview the stats page

Serve the repository root and open `index.html` in a browser:

```bash
python3 -m http.server 8000
```

The page fetches `data/site_stats.json` and renders:

- totals and averages
- top categories (up to 10)
- most-commented highlights (up to 5)

## CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - Triggers on pull requests targeting `main` and manual dispatch.
  - Runs `python3 scripts/verify_site_snapshot.py`.
- `.github/workflows/refresh-site-snapshot.yml`
  - Triggers daily (`cron: 20 6 * * *`) and manual dispatch.
  - Rebuilds snapshots, verifies consistency, and creates/updates a PR from
    branch `ci/refresh-site-snapshot`.

## Troubleshooting and pitfalls

- **`site_stats.json is out of sync`**
  - Cause: `site_stats.json` does not match dataset-derived payload exactly.
  - Fix: run `python3 scripts/build_site_snapshot.py`, then re-run verify.
- **Crawler returns fewer posts than requested**
  - Cause: feed pagination ended before `max_posts`.
  - Behavior: crawler stops when no entries remain or a page is short.
- **`ValueError` for crawl parameters**
  - `max_posts` and `page_size` must both be greater than `0`.
- **Large output files**
  - `--include-content` stores post body text; keep disabled for lean snapshots
    unless content analysis is required.
