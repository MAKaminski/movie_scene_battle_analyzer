from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.verify_site_snapshot import (
    _assert_required_dataset_shape,
    _assert_required_stats_shape,
    _load_json,
    main,
)


class VerifySnapshotHelpersTests(unittest.TestCase):
    def test_load_json_requires_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "missing.json"
            with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
                _load_json(missing)

    def test_dataset_shape_validation_catches_missing_and_bad_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            _assert_required_dataset_shape({"site_title": "x"})
        with self.assertRaisesRegex(ValueError, "posts"):
            _assert_required_dataset_shape(
                {"site_title": "x", "site_url": "u", "posts": {}, "stats": {}}
            )
        with self.assertRaisesRegex(ValueError, "stats"):
            _assert_required_dataset_shape(
                {"site_title": "x", "site_url": "u", "posts": [], "stats": []}
            )

    def test_site_stats_shape_validation_catches_missing_and_bad_types(self) -> None:
        with self.assertRaisesRegex(ValueError, "Site stats missing keys"):
            _assert_required_stats_shape({"site_title": "x"})
        with self.assertRaisesRegex(ValueError, "stats"):
            _assert_required_stats_shape(
                {"site_title": "x", "site_url": "u", "generated_from_posts": 0, "stats": []}
            )


class VerifySnapshotMainTests(unittest.TestCase):
    def _write_snapshot_files(self, root: Path, *, site_stats_payload: dict) -> None:
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        dataset_payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"post_id": "1"}, {"post_id": "2"}],
            "stats": {"total_posts": 2},
        }
        (data_dir / "moviescenebattles_dataset.json").write_text(
            json.dumps(dataset_payload), encoding="utf-8"
        )
        (data_dir / "site_stats.json").write_text(
            json.dumps(site_stats_payload), encoding="utf-8"
        )

    def test_main_accepts_synced_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            synced_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 2,
                "stats": {"total_posts": 2},
            }
            self._write_snapshot_files(root, site_stats_payload=synced_stats)

            original_cwd = Path.cwd()
            try:
                os.chdir(root)
                main()
            finally:
                os.chdir(original_cwd)

    def test_main_rejects_out_of_sync_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            out_of_sync_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 1,
                "stats": {"total_posts": 1},
            }
            self._write_snapshot_files(root, site_stats_payload=out_of_sync_stats)

            original_cwd = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    main()
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
