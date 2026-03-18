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

## Public interfaces and constraints

### CLI interface (`python3 -m movie_scene_battle_analyzer`)

Supported flags:

- `--max-posts` (default: `500`)
- `--include-content` (default: disabled)
- `--output` (default: `data/moviescenebattles_dataset.json`)

Validation constraints:

- `max_posts` must be greater than `0`
- internal `page_size` must be greater than `0`

### Python interface

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

`crawl_moviescenebattles(...)` returns `CrawlDataset` with:

- `site_title`
- `site_url`
- `posts` (`list[BattlePost]`)
- `stats` (`SiteStats`)

## Snapshot pipeline and operational runbook

The repository maintains two generated artifacts:

- `data/moviescenebattles_dataset.json` (full crawl payload)
- `data/site_stats.json` (stats-page payload derived from the dataset)

### Refresh artifacts locally

```bash
python3 scripts/build_site_snapshot.py
```

What this does (from source):

- crawls up to `1000` posts with `include_content=False`
- writes `data/moviescenebattles_dataset.json`
- rebuilds `data/site_stats.json` from `dataset.stats`

### Verify artifact consistency locally

```bash
python3 scripts/verify_site_snapshot.py
```

Verification guarantees:

- required top-level fields exist in both JSON files
- `site_stats.json` exactly matches the payload derived from `moviescenebattles_dataset.json`
- mismatch error includes the remediation command to rebuild snapshots

## Hosted stats page contract (`index.html`)

`index.html` fetches `data/site_stats.json` with `cache: "no-store"` and renders:

- total posts
- matchup-style titles
- average comments/words per post
- top categories
- most-commented post highlights

Payload contract expected by the page:

```json
{
  "site_title": "Movie Scene Battles",
  "site_url": "https://moviescenebattles.blogspot.com",
  "generated_from_posts": 1000,
  "stats": { "...": "SiteStats fields" }
}
```

URL safety constraint:

- highlight links are only rendered as clickable anchors for `http`/`https` URLs
- invalid URLs are rendered as plain text

## CI automation

### `.github/workflows/verify-site-snapshot.yml`

- Trigger: pull requests targeting `main`, plus manual dispatch
- Action: runs `python3 scripts/verify_site_snapshot.py`

### `.github/workflows/refresh-site-snapshot.yml`

- Trigger: scheduled daily at `06:20` UTC (`20 6 * * *`), plus manual dispatch
- Actions:
  1. rebuild snapshot artifacts
  2. verify consistency
  3. create/update PR from branch `ci/refresh-site-snapshot` with refreshed data files

## Troubleshooting and common pitfalls

- **Error:** `Missing required file: data/...json` during verification  
  **Fix:** run `python3 scripts/build_site_snapshot.py` before verifying.

- **Error:** `site_stats.json is out of sync with moviescenebattles_dataset.json`  
  **Fix:** do not hand-edit `data/site_stats.json`; regenerate both artifacts using the build script.

- **Unexpectedly large dataset output**  
  **Cause:** `scripts/build_site_snapshot.py` uses `max_posts=1000` (different from CLI default `500`).

- **Stats page shows load failure**  
  **Checks:** confirm `data/site_stats.json` exists, is valid JSON, and includes `stats` + `generated_from_posts`.

## Notes

- Crawler uses Blogspot feed pagination (`start-index`, `max-results`)
- No third-party dependencies are required
