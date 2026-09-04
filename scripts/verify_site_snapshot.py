#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from movie_scene_battle_analyzer.insights import build_insights


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_required_dataset_shape(dataset: dict) -> None:
    required_keys = {"site_title", "site_url", "posts", "stats"}
    missing = required_keys.difference(dataset.keys())
    if missing:
        raise ValueError(f"Dataset missing keys: {sorted(missing)}")
    if not isinstance(dataset["posts"], list):
        raise ValueError("Dataset field `posts` must be a list")
    if not isinstance(dataset["stats"], dict):
        raise ValueError("Dataset field `stats` must be an object")


def _assert_required_stats_shape(site_stats: dict) -> None:
    required_keys = {"site_title", "site_url", "generated_from_posts", "stats"}
    missing = required_keys.difference(site_stats.keys())
    if missing:
        raise ValueError(f"Site stats missing keys: {sorted(missing)}")
    if not isinstance(site_stats["stats"], dict):
        raise ValueError("Site stats field `stats` must be an object")


def main() -> None:
    dataset_path = Path("data/moviescenebattles_dataset.json")
    site_stats_path = Path("data/site_stats.json")

    dataset = _load_json(dataset_path)
    site_stats = _load_json(site_stats_path)
    _assert_required_dataset_shape(dataset)
    _assert_required_stats_shape(site_stats)

    expected_payload = {
        "site_title": dataset["site_title"],
        "site_url": dataset["site_url"],
        "generated_from_posts": len(dataset["posts"]),
        "stats": dataset["stats"],
    }

    if site_stats != expected_payload:
        raise ValueError(
            "site_stats.json is out of sync with moviescenebattles_dataset.json. "
            "Run: python3 scripts/build_site_snapshot.py"
        )

    insights_path = Path("data/site_insights.json")
    insights = _load_json(insights_path)
    expected_insights = json.loads(json.dumps(build_insights(dataset)))
    if insights != expected_insights:
        raise ValueError(
            "site_insights.json is out of sync with moviescenebattles_dataset.json. "
            "Run: python3 scripts/build_site_snapshot.py"
        )

    print("Snapshot validation passed.")


if __name__ == "__main__":
    main()
