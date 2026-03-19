# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes Blogspot feed entries, and produces JSON snapshot artifacts used by ranking and the hosted stats page.

## Repository overview

```text
movie_scene_battle_analyzer/
  cli.py                # CLI entrypoint (`python -m movie_scene_battle_analyzer`)
  crawler.py            # Feed fetching, normalization, aggregate stat derivation
  models.py             # BattlePost/SiteStats/CrawlDataset dataclasses
scripts/
  build_site_snapshot.py   # Writes dataset + site_stats payloads
  verify_site_snapshot.py  # Validates schema and strict payload consistency
index.html             # Static live stats page reading data/site_stats.json
```

## Setup

- Python 3.12 is the CI baseline (`actions/setup-python@v5`).
- No third-party runtime dependencies are required.
- Run commands from repository root (`/workspace` in CI/automation).

Quick sanity run:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 25 --output data/sample_dataset.json
```

## Public interfaces

### CLI

```bash
python3 -m movie_scene_battle_analyzer [--max-posts N] [--include-content] [--output PATH]
```

Options (from `movie_scene_battle_analyzer/cli.py`):

| Flag | Default | Notes |
| --- | --- | --- |
| `--max-posts` | `500` | Must be greater than `0` (`crawl_moviescenebattles` raises `ValueError` otherwise). |
| `--include-content` | `False` | Includes normalized post body text (`content_text`) in each post record. |
| `--output` | `data/moviescenebattles_dataset.json` | Output file path; parent directories are created automatically. |

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

Key behavior in `movie_scene_battle_analyzer/crawler.py`:

- Crawls paginated Blogspot feed pages using `start-index` and `max-results`.
- Stops when `max_posts` is reached or the feed returns no more entries.
- Derives aggregate stats (`SiteStats`) from normalized posts:
  - yearly posting counts
  - top 10 categories
  - top 5 most-commented posts
  - explicit-matchup count via title regex `\b(vs\.?|versus|v)\b`

## Snapshot artifacts

### `data/moviescenebattles_dataset.json`

Full crawl payload:

- `site_title`
- `site_url`
- `posts` (list of `BattlePost`)
- `stats` (`SiteStats`)

### `data/site_stats.json`

Lightweight payload consumed by `index.html`:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats`

`scripts/verify_site_snapshot.py` enforces that this file is an exact projection of the dataset file (not an independently edited artifact).

## Operational runbook

### Rebuild artifacts locally

```bash
python3 scripts/build_site_snapshot.py
```

This currently crawls up to `1000` posts (`include_content=False`) and writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

### Validate artifacts before commit/PR

```bash
python3 scripts/verify_site_snapshot.py
```

Validation checks:

1. Both files exist and are valid JSON.
2. Required top-level keys are present.
3. `site_stats.json` equals the expected payload derived from `moviescenebattles_dataset.json`.

### Preview the static stats page

`index.html` fetches `data/site_stats.json` with `fetch(...)`. Serve via HTTP (not `file://`):

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/index.html`.

## CI workflows

### Verify snapshot (`.github/workflows/verify-site-snapshot.yml`)

- Trigger: PRs targeting `main` and manual dispatch
- Runs `python3 scripts/verify_site_snapshot.py`

### Refresh snapshot (`.github/workflows/refresh-site-snapshot.yml`)

- Trigger: daily at `20 6 * * *` (UTC) and manual dispatch
- Rebuilds + verifies artifacts
- Uses `peter-evans/create-pull-request` with branch `ci/refresh-site-snapshot`

## Troubleshooting and common pitfalls

- **`ValueError: max_posts must be greater than 0`**
  - Cause: `max_posts <= 0` passed into crawler.
  - Fix: Use a positive integer.

- **`site_stats.json is out of sync ... Run: python3 scripts/build_site_snapshot.py`**
  - Cause: Dataset changed without regenerating derived stats payload.
  - Fix: Re-run `python3 scripts/build_site_snapshot.py`, then verify.

- **Stats page shows “Could not load stats snapshot.”**
  - Common causes:
    - Serving `index.html` via `file://` instead of HTTP.
    - Missing or invalid `data/site_stats.json`.
  - Fix: Serve from repo root with `python3 -m http.server` and rebuild snapshot if needed.

- **Unexpected `None` timestamps**
  - Cause: Feed timestamp not parseable by `datetime.fromisoformat`.
  - Impact: `published_at`/`updated_at` can be `null` in JSON.

## Constraints and assumptions

- The crawler depends on the Blogspot JSON feed shape (`feed.entry`, links, category tags).
- Matchup detection is title-heuristic-based; it does not inspect full post semantics.
- `save_dataset` serializes datetimes using `default=str`, so timestamp strings are emitted in JSON output.

For product-facing update notes, see `UPDATES.md`.
