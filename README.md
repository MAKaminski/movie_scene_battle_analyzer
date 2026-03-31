# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls
[Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes posts,
and produces JSON artifacts used by the hosted stats page and downstream ranking
work.

## Repository map

```text
movie_scene_battle_analyzer/
  cli.py                  # CLI parser + entrypoint
  crawler.py              # Blogspot fetch, normalization, aggregate stats
  models.py               # dataclass payload models
scripts/
  build_site_snapshot.py  # rebuilds both JSON artifacts
  verify_site_snapshot.py # validates shape + cross-file consistency
.github/workflows/
  verify-site-snapshot.yml
  refresh-site-snapshot.yml
index.html                # static page that renders data/site_stats.json
data/
  moviescenebattles_dataset.json
  site_stats.json
```

## Quickstart

```bash
# 1) Crawl and export a dataset
python3 -m movie_scene_battle_analyzer --max-posts 500

# 2) Build deployable snapshot artifacts
python3 scripts/build_site_snapshot.py

# 3) Verify both artifacts are valid and in sync
python3 scripts/verify_site_snapshot.py
```

## Public interfaces

### CLI

Command:

```bash
python3 -m movie_scene_battle_analyzer [options]
```

Supported options (`movie_scene_battle_analyzer/cli.py`):

- `--max-posts` (int, default `500`): maximum number of posts to crawl.
- `--include-content` (flag): include post body text in `content_text`.
- `--output` (path, default `data/moviescenebattles_dataset.json`): destination
  for the dataset JSON.

Constraints from crawler code:

- `max_posts` must be greater than `0`.
- CLI does not expose `page_size` or `timeout`; use Python API for those knobs.

### Python API

Exported from `movie_scene_battle_analyzer/__init__.py`:

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset
```

Signatures:

- `crawl_moviescenebattles(max_posts=500, include_content=False, page_size=150, timeout=30) -> CrawlDataset`
- `save_dataset(dataset, output_path) -> None`

Behavior details:

- Crawling uses Blogspot feed pagination with `start-index` + `max-results`.
- Crawl stops when `max_posts` is reached or feed entries are exhausted.
- `save_dataset` creates parent directories and writes pretty JSON (`indent=2`).

### Data model and JSON contract

`CrawlDataset` fields:

- `site_title`
- `site_url`
- `posts`: list of `BattlePost`
- `stats`: `SiteStats`

`BattlePost` includes:

- identity: `post_id`, `title`, `url`
- timestamps: `published_at`, `updated_at`
- metrics: `comment_count`, `word_count`
- taxonomy: `categories`
- payload: `content_text` (`null` unless `--include-content` is enabled)

`SiteStats` includes:

- totals/averages: `total_posts`, `total_comments`,
  `average_comments_per_post`, `average_words_per_post`
- matchup signal: `posts_with_explicit_matchup` (title regex match on
  `vs|vs.|versus|v`)
- breakdowns: `posts_by_year`, `top_categories`, `most_commented_posts`
- timestamps: `last_post_update`, `crawl_completed_at`

Timestamp serialization note:

- JSON is written with `default=str`, so datetime values are emitted as strings.

## Snapshot artifacts and workflow

### Build snapshot artifacts

`scripts/build_site_snapshot.py` writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

`site_stats.json` is intentionally derived from dataset content:

```json
{
  "site_title": "...",
  "site_url": "...",
  "generated_from_posts": 218,
  "stats": { "...": "copied from dataset.stats" }
}
```

### Verify snapshot artifacts

`scripts/verify_site_snapshot.py` enforces:

1. required keys exist in both files,
2. `posts` is a list and `stats` payloads are objects,
3. `site_stats.json` exactly matches the expected payload derived from
   `moviescenebattles_dataset.json`.

If they diverge, it fails with:

```text
site_stats.json is out of sync with moviescenebattles_dataset.json.
Run: python3 scripts/build_site_snapshot.py
```

## CI automation

### Verify workflow

File: `.github/workflows/verify-site-snapshot.yml`

- Trigger: pull requests targeting `main`, plus manual dispatch.
- Action: runs `python3 scripts/verify_site_snapshot.py` on Python 3.12.

### Refresh workflow

File: `.github/workflows/refresh-site-snapshot.yml`

- Trigger: daily cron (`20 6 * * *`) and manual dispatch.
- Actions:
  1. run `python3 scripts/build_site_snapshot.py`,
  2. run `python3 scripts/verify_site_snapshot.py`,
  3. create/update PR branch `ci/refresh-site-snapshot` via
     `peter-evans/create-pull-request`.

## Hosted stats page (`index.html`)

The static page:

- fetches `data/site_stats.json` with `cache: "no-store"`,
- renders headline/cards + top categories + highlights,
- accepts only `http`/`https` links for post URLs before attaching clickable
  anchors,
- degrades to visible error messaging if snapshot fetch/parsing fails.

## Runbook and troubleshooting

### Common operations

Rebuild + verify before opening a docs/data PR:

```bash
python3 scripts/build_site_snapshot.py
python3 scripts/verify_site_snapshot.py
```

Local stats page check (after artifacts exist):

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

### Frequent failure modes

- **`max_posts must be greater than 0`**
  - Cause: invalid CLI/API argument.
  - Fix: pass a positive integer.
- **`page_size must be greater than 0`**
  - Cause: invalid Python API argument.
  - Fix: pass a positive integer.
- **`Missing required file: data/...json`**
  - Cause: artifacts were not generated.
  - Fix: run `python3 scripts/build_site_snapshot.py`.
- **`site_stats.json is out of sync ...`**
  - Cause: one artifact edited or regenerated without the other.
  - Fix: rebuild both artifacts using the build script.

## Known constraints and pitfalls

- Crawler and scripts intentionally use only Python standard library modules.
- `comment_count` comes from feed field `thr$total.$t` and defaults to `0` when
  missing.
- The verifier expects `site_stats.json` to be derived, not manually curated.
- Any schema changes in `SiteStats` must keep `build_site_snapshot.py`,
  `verify_site_snapshot.py`, and `index.html` aligned.
