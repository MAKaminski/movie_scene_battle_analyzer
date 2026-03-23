from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def _load_verify_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load verify_site_snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_site_snapshot = _load_verify_module()


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
                verify_site_snapshot._load_json(missing_path)

    def test_assert_required_dataset_shape_rejects_missing_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "stats": {},
                }
            )

    def test_main_raises_when_snapshot_is_out_of_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"id": "1"}, {"id": "2"}],
                "stats": {"total_posts": 2},
            }
            stale_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 1,
                "stats": {"total_posts": 2},
            }

            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(stale_stats),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify_site_snapshot.main()
            finally:
                os.chdir(previous_cwd)

    def test_main_succeeds_with_matching_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"id": "1"}, {"id": "2"}],
                "stats": {"total_posts": 2},
            }
            stats_payload = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": len(dataset["posts"]),
                "stats": dataset["stats"],
            }

            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(stats_payload),
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch("builtins.print") as mock_print:
                    verify_site_snapshot.main()
                mock_print.assert_called_once_with("Snapshot validation passed.")
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
