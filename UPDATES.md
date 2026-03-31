# Technical Updates

This file tracks concrete subsystem updates in this repository. It avoids product
roadmap items and only documents behavior verified in source code.

## Crawler and normalization

- Added Blogspot feed crawling through
  `movie_scene_battle_analyzer/crawler.py`.
- Implemented pagination using `start-index` + `max-results` until either:
  - `max_posts` is reached, or
  - the feed returns no more entries.
- Normalized each post into `BattlePost` fields including IDs, timestamps,
  categories, comment counts, and word counts.
- Added aggregate stats computation (`SiteStats`) including yearly counts, top
  categories, most-commented posts, matchup-title detection, and crawl
  timestamps.

## Snapshot artifacts

- Added repeatable snapshot build script:
  `scripts/build_site_snapshot.py`.
- Build output includes:
  - `data/moviescenebattles_dataset.json` (full dataset),
  - `data/site_stats.json` (derived payload for `index.html`).
- `site_stats.json` is generated from dataset values, not hand-maintained.

## Snapshot verification

- Added validator script: `scripts/verify_site_snapshot.py`.
- Validator checks:
  - required keys and basic shape in both JSON files,
  - strict equality between `site_stats.json` and expected payload derived from
    `moviescenebattles_dataset.json`.
- CI fails if artifacts are missing or out of sync.

## CI workflows

- Added PR verification workflow:
  `.github/workflows/verify-site-snapshot.yml`.
  - Runs on pull requests to `main`.
  - Executes snapshot validation.
- Added scheduled refresh workflow:
  `.github/workflows/refresh-site-snapshot.yml`.
  - Rebuilds and validates snapshot artifacts.
  - Opens/updates automated refresh PRs via `peter-evans/create-pull-request`.

## Hosted stats page

- Added static `index.html` that loads `data/site_stats.json` at runtime.
- Renders top-level totals, category leaders, and highlighted posts.
- Restricts outbound highlight links to `http`/`https` URLs before rendering.
- Displays user-visible error state when snapshot loading fails.
