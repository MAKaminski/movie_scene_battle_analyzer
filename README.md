# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes feed entries into structured records, and computes site-level stats used by the static stats page.

## Architecture at a glance

| Path | Purpose |
| --- | --- |
| `movie_scene_battle_analyzer/crawler.py` | Blogspot feed pagination, post normalization, aggregate stat computation |
| `movie_scene_battle_analyzer/models.py` | Dataclasses for `BattlePost`, `SiteStats`, `CrawlDataset`, and stat subtypes |
| `movie_scene_battle_analyzer/cli.py` | CLI entrypoint for crawl + dataset export |
| `scripts/build_site_snapshot.py` | Rebuilds both JSON artifacts consumed by the site |
| `scripts/verify_site_snapshot.py` | Enforces artifact shape and exact parity between files |
| `index.html` | Static page that fetches `data/site_stats.json` and renders live stats |

## Public interfaces

### CLI

Run from repository root:

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Arguments:

- `--max-posts` (int, default `500`): maximum posts to crawl.
- `--include-content` (flag, default `false`): include normalized post body text in `content_text`.
- `--output` (path, default `data/moviescenebattles_dataset.json`): output JSON path.

### Python API

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Behavior and constraints (from `crawler.py`):

- `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30)`
  - uses Blogspot feed pagination via `start-index` / `max-results`.
  - stops when `max_posts` is reached or when a page returns no entries.
  - raises `ValueError` when `max_posts <= 0` or `page_size <= 0`.
- `save_dataset(dataset, output_path)`
  - creates parent directories automatically.
  - serializes datetimes as strings using `json.dumps(..., default=str)`.

## Output artifacts

### `data/moviescenebattles_dataset.json`

Primary crawl output with:

- site metadata: `site_title`, `site_url`
- `posts`: list of normalized `BattlePost`
- `stats`: computed `SiteStats`

`BattlePost` includes:

- `post_id`, `title`, `url`
- `published_at`, `updated_at`
- `comment_count`, `categories`, `word_count`
- `content_text` (only populated when `--include-content` or `include_content=True`)

`SiteStats` includes:

- totals and averages: `total_posts`, `total_comments`, `average_comments_per_post`, `average_words_per_post`
- ranking context: `posts_with_explicit_matchup`, `posts_by_year`, `top_categories`, `most_commented_posts`
- timing fields: `last_post_update`, `crawl_completed_at`

### `data/site_stats.json`

Derived payload for the website, written by `scripts/build_site_snapshot.py`:

- `site_title`
- `site_url`
- `generated_from_posts` (must equal `len(dataset.posts)`)
- `stats` (must exactly match `dataset.stats`)

`scripts/verify_site_snapshot.py` fails if this file diverges from the dataset-derived expected payload.

## Snapshot runbook (local)

1. Rebuild artifacts:

   ```bash
   python3 scripts/build_site_snapshot.py
   ```

2. Verify artifacts are internally consistent:

   ```bash
   python3 scripts/verify_site_snapshot.py
   ```

3. Preview the static site locally:

   ```bash
   python3 -m http.server 8000
   ```

   Then open `http://localhost:8000/` and confirm cards/lists render from `data/site_stats.json`.

## CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - runs on pull requests to `main` and manual dispatch.
  - executes `python3 scripts/verify_site_snapshot.py`.
- `.github/workflows/refresh-site-snapshot.yml`
  - runs daily on cron and manual dispatch.
  - rebuilds snapshot artifacts, verifies them, and opens/updates an automated refresh PR.

## Troubleshooting and common pitfalls

- **`Missing required file: data/...`**
  - `verify_site_snapshot.py` expects both JSON artifacts to exist.
  - run `python3 scripts/build_site_snapshot.py` first.

- **`site_stats.json is out of sync with moviescenebattles_dataset.json`**
  - `site_stats.json` is intentionally strict: it must exactly equal the dataset-derived payload.
  - regenerate both files via `scripts/build_site_snapshot.py` instead of editing one manually.

- **Unexpectedly large dataset output**
  - `content_text` is omitted by default; enabling `--include-content` can increase file size significantly.

- **No local stats rendering in browser**
  - `index.html` loads data via `fetch("data/site_stats.json")`; serve the repo over HTTP (`python3 -m http.server`) rather than opening `file://.../index.html` directly.

## Notes

- No third-party runtime dependencies are required.
- Link rendering in `index.html` is restricted to `http:` / `https:` URLs (`safeUrl`) for safety.
