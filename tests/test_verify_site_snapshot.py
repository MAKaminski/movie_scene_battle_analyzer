from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import verify_site_snapshot


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self) -> None:
        missing_path = Path("definitely_missing_snapshot_file.json")

        with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
            verify_site_snapshot._load_json(missing_path)

    def test_assert_required_dataset_shape_rejects_wrong_posts_type(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": {},
            "stats": {},
        }

        with self.assertRaisesRegex(ValueError, "Dataset field `posts` must be a list"):
            verify_site_snapshot._assert_required_dataset_shape(dataset)

    def test_assert_required_stats_shape_rejects_missing_keys(self) -> None:
        site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "stats": {},
        }

        with self.assertRaisesRegex(ValueError, r"Site stats missing keys: \['generated_from_posts'\]"):
            verify_site_snapshot._assert_required_stats_shape(site_stats)

    def test_main_passes_when_site_stats_matches_dataset(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "1"}, {"id": "2"}],
            "stats": {"total_posts": 2, "total_comments": 8},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 2,
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                data_dir = Path("data")
                data_dir.mkdir()
                (data_dir / "moviescenebattles_dataset.json").write_text(
                    json.dumps(dataset), encoding="utf-8"
                )
                (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

                output = io.StringIO()
                with redirect_stdout(output):
                    verify_site_snapshot.main()

                self.assertIn("Snapshot validation passed.", output.getvalue())
            finally:
                os.chdir(cwd)

    def test_main_raises_when_site_stats_is_out_of_sync(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "1"}, {"id": "2"}],
            "stats": {"total_posts": 2, "total_comments": 8},
        }
        out_of_sync_site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 1,
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                data_dir = Path("data")
                data_dir.mkdir()
                (data_dir / "moviescenebattles_dataset.json").write_text(
                    json.dumps(dataset), encoding="utf-8"
                )
                (data_dir / "site_stats.json").write_text(
                    json.dumps(out_of_sync_site_stats), encoding="utf-8"
                )

                with self.assertRaisesRegex(ValueError, "site_stats.json is out of sync"):
                    verify_site_snapshot.main()
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
