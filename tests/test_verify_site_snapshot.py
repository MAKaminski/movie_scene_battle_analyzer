from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


def _load_verify_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load verify_site_snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_site_snapshot = _load_verify_module()


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
                verify_site_snapshot._load_json(missing)

    def test_dataset_shape_validation_rejects_bad_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape({"site_title": "x"})
        with self.assertRaisesRegex(ValueError, "must be a list"):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "x",
                    "site_url": "u",
                    "posts": {},
                    "stats": {},
                }
            )

    def test_site_stats_shape_validation_rejects_bad_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "Site stats missing keys"):
            verify_site_snapshot._assert_required_stats_shape({"site_title": "x"})
        with self.assertRaisesRegex(ValueError, "must be an object"):
            verify_site_snapshot._assert_required_stats_shape(
                {
                    "site_title": "x",
                    "site_url": "u",
                    "generated_from_posts": 1,
                    "stats": [],
                }
            )

    def test_main_passes_when_snapshot_matches_dataset(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"post_id": "1"}],
            "stats": {"total_posts": 1, "total_comments": 2},
        }
        site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 1,
            "stats": {"total_posts": 1, "total_comments": 2},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                verify_site_snapshot.main()
            finally:
                os.chdir(old_cwd)

    def test_main_raises_when_site_stats_out_of_sync(self) -> None:
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

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(mismatched_site_stats), encoding="utf-8"
            )

            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify_site_snapshot.main()
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
