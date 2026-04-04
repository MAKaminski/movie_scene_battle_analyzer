# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and generates snapshot artifacts used by the site stats page.

## Intent and architecture

The repository keeps two things in sync:

1. **Crawl dataset** for analysis (`data/moviescenebattles_dataset.json`)
2. **Site stats payload** for the deployed page (`data/site_stats.json`)

### Main codepaths

```text
movie_scene_battle_analyzer/
  cli.py                  # CLI interface
  crawler.py              # feed pagination, post normalization, aggregate stats
  models.py               # BattlePost, SiteStats, CrawlDataset dataclasses
scripts/
  build_site_snapshot.py  # rebuilds both JSON artifacts
  verify_site_snapshot.py # validates required shape + exact sync
.github/workflows/
  verify-site-snapshot.yml  # PR gate for artifact consistency
  refresh-site-snapshot.yml # scheduled rebuild + automated refresh PR
index.html                  # reads data/site_stats.json at runtime
```

## Setup

### Requirements

- Python 3.12+ (CI target)
- No third-party Python dependencies

### Local bootstrap

```bash
python3 --version
python3 -m movie_scene_battle_analyzer --max-posts 100 --output data/moviescenebattles_dataset.json
```

## Public interfaces

### CLI (`python3 -m movie_scene_battle_analyzer`)

Supported flags (from `movie_scene_battle_analyzer/cli.py`):

- `--max-posts <int>`: max posts to crawl (default `500`)
- `--include-content`: include extracted post body text in `content_text`
- `--output <path>`: dataset output path (default `data/moviescenebattles_dataset.json`)

Example:

```bash
python3 -m movie_scene_battle_analyzer \
  --max-posts 300 \
  --include-content \
  --output data/moviescenebattles_dataset.json
```

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

Key constraints enforced in code:

- `max_posts > 0`
- `page_size > 0`
- Feed pagination uses Blogspot `start-index` + `max-results`

## Snapshot workflow runbook

### Rebuild artifacts

```bash
python3 scripts/build_site_snapshot.py
```

This script crawls up to 1000 posts and writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

`site_stats.json` is intentionally derived from `dataset.stats` plus:

- `site_title`
- `site_url`
- `generated_from_posts`

### Verify artifact integrity

```bash
python3 scripts/verify_site_snapshot.py
```

Verification checks:

- Required top-level keys exist in both files
- `dataset.posts` is a list, `stats` payloads are objects
- `data/site_stats.json` exactly matches the expected payload derived from
  `data/moviescenebattles_dataset.json`

If verification fails with an out-of-sync error, regenerate artifacts with:

```bash
python3 scripts/build_site_snapshot.py
```

### Preview stats page locally

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000` and confirm `index.html` loads `data/site_stats.json`.

## CI and automation behavior

### `verify-site-snapshot.yml`

- Triggers on pull requests targeting `main` (and manual dispatch)
- Runs `python3 scripts/verify_site_snapshot.py`
- Prevents merging inconsistent artifact updates

### `refresh-site-snapshot.yml`

- Runs on schedule (`20 6 * * *`) and manual dispatch
- Rebuilds artifacts, verifies them, then opens/updates an automated refresh PR
- Uses branch `ci/refresh-site-snapshot` via `peter-evans/create-pull-request`

## Troubleshooting and common pitfalls

- **ValueError: `max_posts` or `page_size` must be greater than 0**  
  Pass positive integers to crawler inputs.
- **Snapshot verification mismatch**  
  `site_stats.json` was edited or generated from a different dataset. Re-run
  `python3 scripts/build_site_snapshot.py`.
- **Crawler/network failures**  
  The crawler uses direct HTTP requests to Blogspot with a timeout; retry the run
  when network conditions stabilize.
- **Missing `content_text` in output**  
  Expected unless `--include-content` is enabled.
- **Links missing in highlights panel**  
  `index.html` only renders `http`/`https` URLs (`safeUrl` guard).

## Related docs

- `UPDATES.md`: product-facing engagement updates
- `agents.md`: guardrails for coding agents working in this repository
