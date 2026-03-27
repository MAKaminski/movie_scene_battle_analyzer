# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and builds reproducible snapshot artifacts for analytics and ranking workflows.

## Intent

- Produce a consistent crawl dataset (`moviescenebattles_dataset.json`) for downstream consumers.
- Produce a lightweight stats payload (`site_stats.json`) for the hosted stats page.
- Keep snapshot generation deterministic and verifiable in CI.

## Architecture at a glance

```text
movie_scene_battle_analyzer/
  __init__.py            # Public exports
  __main__.py            # python -m entrypoint
  cli.py                 # CLI flags and output handling
  crawler.py             # Feed pagination, normalization, aggregate stats
  models.py              # BattlePost/SiteStats/CrawlDataset dataclasses
scripts/
  build_site_snapshot.py # Regenerates both JSON artifacts
  verify_site_snapshot.py# Validates artifact shape + sync
index.html               # Reads data/site_stats.json at runtime
```

## Public interfaces

### CLI

```bash
python3 -m movie_scene_battle_analyzer \
  --max-posts 500 \
  --output data/moviescenebattles_dataset.json
```

Flags:

- `--max-posts` (int, default `500`): upper bound on crawled posts.
- `--include-content` (flag): stores extracted post text in `content_text`.
- `--output` (path, default `data/moviescenebattles_dataset.json`): dataset target path.

### Python API

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(
    max_posts=300,
    include_content=False,
)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

`crawl_moviescenebattles` also supports:

- `page_size` (default `150`) for feed request pagination.
- `timeout` seconds (default `30`) for each feed request.

## Data model summary

### `BattlePost`

Normalized post fields: `post_id`, `title`, `url`, `published_at`, `updated_at`,
`comment_count`, `categories`, `word_count`, `content_text`.

### `SiteStats`

Aggregate metrics derived from crawled posts:

- volume: `total_posts`, `total_comments`
- averages: `average_comments_per_post`, `average_words_per_post`
- matchup signal: `posts_with_explicit_matchup` (title regex for `vs`, `v`, `versus`)
- distributions/highlights: `posts_by_year`, `top_categories`, `most_commented_posts`
- timestamps: `last_post_update`, `crawl_completed_at`

### `CrawlDataset`

Top-level payload: `site_title`, `site_url`, `posts`, `stats`.

## Snapshot workflow (developer runbook)

### 1) Rebuild artifacts

```bash
python3 scripts/build_site_snapshot.py
```

What it does:

- crawls up to 1000 posts (`include_content=False`)
- writes `data/moviescenebattles_dataset.json`
- writes `data/site_stats.json` with:
  - `site_title`
  - `site_url`
  - `generated_from_posts`
  - `stats` (copied from dataset stats)

### 2) Verify artifact consistency

```bash
python3 scripts/verify_site_snapshot.py
```

Verification checks:

- required keys exist in both JSON files
- `data/site_stats.json` is exactly in sync with dataset-derived expected payload

## CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - triggers on PRs to `main` and manual dispatch
  - runs `python3 scripts/verify_site_snapshot.py`
- `.github/workflows/refresh-site-snapshot.yml`
  - runs on schedule and manual dispatch
  - rebuilds and verifies artifacts
  - opens/updates an automated refresh PR

## Hosted stats page behavior

`index.html` fetches `data/site_stats.json` with `cache: "no-store"` and renders:

- cards: total posts, matchup-style titles, average comments, average words
- lists: top 10 categories and top 5 most-commented posts

Safety behavior:

- post links are rendered only when URL protocol resolves to `http:` or `https:`
- fetch or parsing failure shows an inline error state in the hero panel

## Troubleshooting and pitfalls

- `ValueError: max_posts must be greater than 0`
  - pass a positive `--max-posts` or `max_posts` value.
- `ValueError: page_size must be greater than 0`
  - only applies when calling Python API with custom `page_size`.
- `site_stats.json is out of sync...`
  - run:
    1. `python3 scripts/build_site_snapshot.py`
    2. `python3 scripts/verify_site_snapshot.py`
- Missing links in the highlights panel
  - expected when a post URL is empty or fails safe URL validation in `index.html`.
- Network/timeout failures during crawl
  - increase `timeout` when using Python API (default is 30 seconds per request).

## Constraints

- Feed source is Blogspot pagination (`start-index`, `max-results`) via JSON feed API.
- Datetimes are serialized as strings in output JSON (`default=str`).
- No third-party runtime dependencies are required.
