# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes feed entries, and produces JSON snapshots used by analytics and the hosted stats page.

## Intent and architecture

The codebase has one primary workflow:

1. Crawl Blogspot feed entries into a normalized dataset.
2. Compute aggregate site stats from crawled posts.
3. Publish two JSON artifacts consumed by `index.html`.
4. Verify artifact consistency in CI before merge.

### Subsystems and codepaths

| Subsystem | Codepath | Responsibility |
| --- | --- | --- |
| Crawl + normalization | `movie_scene_battle_analyzer/crawler.py` | Fetches paginated Blogspot feed JSON and converts entries to `BattlePost` |
| Data contracts | `movie_scene_battle_analyzer/models.py` | Defines `BattlePost`, `SiteStats`, `CrawlDataset`, and nested stat types |
| Public CLI | `movie_scene_battle_analyzer/cli.py`, `movie_scene_battle_analyzer/__main__.py` | Runs crawl and writes dataset JSON |
| Snapshot build runbook | `scripts/build_site_snapshot.py` | Regenerates `data/moviescenebattles_dataset.json` and `data/site_stats.json` |
| Snapshot verification | `scripts/verify_site_snapshot.py` | Validates required keys and exact dataset-to-site-stats consistency |
| Hosted dashboard | `index.html` | Fetches `data/site_stats.json` and renders summary cards + lists |

## Public interfaces

### CLI

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Flags:

- `--max-posts` (default `500`): maximum number of posts to crawl
- `--include-content` (off by default): include normalized post body text in `content_text`
- `--output` (default `data/moviescenebattles_dataset.json`): output file path

Constraints enforced by code:

- `max_posts` must be greater than `0`
- crawler pagination uses Blogspot `start-index` + `max-results`

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

`crawl_moviescenebattles(...)` returns a `CrawlDataset` with:

- `site_title`, `site_url`
- `posts: list[BattlePost]`
- `stats: SiteStats`

## Artifact contracts

### `data/moviescenebattles_dataset.json`

Top-level keys required by `scripts/verify_site_snapshot.py`:

- `site_title`
- `site_url`
- `posts` (must be a list)
- `stats` (must be an object)

### `data/site_stats.json`

Top-level keys required by `scripts/verify_site_snapshot.py`:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats` (must be an object)

`site_stats.json` is expected to exactly match:

- site metadata from the dataset
- `generated_from_posts == len(dataset["posts"])`
- `stats == dataset["stats"]`

## Operational runbooks

### Refresh snapshot artifacts locally

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Expected outputs:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`
- `Snapshot validation passed.` from verify script

### Verify only (for pre-commit or CI parity)

```bash
python3 scripts/verify_site_snapshot.py
```

## CI workflows

### `.github/workflows/verify-site-snapshot.yml`

- Triggers: pull requests targeting `main`, plus manual dispatch
- Runs: `python3 scripts/verify_site_snapshot.py`

### `.github/workflows/refresh-site-snapshot.yml`

- Triggers: scheduled cron `20 6 * * *` (UTC) and manual dispatch
- Steps:
  1. Rebuild artifacts via `scripts/build_site_snapshot.py`
  2. Verify artifacts via `scripts/verify_site_snapshot.py`
  3. Open/update automated refresh PR via `peter-evans/create-pull-request`

## Hosted stats page behavior

`index.html` fetches `data/site_stats.json` with `cache: "no-store"` and renders:

- Total posts
- Explicit matchup-style title count
- Average comments per post
- Average words per post
- Top categories
- Most-commented post highlights

When rendering highlight links, the page only allows `http`/`https` URLs (`safeUrl(...)`), and falls back to plain text when a URL is invalid.

## Setup and troubleshooting

### Setup

- No third-party Python dependencies are required.
- CI uses Python `3.12`; local development should use a modern Python 3 version compatible with type-union syntax (`|`).

### Common issues

#### `site_stats.json is out of sync with moviescenebattles_dataset.json`

Cause: one artifact was edited or regenerated without the other.

Fix:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Commit both JSON artifacts together.

#### `Missing required file: data/...json`

Cause: snapshot artifacts were not generated locally.

Fix: run `python3 scripts/build_site_snapshot.py`.

#### Crawl returns fewer posts than `--max-posts`

Expected when the feed has fewer entries than requested or pagination is exhausted.

#### Dataset file grows unexpectedly

If `--include-content` is enabled, every post stores normalized body text (`content_text`), which increases artifact size.
