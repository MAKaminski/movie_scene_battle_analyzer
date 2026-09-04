# Product Updates

## 2026-09-04 - The vote, surfaced

### What we achieved

- **Read the actual votes.** Every closed battle publishes its poll result, and we now parse all of them: **3,962 votes
  across 317 polls**. The previous release wrongly assumed vote totals were never published.
- **Validated the whole reconstruction against them.** The poll winner and the next post's champion agree on **317 of
  317** decided battles, on top of the win-counter check (308 of 309) and the Hall of Fame reconciliation (9 of 9).
- **Surfaced the community.** Submitter credits are now attributed to the scene they sit beside, giving a leaderboard of
  the **6 named contributors** behind 11 scenes and 16 battles.
- **Reorganised the page into seven tabs**, so each view is a screen or two instead of one long scroll.

### The findings worth arguing about

- **31% of all battles are decided by a single vote** (97 of 317), on an average turnout of 12.5.
- **Four polls ended level** and were settled by the site owner's tiebreaker.
- **Turnout is flat across the ladder** (12.2 to 13.3 votes at every rung), so the rising hold rate for long-running
  champions is voters changing their minds, not a bandwagon arriving.
- **The most dominant reign** is The Rules for Surviving Horror Movies (Scream), seven wins at an average margin of 6.5.

### Interactive feature callout

- **The Vote tab** puts every poll on a split bar - nail-biters, blowouts and tiebreakers - so a reader can see how close
  the tournament really is.

### Fairness and transparency

- Every number remains a pure function of the crawl. One score line on the site names a scene that is not in its own
  matchup; it is reported in the Method tab and left uncounted rather than guessed.

## 2026-09-04 - Tournament Intelligence refresh

### What we achieved

- **Re-joined 319 battles into one ladder.** Winners are inferred from the succession of posts (the scene that returns
  as champion won). 318 of 319 battles are decided; the one left open is today's poll.
- **Cross-checked the inference against the site itself.** The champion's "(N)" counter agreed 308 of 309 times, and the
  nine inferred retirements match the nine movies labelled on the Hall of Fame page.
- **Shipped the analytical dashboard.** Head-to-head meter, rejoinder stat tiles, estimate-vs-actual cadence,
  hold rate by streak, reign lengths, Hall of Fame and near misses, giant killers, movie and decade leaderboards, a
  debate card and a data-integrity panel. Every chart has a table view.
- **Refreshed the snapshot.** 325 posts (up from 218), data through 2026-09-03.

### Interactive feature callout

- **Daily head-to-head** shows the live matchup, the champion's road to retirement and the historical hold rate at that
  rung, with a one-click debate card to share.

### Fairness and transparency

- No hidden weighting: every number is a pure function of the crawl, and the integrity panel lists every judgement call
  the chain needed (four scene-name typos matched on movie, one win-counter mismatch resolved against the Hall of Fame).

## Engagement Refresh (earlier)

## What we achieved

- **Launched a live crawler** for Movie Scene Battles so rankings can be powered by current, structured data.
- **Added stat-rich datasets** (comments, category leaders, yearly activity, matchup signal) to improve ranking context.
- **Made exports repeatable** so rankings can be regenerated and verified at any time.

## New fun features in development

1. **Daily Head-to-Head Arena**
   - One featured scene battle each day with community voting.
2. **Category Clash Leaderboards**
   - Rank scenes inside specific battle styles (e.g., rivalry, final showdown, courtroom scene).
3. **Debate Boost**
   - Highlight high-quality community arguments, not just vote totals.
4. **Momentum Tracker**
   - Show which battles are rising this week while preserving long-term ranking history.

## Integrity commitments

- Canonical rankings remain formula-based and auditable.
- Community interactions are tracked as separate signals until validated.
- Ranking formula changes are versioned and documented.
- Low-sample matchups display confidence indicators.
