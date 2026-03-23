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

### Use in Python

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

### Public interface notes and constraints

- CLI entrypoint: `python3 -m movie_scene_battle_analyzer`
  - `--max-posts` (default: `500`) must be greater than 0
  - `--include-content` includes normalized body text in `BattlePost.content_text`
  - `--output` defaults to `data/moviescenebattles_dataset.json`
- Library API:
  - `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30)`
  - `save_dataset(dataset, output_path)`
- The crawler fetches Blogspot feed pages via `start-index`/`max-results` pagination and stops when:
  - `max_posts` is reached, or
  - the feed returns no additional entries.

## Hosted stats page

The deployable `index.html` page reads `data/site_stats.json` and renders summary cards and highlight lists.

### Snapshot architecture and codepaths

- `scripts/build_site_snapshot.py`
  - Crawls up to 1000 posts with `include_content=False`
  - Writes:
    - `data/moviescenebattles_dataset.json`
    - `data/site_stats.json` (derived payload used by `index.html`)
- `scripts/verify_site_snapshot.py`
  - Asserts required keys exist in both artifacts
  - Reconstructs expected `site_stats.json` from dataset fields and requires exact equality
- `index.html`
  - Fetches `data/site_stats.json` and expects:
    - top-level keys: `site_title`, `site_url`, `generated_from_posts`, `stats`
    - nested metrics used in UI cards and lists (`total_posts`, `posts_with_explicit_matchup`, `average_*`, `top_categories`, `most_commented_posts`)

## CI automation

This repo includes GitHub Actions to handle the refresh process:

- `.github/workflows/verify-site-snapshot.yml`
  - Runs on PRs to `main`
  - Validates `data/moviescenebattles_dataset.json` and `data/site_stats.json` schema/consistency
- `.github/workflows/refresh-site-snapshot.yml`
  - Runs daily (scheduled) and on manual dispatch
  - Rebuilds artifacts, verifies consistency, and opens/updates an automated PR with refreshed data

## Snapshot operations runbook

Use this sequence for local snapshot updates:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

What each command guarantees:

1. `build_site_snapshot.py`
   - Regenerates both snapshot artifacts from the live blog feed.
2. `verify_site_snapshot.py`
   - Fails if either file is missing, malformed, or out of sync.
   - Enforces that `site_stats.json` exactly matches a payload derived from the dataset.

When changing snapshot-related code, keep these codepaths aligned:

- crawler/data model changes: `movie_scene_battle_analyzer/crawler.py`, `movie_scene_battle_analyzer/models.py`
- snapshot assembly: `scripts/build_site_snapshot.py`
- validation contract: `scripts/verify_site_snapshot.py`
- UI consumption: `index.html`
- CI orchestration: `.github/workflows/verify-site-snapshot.yml`, `.github/workflows/refresh-site-snapshot.yml`

## Troubleshooting

- **`site_stats.json is out of sync with moviescenebattles_dataset.json`**
  - Cause: the verifier compares exact payload equality.
  - Fix: run `python3 scripts/build_site_snapshot.py` and commit both files together.
- **`Missing required file: data/...`**
  - Cause: snapshot artifacts were not generated or not checked in.
  - Fix: regenerate with `build_site_snapshot.py`, then rerun `verify_site_snapshot.py`.
- **`max_posts must be greater than 0`**
  - Cause: invalid `--max-posts` input or API call argument.
  - Fix: use a positive integer for `max_posts`.
- **Stats page shows "Could not load stats snapshot."**
  - Cause: `data/site_stats.json` is missing or invalid JSON for the current deployment.
  - Fix: regenerate artifacts and verify locally before publishing.

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
