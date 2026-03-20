# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and computes ranking-friendly site stats so movie matchups can be explored and compared with confidence.

## What this tool does

- Crawls Blogspot feed pages from `https://moviescenebattles.blogspot.com`
- Normalizes each post into a structured `BattlePost` record
- Builds aggregate `SiteStats` (comments, category leaders, yearly posting trends, etc.)
- Exports all data to JSON for downstream ranking, analytics, or product features

## Project structure

```text
movie_scene_battle_analyzer/
  __init__.py
  __main__.py
  cli.py
  crawler.py
  models.py
```

Additional operational components:

```text
scripts/
  build_site_snapshot.py      # rebuilds dataset + site_stats payload
  verify_site_snapshot.py     # schema + consistency checks between artifacts
.github/workflows/
  verify-site-snapshot.yml    # validates artifacts on PRs to main
  refresh-site-snapshot.yml   # scheduled/manual artifact refresh + PR automation
```

## Architecture and data flow

1. `crawl_moviescenebattles(...)` in `crawler.py` pages through the Blogspot feed (`start-index`, `max-results`) and normalizes each entry into `BattlePost`.
2. `_build_stats(...)` derives site-level aggregates (`SiteStats`) from the normalized post list.
3. `save_dataset(...)` writes a full `CrawlDataset` to `data/moviescenebattles_dataset.json`.
4. `scripts/build_site_snapshot.py` rebuilds the dataset and writes `data/site_stats.json` with this shape:
   - `site_title`
   - `site_url`
   - `generated_from_posts`
   - `stats` (mirrors dataset `stats`)
5. `scripts/verify_site_snapshot.py` validates required keys/types and enforces that `site_stats.json` is exactly derived from the dataset.

## Core data structures

### `BattlePost`
Stores one crawlable matchup post:
- `post_id`
- `title`
- `url`
- `published_at`
- `updated_at`
- `comment_count`
- `categories`
- `word_count`
- `content_text` (optional)

### `SiteStats`
Stores aggregate website metrics:
- `total_posts`
- `total_comments`
- `average_comments_per_post`
- `average_words_per_post`
- `posts_with_explicit_matchup`
- `posts_by_year`
- `top_categories`
- `most_commented_posts`
- `last_post_update`
- `crawl_completed_at`

### `CrawlDataset`
Stores:
- site metadata (`site_title`, `site_url`)
- all normalized posts
- computed aggregate stats

## Usage

### Run from CLI

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Optional:

```bash
python3 -m movie_scene_battle_analyzer --include-content
```

CLI defaults and constraints:

- `--max-posts` default: `500`
- `--output` default: `data/moviescenebattles_dataset.json`
- `--include-content` default: disabled (stores `content_text=None` for posts)
- `max_posts` must be greater than `0` (`ValueError` otherwise)

### Use in Python

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Public interface exported by `movie_scene_battle_analyzer`:

- Data models: `BattlePost`, `CategoryCount`, `PostHighlight`, `SiteStats`, `CrawlDataset`
- Functions:
  - `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30)`
  - `save_dataset(dataset, output_path)`

Function constraints/pitfalls:

- `max_posts <= 0` raises `ValueError`
- `page_size <= 0` raises `ValueError`
- Crawling is network-bound to `https://moviescenebattles.blogspot.com`; transient HTTP/network errors surface from `urllib`
- `--include-content` increases output size because full post text is retained

## Hosted stats page

This repository now includes a deployable `index.html` page that reads live snapshot data from:

- `data/site_stats.json`

To refresh both the full dataset and website stats payload before deploy:

```bash
python3 scripts/build_site_snapshot.py
```

This writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

## CI automation

This repo includes GitHub Actions to handle the refresh process:

- `.github/workflows/verify-site-snapshot.yml`
  - Triggers: PRs to `main`, manual dispatch
  - Runtime: Python `3.12`
  - Runs `python3 scripts/verify_site_snapshot.py`
  - Enforces required artifact shape and dataset/site_stats consistency
- `.github/workflows/refresh-site-snapshot.yml`
  - Triggers: schedule `20 6 * * *` (UTC), manual dispatch
  - Runtime: Python `3.12`
  - Runs:
    1. `python3 scripts/build_site_snapshot.py`
    2. `python3 scripts/verify_site_snapshot.py`
    3. `peter-evans/create-pull-request@v7` to open/update branch `ci/refresh-site-snapshot`

## Snapshot operations runbook

### Refresh artifacts locally

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Expected output:

- `build_site_snapshot.py`: `Wrote data/moviescenebattles_dataset.json and data/site_stats.json`
- `verify_site_snapshot.py`: `Snapshot validation passed.`

### Troubleshoot validation failures

If verification fails with:

```text
site_stats.json is out of sync with moviescenebattles_dataset.json.
Run: python3 scripts/build_site_snapshot.py
```

Use this sequence:

1. Rebuild artifacts: `python3 scripts/build_site_snapshot.py`
2. Re-run verification: `python3 scripts/verify_site_snapshot.py`
3. Commit both files together (`data/moviescenebattles_dataset.json` and `data/site_stats.json`) to keep CI green.

### Common pitfalls

- Regenerating only one artifact causes CI mismatch errors.
- Non-positive `--max-posts` values fail fast in crawler input validation.
- Large crawls with `--include-content` can significantly increase JSON size.
- Network instability during crawling may require rerunning the snapshot build.

## Engaging Product Updates (Integrity-First Edition)

These updates are designed to make the experience more fun while preserving the core mission: **let people rank movie scenes against one another fairly**.

### Achievements to highlight

1. **Reliable crawl + structured dataset**
   - We now convert raw Blogspot entries into a clean, reusable battle dataset.
2. **Transparent ranking context**
   - Category, comments, and publication trends are captured so users can understand *why* scenes perform well.
3. **Repeatable exports**
   - Snapshots can be generated again at any time, keeping rankings fresh and auditable.

### Fun user-facing features (without compromising ranking integrity)

1. **Daily Head-to-Head**
   - Users vote on one curated scene battle per day.
   - Votes count separately from canonical rank until moderation checks pass.
2. **Streaks for thoughtful voting**
   - Reward consistency (e.g., 7-day vote streak) rather than vote volume spam.
3. **Category Clash mode**
   - Filter battles by themes (hero showdown, final act, best monologue) and compare category leaders.
4. **Comment Power Meter**
   - Show which battles generated the strongest discussion while keeping rank calculations transparent.
5. **Debate Cards**
   - One-click shareable cards with matchup title, current rank delta, and comment highlights.

## Ranking integrity principles

- Keep source crawl data immutable once snapshotted
- Store vote events separately from base crawl stats
- Version ranking formula changes so historical comparisons stay valid
- Surface confidence indicators when sample sizes are small

## Notes

- Crawler uses Blogspot feed pagination (`start-index`, `max-results`)
- No third-party dependencies are required
