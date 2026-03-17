# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and computes ranking-friendly site stats so movie matchups can be explored and compared with confidence.

## What this tool does

- Crawls Blogspot feed pages from `https://moviescenebattles.blogspot.com`
- Normalizes each post into a structured `BattlePost` record
- Builds aggregate `SiteStats` (comments, category leaders, yearly posting trends, etc.)
- Exports all data to JSON for downstream ranking, analytics, or product features

## Project structure

```text
movie_scene_battle_analyzer/
  __init__.py
  __main__.py
  cli.py
  crawler.py
  models.py
```

## Core data structures

### `BattlePost`
Stores one crawlable matchup post:
- `post_id`
- `title`
- `url`
- `published_at`
- `updated_at`
- `comment_count`
- `categories`
- `word_count`
- `content_text` (optional)

### `SiteStats`
Stores aggregate website metrics:
- `total_posts`
- `total_comments`
- `average_comments_per_post`
- `average_words_per_post`
- `posts_with_explicit_matchup`
- `posts_by_year`
- `top_categories`
- `most_commented_posts`
- `last_post_update`
- `crawl_completed_at`

### `CrawlDataset`
Stores:
- site metadata (`site_title`, `site_url`)
- all normalized posts
- computed aggregate stats

## Usage

### Run from CLI

```bash
python3 -m movie_scene_battle_analyzer --max-posts 500 --output data/moviescenebattles_dataset.json
```

Optional:

```bash
python3 -m movie_scene_battle_analyzer --include-content
```

### Use in Python

```python
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset

dataset = crawl_moviescenebattles(max_posts=300, include_content=False)
save_dataset(dataset, "data/moviescenebattles_dataset.json")
```

## Hosted stats page

This repository now includes a deployable `index.html` page that reads live snapshot data from:

- `data/site_stats.json`

To refresh both the full dataset and website stats payload before deploy:

```bash
python3 scripts/build_site_snapshot.py
```

This writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`

## Engaging Product Updates (Integrity-First Edition)

These updates are designed to make the experience more fun while preserving the core mission: **let people rank movie scenes against one another fairly**.

### Achievements to highlight

1. **Reliable crawl + structured dataset**
   - We now convert raw Blogspot entries into a clean, reusable battle dataset.
2. **Transparent ranking context**
   - Category, comments, and publication trends are captured so users can understand *why* scenes perform well.
3. **Repeatable exports**
   - Snapshots can be generated again at any time, keeping rankings fresh and auditable.

### Fun user-facing features (without compromising ranking integrity)

1. **Daily Head-to-Head**
   - Users vote on one curated scene battle per day.
   - Votes count separately from canonical rank until moderation checks pass.
2. **Streaks for thoughtful voting**
   - Reward consistency (e.g., 7-day vote streak) rather than vote volume spam.
3. **Category Clash mode**
   - Filter battles by themes (hero showdown, final act, best monologue) and compare category leaders.
4. **Comment Power Meter**
   - Show which battles generated the strongest discussion while keeping rank calculations transparent.
5. **Debate Cards**
   - One-click shareable cards with matchup title, current rank delta, and comment highlights.

## Ranking integrity principles

- Keep source crawl data immutable once snapshotted
- Store vote events separately from base crawl stats
- Version ranking formula changes so historical comparisons stay valid
- Surface confidence indicators when sample sizes are small

## Notes

- Crawler uses Blogspot feed pagination (`start-index`, `max-results`)
- No third-party dependencies are required
