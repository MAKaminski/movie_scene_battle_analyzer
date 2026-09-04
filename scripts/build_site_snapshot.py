#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset
from movie_scene_battle_analyzer.insights import build_insights


def main() -> None:
    dataset_path = Path("data/moviescenebattles_dataset.json")
    stats_path = Path("data/site_stats.json")
    insights_path = Path("data/site_insights.json")

    dataset = crawl_moviescenebattles(max_posts=1000, include_content=False)
    save_dataset(dataset, dataset_path)

    stats_payload = {
        "site_title": dataset.site_title,
        "site_url": dataset.site_url,
        "generated_from_posts": len(dataset.posts),
        "stats": asdict(dataset.stats),
    }
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats_payload, indent=2, default=str), encoding="utf-8")

    # Insights are derived from the on-disk dataset so verify_site_snapshot.py can
    # regenerate them byte-for-byte without network access.
    dataset_dict = json.loads(dataset_path.read_text(encoding="utf-8"))
    insights_path.write_text(json.dumps(build_insights(dataset_dict), indent=2), encoding="utf-8")

    print(f"Wrote {dataset_path}, {stats_path} and {insights_path}")


if __name__ == "__main__":
    main()
