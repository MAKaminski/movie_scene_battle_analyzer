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
  - Fetches Blogspot JSON feed pages
  - Normalizes post entries
  - Builds aggregate stats
- `movie_scene_battle_analyzer/models.py`
  - Defines `BattlePost`, `SiteStats`, and `CrawlDataset`
- `movie_scene_battle_analyzer/cli.py`
  - Command-line entrypoint for crawling + JSON export

## Data integrity rules

- Never mutate historical snapshots after export.
- Prefer additive event logging over destructive updates.
- Treat ranking formula changes as versioned behavior.
- Avoid hidden weighting; document all ranking inputs.

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
