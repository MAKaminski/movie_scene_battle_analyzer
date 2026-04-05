import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import verify_site_snapshot as verify


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.json"
            with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
                verify._load_json(missing)

    def test_assert_required_dataset_shape_requires_required_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify._assert_required_dataset_shape({"site_title": "Movie Scene Battles"})

    def test_assert_required_stats_shape_requires_stats_object(self) -> None:
        payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 1,
            "stats": [],
        }
        with self.assertRaisesRegex(ValueError, "Site stats field `stats` must be an object"):
            verify._assert_required_stats_shape(payload)

    def test_main_passes_when_site_stats_matches_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}],
                "stats": {"total_posts": 1},
            }
            site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": 1,
                "stats": dataset["stats"],
            }

            _write_json(data_dir / "moviescenebattles_dataset.json", dataset)
            _write_json(data_dir / "site_stats.json", site_stats)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                verify.main()
            finally:
                os.chdir(original_cwd)

    def test_main_fails_when_site_stats_is_out_of_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}, {"post_id": "2"}],
                "stats": {"total_posts": 2},
            }
            stale_site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": 1,
                "stats": {"total_posts": 1},
            }

            _write_json(data_dir / "moviescenebattles_dataset.json", dataset)
            _write_json(data_dir / "site_stats.json", stale_site_stats)

            original_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify.main()
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
