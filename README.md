# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes posts, and builds snapshot artifacts that power analytics and the static stats page.

## Intent and architecture

The project has four main responsibilities:

1. **Fetch** Blogspot feed pages (`movie_scene_battle_analyzer/crawler.py`).
2. **Normalize** entries into typed records (`movie_scene_battle_analyzer/models.py`).
3. **Aggregate** site-level metrics (`SiteStats`) from crawled posts.
4. **Publish** JSON snapshots used by `index.html` and CI checks.

### Key codepaths

```text
movie_scene_battle_analyzer/cli.py         # CLI entrypoint
movie_scene_battle_analyzer/crawler.py     # feed fetch + parsing + stats build
movie_scene_battle_analyzer/models.py      # dataclasses for post and stats schema
scripts/build_site_snapshot.py             # writes dataset + site_stats payloads
scripts/verify_site_snapshot.py            # validates shape and sync between files
index.html                                 # static page reads data/site_stats.json
```

## Setup

No third-party Python dependencies are required.

```bash
python3 --version
python3 -m movie_scene_battle_analyzer --max-posts 100
```

Default CLI output path: `data/moviescenebattles_dataset.json`.

## Public interfaces

### CLI (`python3 -m movie_scene_battle_analyzer`)

| Flag | Default | Description |
| --- | --- | --- |
| `--max-posts` | `500` | Maximum posts to crawl. Must be greater than `0`. |
| `--include-content` | `false` | Include normalized post body text in each `BattlePost.content_text`. |
| `--output` | `data/moviescenebattles_dataset.json` | Output file path for the crawl dataset JSON. |

Example:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 300 --include-content --output data/moviescenebattles_dataset.json
```

### Python API (`movie_scene_battle_analyzer/__init__.py`)

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Behavioral constraints from `crawl_moviescenebattles`:

- Raises `ValueError` when `max_posts <= 0`.
- Raises `ValueError` when `page_size <= 0`.
- Uses Blogspot feed pagination (`start-index`, `max-results`) until max posts are collected or feed entries are exhausted.

## Snapshot artifacts and runbook

### Artifacts

- `data/moviescenebattles_dataset.json`
  - Full normalized crawl payload with keys: `site_title`, `site_url`, `posts`, `stats`.
- `data/site_stats.json`
  - Reduced payload consumed by `index.html`:
    - `site_title`
    - `site_url`
    - `generated_from_posts`
    - `stats` (must match dataset `stats` exactly)

### Local refresh workflow

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

What this does:

1. Rebuilds both snapshot files from a fresh crawl (`max_posts=1000`, `include_content=False`).
2. Verifies required keys and ensures `site_stats.json` is exactly derived from the dataset file.

## CI workflows

### `.github/workflows/verify-site-snapshot.yml`

- Triggered on pull requests to `main` and manual dispatch.
- Runs `python3 scripts/verify_site_snapshot.py`.
- Fails if snapshot files are missing, malformed, or out of sync.

### `.github/workflows/refresh-site-snapshot.yml`

- Triggered daily (`20 6 * * *`) and manual dispatch.
- Rebuilds artifacts, verifies them, then opens/updates PR branch `ci/refresh-site-snapshot`.
- Uses commit title: `chore: refresh movie scene snapshot data`.

## Static stats page (`index.html`)

The page fetches `data/site_stats.json` with `cache: "no-store"` and renders:

- total posts
- matchup-style title count
- average comments and words per post
- top 10 categories
- top 5 most-commented posts

Safety behavior:

- Post links are validated in-browser; only `http:` and `https:` URLs are linked.
- Invalid URLs are rendered as plain text.

For local testing, serve the repository via HTTP (not `file://`):

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Troubleshooting and common pitfalls

### `ValueError: max_posts must be greater than 0`

Use a positive `--max-posts` value or API argument.

### `site_stats.json is out of sync with moviescenebattles_dataset.json`

Run:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Commit both updated data files together.

### `Missing required file: data/...`

Snapshot artifacts have not been generated in the current workspace. Run the build script above.

### `Could not load stats snapshot.` in the browser

Likely causes:

- `data/site_stats.json` is missing
- the page is opened via `file://` instead of an HTTP server
- invalid JSON payload

Verify with `python3 scripts/verify_site_snapshot.py` and serve via `python3 -m http.server`.
