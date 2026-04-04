from __future__ import annotations

import importlib.util
import io
import json
import os
from contextlib import contextmanager, redirect_stdout
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer.models import BattlePost, CrawlDataset, SiteStats


ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_site_snapshot.py"
BUILD_SCRIPT = ROOT / "scripts" / "build_site_snapshot.py"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    spec.loader.exec_module(module)
    return module


@contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class VerifySiteSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module(VERIFY_SCRIPT, "verify_site_snapshot_test_module")

    def test_load_json_raises_for_missing_file(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
            self.module._load_json(Path("missing.json"))

    def test_assert_required_dataset_shape_rejects_non_list_posts(self) -> None:
        with self.assertRaisesRegex(ValueError, "posts` must be a list"):
            self.module._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": {},
                    "stats": {},
                }
            )

    def test_main_raises_when_site_stats_out_of_sync(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": 1}],
            "stats": {"total_posts": 1},
        }
        mismatched_site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 999,
            "stats": {"total_posts": 1},
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(mismatched_site_stats), encoding="utf-8"
            )

            with _cwd(root):
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    self.module.main()

    def test_main_passes_with_matching_payload(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": 1}, {"id": 2}],
            "stats": {"total_posts": 2},
        }
        matching_site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 2,
            "stats": {"total_posts": 2},
        }

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(matching_site_stats), encoding="utf-8"
            )

            with _cwd(root):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.module.main()

            self.assertIn("Snapshot validation passed.", output.getvalue())


class BuildSiteSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module(BUILD_SCRIPT, "build_site_snapshot_test_module")

    def test_main_builds_expected_stats_payload(self) -> None:
        stats = SiteStats(
            total_posts=1,
            total_comments=3,
            average_comments_per_post=3.0,
            average_words_per_post=42.0,
            posts_with_explicit_matchup=1,
            posts_by_year={"2025": 1},
            top_categories=[],
            most_commented_posts=[],
            last_post_update=datetime(2025, 1, 10, tzinfo=timezone.utc),
            crawl_completed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        )
        dataset = CrawlDataset(
            site_title="Movie Scene Battles",
            site_url="https://moviescenebattles.blogspot.com",
            posts=[
                BattlePost(
                    post_id="post-1",
                    title="Hero vs Villain",
                    url="https://moviescenebattles.blogspot.com/post-1",
                    published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    comment_count=3,
                    categories=["Action"],
                    word_count=42,
                    content_text=None,
                )
            ],
            stats=stats,
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with _cwd(root):
                with patch.object(self.module, "crawl_moviescenebattles", return_value=dataset) as crawl_mock:
                    with patch.object(self.module, "save_dataset") as save_mock:
                        self.module.main()

            crawl_mock.assert_called_once_with(max_posts=1000, include_content=False)
            save_mock.assert_called_once_with(dataset, Path("data/moviescenebattles_dataset.json"))

            site_stats_path = root / "data" / "site_stats.json"
            self.assertTrue(site_stats_path.exists())

            payload = json.loads(site_stats_path.read_text(encoding="utf-8"))
            expected_payload = {
                "site_title": dataset.site_title,
                "site_url": dataset.site_url,
                "generated_from_posts": len(dataset.posts),
                "stats": asdict(dataset.stats),
            }
            expected_json = json.loads(json.dumps(expected_payload, default=str))
            self.assertEqual(payload, expected_json)


if __name__ == "__main__":
    unittest.main()
