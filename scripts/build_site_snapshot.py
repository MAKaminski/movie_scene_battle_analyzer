#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from movie_scene_battle_analyzer import crawl_moviescenebattles, save_dataset


def main() -> None:
    dataset_path = Path("data/moviescenebattles_dataset.json")
    stats_path = Path("data/site_stats.json")

    dataset = crawl_moviescenebattles(max_posts=1000, include_content=False)
    if not dataset.posts:
        raise RuntimeError(
            "Crawler returned zero posts; refusing to overwrite snapshot artifacts with empty data."
        )
    save_dataset(dataset, dataset_path)

    stats_payload = {
        "site_title": dataset.site_title,
        "site_url": dataset.site_url,
        "generated_from_posts": len(dataset.posts),
        "stats": asdict(dataset.stats),
    }
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats_payload, indent=2, default=str), encoding="utf-8")

    print(f"Wrote {dataset_path} and {stats_path}")


if __name__ == "__main__":
    main()
