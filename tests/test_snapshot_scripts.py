from __future__ import annotations

import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_scene_battle_analyzer.models import CrawlDataset, SiteStats
from scripts import build_site_snapshot, verify_site_snapshot


@contextlib.contextmanager
def _in_temp_workdir() -> object:
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        try:
            yield Path(tmpdir)
        finally:
            os.chdir(original_cwd)


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_when_file_missing(self) -> None:
        missing = Path("does-not-exist.json")
        with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
            verify_site_snapshot._load_json(missing)

    def test_assert_required_dataset_shape_validates_posts_type(self) -> None:
        invalid_dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": {},
            "stats": {},
        }
        with self.assertRaisesRegex(ValueError, "Dataset field `posts` must be a list"):
            verify_site_snapshot._assert_required_dataset_shape(invalid_dataset)

    def test_main_raises_when_site_stats_is_out_of_sync(self) -> None:
        with _in_temp_workdir() as tmpdir:
            data_dir = tmpdir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}],
                "stats": {"total_posts": 1},
            }
            site_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 999,
                "stats": {"total_posts": 1},
            }
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "out of sync"):
                verify_site_snapshot.main()

    def test_main_passes_when_dataset_and_site_stats_match(self) -> None:
        with _in_temp_workdir() as tmpdir:
            data_dir = tmpdir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}, {"post_id": "2"}],
                "stats": {"total_posts": 2},
            }
            site_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 2,
                "stats": {"total_posts": 2},
            }
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            verify_site_snapshot.main()


class BuildSiteSnapshotTests(unittest.TestCase):
    def test_main_writes_site_stats_payload_from_dataset(self) -> None:
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
                posts_by_year={},
                top_categories=[],
                most_commented_posts=[],
            ),
        )

        with _in_temp_workdir() as tmpdir:
            with patch.object(
                build_site_snapshot, "crawl_moviescenebattles", return_value=dataset
            ) as crawl_mock, patch.object(build_site_snapshot, "save_dataset") as save_mock:
                build_site_snapshot.main()

            crawl_mock.assert_called_once_with(max_posts=1000, include_content=False)
            save_mock.assert_called_once()
            save_path = save_mock.call_args.args[1]
            self.assertEqual(Path(save_path), Path("data/moviescenebattles_dataset.json"))

            site_stats_file = tmpdir / "data" / "site_stats.json"
            self.assertTrue(site_stats_file.exists())
            payload = json.loads(site_stats_file.read_text(encoding="utf-8"))
            self.assertEqual(
                payload,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 0,
                    "stats": {
                        "total_posts": 0,
                        "total_comments": 0,
                        "average_comments_per_post": 0.0,
                        "average_words_per_post": 0.0,
                        "posts_with_explicit_matchup": 0,
                        "posts_by_year": {},
                        "top_categories": [],
                        "most_commented_posts": [],
                        "last_post_update": None,
                        "crawl_completed_at": None,
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
