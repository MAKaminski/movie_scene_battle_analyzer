# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls
[Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes posts,
and produces snapshot artifacts used by the hosted stats page and CI checks.

## Intent and architecture

The project has one core workflow:

1. Crawl Blogspot feed entries.
2. Normalize each entry into typed records.
3. Compute aggregate site stats.
4. Write JSON artifacts consumed by `index.html` and CI verification.

### Codepath map

```text
movie_scene_battle_analyzer/crawler.py    # feed fetch, normalization, stats computation
movie_scene_battle_analyzer/models.py     # BattlePost/SiteStats/CrawlDataset dataclasses
movie_scene_battle_analyzer/cli.py        # CLI args and crawl entrypoint
scripts/build_site_snapshot.py            # builds dataset + site_stats artifacts
scripts/verify_site_snapshot.py           # validates required keys + artifact consistency
index.html                                # reads data/site_stats.json for live stats page
```

## Public interfaces

### CLI interface

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Supported flags (from `movie_scene_battle_analyzer/cli.py`):

- `--max-posts` (default `500`, must be `> 0`)
- `--include-content` (stores extracted post body text in `content_text`)
- `--output` (default `data/moviescenebattles_dataset.json`)

### Python API

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(
    max_posts=300,        # must be > 0
    include_content=False,
    page_size=150,        # must be > 0
    timeout=30,           # urllib timeout in seconds
)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

Exported API surface (`movie_scene_battle_analyzer/__init__.py`):

- `crawl_moviescenebattles(...) -> CrawlDataset`
- `save_dataset(dataset, output_path) -> None`
- dataclasses: `BattlePost`, `CategoryCount`, `PostHighlight`, `SiteStats`, `CrawlDataset`

## Data artifacts and constraints

### `data/moviescenebattles_dataset.json`

Contains:

- `site_title`
- `site_url`
- `posts` (`BattlePost[]`)
- `stats` (`SiteStats`)

### `data/site_stats.json`

Contains:

- `site_title`
- `site_url`
- `generated_from_posts`
- `stats`

`scripts/verify_site_snapshot.py` enforces that `data/site_stats.json` must match
the expected payload derived from `data/moviescenebattles_dataset.json`.

### Stats behavior (important for consumers)

- `posts_with_explicit_matchup` is title-based and uses regex:
  `\b(vs\.?|versus|v)\b` (case-insensitive).
- `top_categories` is capped to 10 entries.
- `most_commented_posts` is capped to 5 entries.
- Datetime fields are serialized as strings in JSON output.

## Runbook: refresh and verify snapshots

### Local refresh

```bash
python3 scripts/build_site_snapshot.py
```

Writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

### Local verification

```bash
python3 scripts/verify_site_snapshot.py
```

The check fails if either artifact is missing, has wrong top-level keys, or if
`site_stats.json` is out of sync with `moviescenebattles_dataset.json`.

### Hosted page

`index.html` fetches `data/site_stats.json` with `cache: "no-store"` and renders:

- total posts
- matchup-style post count
- average comments/words per post
- top categories
- most-commented post links

## CI workflows

- `.github/workflows/verify-site-snapshot.yml`
  - triggers: PRs targeting `main`, manual dispatch
  - action: runs `python3 scripts/verify_site_snapshot.py`
- `.github/workflows/refresh-site-snapshot.yml`
  - triggers: daily cron (`20 6 * * *`), manual dispatch
  - action: rebuilds artifacts, verifies, and opens/updates refresh PRs

## Troubleshooting and common pitfalls

- **`ValueError: max_posts must be greater than 0`**
  - Cause: invalid `--max-posts` or API argument.
  - Fix: pass a positive integer.
- **`ValueError: page_size must be greater than 0`**
  - Cause: invalid API usage of `crawl_moviescenebattles(page_size=...)`.
  - Fix: keep `page_size >= 1`.
- **`site_stats.json is out of sync` during verify**
  - Cause: dataset changed without regenerating site stats.
  - Fix: run `python3 scripts/build_site_snapshot.py` and commit both files.
- **Network timeout or transient fetch failures**
  - Cause: Blogspot feed unavailable/slow.
  - Fix: retry; increase `timeout` when using the Python API.
- **Unexpectedly large dataset files**
  - Cause: `--include-content` stores full extracted post text per post.
  - Fix: omit `--include-content` unless downstream consumers require body text.

## Related docs

- Product-oriented update notes: `UPDATES.md`
- Agent behavior and integrity principles: `agents.md`
