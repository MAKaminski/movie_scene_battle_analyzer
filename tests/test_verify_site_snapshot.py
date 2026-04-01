import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


def _load_verify_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class VerifySiteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.verify_module = _load_verify_module()

    def test_main_passes_for_consistent_snapshot_payloads(self):
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "1"}, {"id": "2"}],
            "stats": {"total_posts": 2},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 2,
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                self.verify_module.main()
            finally:
                os.chdir(original_cwd)

    def test_main_raises_when_site_stats_is_out_of_sync(self):
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "1"}],
            "stats": {"total_posts": 1},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 999,
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_dir = Path(tmp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                with self.assertRaises(ValueError) as ctx:
                    self.verify_module.main()
                self.assertIn("out of sync", str(ctx.exception))
            finally:
                os.chdir(original_cwd)

    def test_dataset_shape_validation_rejects_missing_required_keys(self):
        with self.assertRaises(ValueError) as ctx:
            self.verify_module._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": [],
                }
            )
        self.assertIn("Dataset missing keys", str(ctx.exception))

    def test_stats_shape_validation_rejects_non_object_stats_field(self):
        with self.assertRaises(ValueError) as ctx:
            self.verify_module._assert_required_stats_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 10,
                    "stats": [],
                }
            )
        self.assertIn("must be an object", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
