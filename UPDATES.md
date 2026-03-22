# Technical Updates

## Snapshot automation and verification

- Added `scripts/build_site_snapshot.py` to regenerate:
  - `data/moviescenebattles_dataset.json`
  - `data/site_stats.json`
- Added `scripts/verify_site_snapshot.py` to enforce:
  - required JSON keys
  - strict consistency between dataset-derived stats and `site_stats.json`

## CI workflow coverage

- Added `.github/workflows/verify-site-snapshot.yml`
  - runs on PRs to `main` and manual dispatch
  - executes snapshot validation script
- Added `.github/workflows/refresh-site-snapshot.yml`
  - scheduled daily (`20 6 * * *`) and manual dispatch
  - rebuilds artifacts, verifies them, and opens/updates PR branch `ci/refresh-site-snapshot`

## Stats page hardening

- Updated `index.html` to validate outgoing post URLs before linking.
- Invalid or non-HTTP(S) URLs now render as plain text instead of clickable links.
- Snapshot fetch uses `cache: "no-store"` so the page favors current data.

## Documentation improvements in this update

- `README.md` now documents:
  - CLI and Python public interfaces
  - snapshot artifact contract
  - local runbook for build/verify
  - CI behavior and troubleshooting paths
