# Movie Scene Battle Analyzer

`movie_scene_battle_analyzer` crawls [Movie Scene Battles](https://moviescenebattles.blogspot.com), normalizes post data, and computes ranking-friendly site stats so movie matchups can be explored and compared with confidence.

## What this tool does

- Crawls Blogspot feed pages from `https://moviescenebattles.blogspot.com`
- Normalizes each post into a structured `BattlePost` record
- Builds aggregate `SiteStats` (comments, category leaders, yearly posting trends, etc.)
- Exports all data to JSON for downstream ranking, analytics, or product features

## How the tournament is rebuilt

Movie Scene Battles is a king-of-the-hill ladder: two scenes are posted, readers vote, the winner returns the next day as
champion and keeps defending until it loses or reaches seven wins, at which point it retires to the Hall of Fame.

Each post carries three independent signals, and `insights.py` **re-joins** them:

- **The published poll** - every closed battle ends with `The Score: <scene> <votes>, <scene> <votes>`, sometimes marked
  `(tiebreaker used)` when the poll ended level and the owner cast the deciding vote.
- **The succession of posts** - the scene that comes back as champion won the previous battle, and a post introducing two
  challengers marks a retirement at seven wins.
- **The site's own counter** - the champion's `(N)` in each "The Case for" heading.

Cross-checking the three is what makes the reconstruction trustworthy: on the current snapshot the poll result and the
next post's champion agree on **317 of 317** decided battles. Scene-name typos are tolerated by anchoring identity on the
movie plus a fuzzy name match, and anything that cannot be resolved is reported rather than guessed.

Submitter credits (`(Submitted by <name>)`) are attributed positionally to the scene whose "The Case for" block they sit
in, because the credit rides that scene through its entire reign.

The resulting `data/site_insights.json` carries vote turnout and margins, reigns, Hall of Fame, upset rates, hold rate by
streak, movie and decade leaderboards, a submitter leaderboard, monthly cadence with trailing-average estimates vs
actuals, and a data-quality block reporting every judgement call.

## Project structure

```text
movie_scene_battle_analyzer/
  __init__.py
  __main__.py
  cli.py
  crawler.py     # feed crawl + champion/challenger parsing
  insights.py    # tournament reconstruction and analytics
  models.py
scripts/
  build_site_snapshot.py
  verify_site_snapshot.py
tests/
  test_insights.py
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
- `champion`, `champion_movie`, `challenger`, `challenger_movie` (parsed from the post body)
- `champion_wins_claimed` (the site's own "(N)" counter) and `battle_type` (`defense` or `fresh`)
- `score_entries` (the published vote counts), `tiebreaker`, and `submitters` (credited name plus the scene credited)

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

This repository includes a deployable `index.html` dashboard that reads snapshot data from:

- `data/site_stats.json`
- `data/site_insights.json`

The page is organised as seven tabs so no single view runs long — deep-link to any of them with a hash:

| Tab | `#hash` | What it holds |
|---|---|---|
| Today | `#today` | Live head-to-head, road-to-retirement meter, last five results, debate card |
| The Vote | `#vote` | Turnout, margin distribution, nail-biters, blowouts, tiebreakers, turnout by streak |
| The Ladder | `#ladder` | Hold rate by streak, reign lengths, Hall of Fame, giant killers, most dominant reigns |
| Movies | `#movies` | Movie leaderboard, win rate by decade |
| Cadence | `#cadence` | Estimate vs actual per month, weekday and hour, 30-day momentum |
| People | `#people` | Credited submitters, their scenes and records |
| Method | `#method` | Reconstruction confidence and every judgement call |

Every chart has a table view and hover tooltips, tabs are keyboard-navigable, and the page is plain HTML with no build
step.

To refresh the dataset, stats and insights before deploy:

```bash
python3 scripts/build_site_snapshot.py
python3 -m unittest discover -s tests
python3 scripts/verify_site_snapshot.py
```

This writes:

- `data/moviescenebattles_dataset.json`
- `data/site_stats.json`
- `data/site_insights.json`

## CI automation

This repo includes GitHub Actions to handle the refresh process:

- `.github/workflows/verify-site-snapshot.yml`
  - Runs on PRs to `main`
  - Runs the unit tests, then validates that `site_stats.json` and `site_insights.json` are byte-for-byte what the
    dataset regenerates
- `.github/workflows/refresh-site-snapshot.yml`
  - Runs daily (scheduled) and on manual dispatch
  - Rebuilds artifacts, verifies consistency, and opens/updates an automated PR with refreshed data
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
