# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and builds reproducible snapshot artifacts used by analytics and the hosted stats page.

## What this repository provides

- A crawler for Blogspot feed pages (`movie_scene_battle_analyzer/crawler.py`)
- A CLI entrypoint for ad-hoc exports (`python3 -m movie_scene_battle_analyzer`)
- Snapshot build/verification scripts for operational workflows (`scripts/`)
- A static stats page (`index.html`) that reads `data/site_stats.json`
- CI workflows that verify and refresh snapshot artifacts (`.github/workflows/`)

## Project structure

```text
movie_scene_battle_analyzer/
  __init__.py
  __main__.py
  cli.py
  crawler.py
  models.py
scripts/
  build_site_snapshot.py
  verify_site_snapshot.py
data/
  moviescenebattles_dataset.json
  site_stats.json
index.html
```

## Quick start

Prerequisites:
- Python 3.12+ recommended (matches CI)
- No third-party Python dependencies

Generate a dataset locally:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Generate deployable snapshot artifacts:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

## Public interfaces

### CLI (`movie_scene_battle_analyzer/cli.py`)

```bash
python3 -m movie_scene_battle_analyzer --help
```

Flags:
- `--max-posts` (default: `500`) - maximum posts to crawl
- `--include-content` (default: disabled) - include plain-text post body in `content_text`
- `--output` (default: `data/moviescenebattles_dataset.json`) - destination JSON path

Example:

```bash
python3 -m movie_scene_battle_analyzer \
  --max-posts 300 \
  --include-content \
  --output data/moviescenebattles_dataset.json
```

### Python API (`movie_scene_battle_analyzer/__init__.py`)

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

Key constraints from implementation:
- `max_posts` must be `> 0`
- `page_size` must be `> 0`
- Crawl stops early when the feed returns no entries or a partial page

## Data contracts

### `data/moviescenebattles_dataset.json`

Top-level keys:
- `site_title`
- `site_url`
- `posts` (array of normalized `BattlePost`)
- `stats` (`SiteStats` derived from `posts`)

`BattlePost` fields:
- `post_id`, `title`, `url`
- `published_at`, `updated_at` (ISO timestamps or `null`)
- `comment_count`, `categories`, `word_count`
- `content_text` (`null` unless `--include-content` is used)

`SiteStats` fields include:
- totals/averages (`total_posts`, `total_comments`, `average_*`)
- matchup signal (`posts_with_explicit_matchup`, title regex based)
- aggregates (`posts_by_year`, `top_categories`, `most_commented_posts`)
- timestamps (`last_post_update`, `crawl_completed_at`)

### `data/site_stats.json`

Built by `scripts/build_site_snapshot.py` as:

```json
{
  "site_title": "...",
  "site_url": "...",
  "generated_from_posts": 1000,
  "stats": { "...": "mirrors dataset.stats" }
}
```

`scripts/verify_site_snapshot.py` requires this payload to exactly match:
- dataset identity (`site_title`, `site_url`)
- `generated_from_posts == len(dataset.posts)`
- full `stats` object equality with `dataset.stats`

## Operational runbook

### Refresh snapshot artifacts locally

1. Rebuild:
   ```bash
   python3 scripts/build_site_snapshot.py
   ```
2. Verify consistency:
   ```bash
   python3 scripts/verify_site_snapshot.py
   ```
3. If verification fails, rebuild before committing any `data/` changes.

### CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - runs on pull requests to `main` and manual dispatch
  - validates shape + strict consistency of snapshot artifacts
- `.github/workflows/refresh-site-snapshot.yml`
  - runs on schedule (`20 6 * * *`) and manual dispatch
  - rebuilds artifacts, verifies output, then opens/updates an automated refresh PR

## Troubleshooting and common pitfalls

- **`max_posts must be greater than 0`**
  - Cause: invalid CLI/API input.
  - Fix: pass a positive `--max-posts` or `max_posts` value.

- **`site_stats.json is out of sync with moviescenebattles_dataset.json`**
  - Cause: one artifact changed without rebuilding both.
  - Fix: run `python3 scripts/build_site_snapshot.py` and re-run verification.

- **Crawl returns fewer posts than requested**
  - Cause: feed has no more entries or returns a partial page at current bounds.
  - Fix: expected behavior; inspect the generated dataset count and continue.

- **Network/timeout issues while crawling**
  - Cause: Blogspot feed request failed or timed out.
  - Fix: retry later or increase API timeout when calling `crawl_moviescenebattles(timeout=...)`.

## Notes

- Feed pagination uses Blogspot `start-index` and `max-results` parameters.
- Text extraction strips HTML and normalizes whitespace before `word_count` calculation.
- No third-party Python dependencies are required.
