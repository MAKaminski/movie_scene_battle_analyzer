# agents.md

## Purpose

This document guides coding agents working on the Movie Scene Battle Analyzer.

Primary product goal: **help people rank movie scenes against one another in a fun, transparent, and trustworthy way.**

## Core responsibilities for agents

1. Keep crawler reliability high.
2. Preserve data integrity in ranking workflows.
3. Make feature updates engaging for users without introducing manipulation vectors.

## Technical architecture map

- `movie_scene_battle_analyzer/crawler.py`
  - Fetches Blogspot JSON feed pages (`start-index`, `max-results`)
  - Normalizes entries into `BattlePost`
  - Computes aggregate `SiteStats`
- `movie_scene_battle_analyzer/models.py`
  - Defines `BattlePost`, `CategoryCount`, `PostHighlight`, `SiteStats`, and `CrawlDataset`
- `movie_scene_battle_analyzer/cli.py` + `__main__.py`
  - CLI entrypoint (`python3 -m movie_scene_battle_analyzer`)
  - Writes crawl dataset JSON
- `scripts/build_site_snapshot.py`
  - Builds `data/moviescenebattles_dataset.json`
  - Builds page-facing `data/site_stats.json`
- `scripts/verify_site_snapshot.py`
  - Validates required JSON shape
  - Enforces `site_stats.json` consistency with dataset projection
- `index.html`
  - Static viewer that reads `data/site_stats.json`
  - Renders cards and lists from `payload.stats`
- `.github/workflows/verify-site-snapshot.yml`
  - PR/manual validation gate
- `.github/workflows/refresh-site-snapshot.yml`
  - Scheduled/manual snapshot refresh automation with PR creation

## Data integrity rules

- Never mutate historical snapshots after export.
- Prefer additive event logging over destructive updates.
- Treat ranking formula changes as versioned behavior.
- Avoid hidden weighting; document all ranking inputs.
- Keep `data/site_stats.json` and `data/moviescenebattles_dataset.json` in sync.
- If consistency checks fail, rerun `python3 scripts/build_site_snapshot.py`.

## Engagement rules

When proposing “fun” features, agents should:

- Encourage quality participation (discussion, consistency, clarity)
- Avoid raw vote-farming mechanics
- Keep canonical rankings explainable and reproducible

Good examples:
- Daily matchup prompt
- Category-based showdown filters
- Explanation panels showing rank contributors

Avoid:
- Opaque boosts for high-activity users
- Unlimited re-voting without audit trail
- Features that blend hype metrics directly into rank without controls

## Update-writing style guide

When writing product updates/changelogs:

1. Lead with achievements (what improved for users and why it matters).
2. Include at least one interactive feature callout.
3. Reaffirm ranking fairness and transparency in plain language.
4. Use concise bullets; avoid overpromising.

## Documentation automation rules

When performing documentation updates:

1. Verify behavior from source code or workflow YAML before documenting it.
2. Prefer editing `README.md` (or existing docs) over creating new files.
3. Document public interfaces and operational steps with runnable examples.
4. Keep docs scannable: short sections, bullets, and explicit constraints.
