from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from movie_scene_battle_analyzer.models import CrawlDataset, SiteStats

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    spec.loader.exec_module(module)
    return module


verify_site_snapshot = _load_module(
    "verify_site_snapshot",
    ROOT / "scripts" / "verify_site_snapshot.py",
)
build_site_snapshot = _load_module(
    "build_site_snapshot",
    ROOT / "scripts" / "build_site_snapshot.py",
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@contextmanager
def _in_temp_cwd():
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        try:
            yield Path(temp_dir)
        finally:
            os.chdir(old_cwd)


class VerifySnapshotScriptTests(unittest.TestCase):
    def test_assert_required_dataset_shape_rejects_bad_posts_type(self) -> None:
        with self.assertRaises(ValueError):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": {},
                    "stats": {},
                }
            )

    def test_main_raises_when_site_stats_is_out_of_sync(self) -> None:
        with _in_temp_cwd() as temp_root:
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}],
                "stats": {"total_posts": 1},
            }
            mismatched_site_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 999,
                "stats": {"total_posts": 999},
            }
            _write_json(temp_root / "data" / "moviescenebattles_dataset.json", dataset)
            _write_json(temp_root / "data" / "site_stats.json", mismatched_site_stats)

            with self.assertRaises(ValueError):
                verify_site_snapshot.main()

    def test_main_passes_when_site_stats_matches_dataset(self) -> None:
        with _in_temp_cwd() as temp_root:
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}, {"post_id": "2"}],
                "stats": {"total_posts": 2, "total_comments": 8},
            }
            matching_site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": len(dataset["posts"]),
                "stats": dataset["stats"],
            }
            _write_json(temp_root / "data" / "moviescenebattles_dataset.json", dataset)
            _write_json(temp_root / "data" / "site_stats.json", matching_site_stats)

            verify_site_snapshot.main()


class BuildSnapshotScriptTests(unittest.TestCase):
    def test_main_writes_expected_site_stats_payload(self) -> None:
        dataset = CrawlDataset(
            site_title="Movie Scene Battles",
            site_url="https://moviescenebattles.blogspot.com",
            posts=[],
            stats=SiteStats(
                total_posts=0,
                total_comments=0,
                average_comments_per_post=0.0,
                average_words_per_post=0.0,
                posts_with_explicit_matchup=0,
            ),
        )

        with _in_temp_cwd() as temp_root:
            with (
                patch.object(build_site_snapshot, "crawl_moviescenebattles", return_value=dataset) as crawl_mock,
                patch.object(build_site_snapshot, "save_dataset") as save_mock,
            ):
                build_site_snapshot.main()

            crawl_mock.assert_called_once_with(max_posts=1000, include_content=False)
            save_mock.assert_called_once_with(dataset, Path("data/moviescenebattles_dataset.json"))

            site_stats_path = temp_root / "data" / "site_stats.json"
            written_payload = json.loads(site_stats_path.read_text(encoding="utf-8"))

            self.assertEqual(written_payload["site_title"], dataset.site_title)
            self.assertEqual(written_payload["site_url"], dataset.site_url)
            self.assertEqual(written_payload["generated_from_posts"], 0)
            self.assertEqual(written_payload["stats"]["total_posts"], 0)


if __name__ == "__main__":
    unittest.main()
