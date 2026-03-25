import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_site_snapshot import validate_snapshot_files


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_validate_snapshot_files_passes_for_consistent_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset_path = base / "moviescenebattles_dataset.json"
            site_stats_path = base / "site_stats.json"
            dataset_payload = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "p1"}, {"post_id": "p2"}],
                "stats": {"total_posts": 2},
            }
            stats_payload = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 2,
                "stats": {"total_posts": 2},
            }
            _write_json(dataset_path, dataset_payload)
            _write_json(site_stats_path, stats_payload)

            validate_snapshot_files(dataset_path, site_stats_path)

    def test_validate_snapshot_files_raises_for_missing_dataset_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset_path = base / "missing_dataset.json"
            site_stats_path = base / "site_stats.json"
            _write_json(
                site_stats_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 0,
                    "stats": {},
                },
            )

            with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
                validate_snapshot_files(dataset_path, site_stats_path)

    def test_validate_snapshot_files_raises_for_dataset_shape_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset_path = base / "moviescenebattles_dataset.json"
            site_stats_path = base / "site_stats.json"
            _write_json(
                dataset_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": "not-a-list",
                    "stats": {},
                },
            )
            _write_json(
                site_stats_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 0,
                    "stats": {},
                },
            )

            with self.assertRaisesRegex(ValueError, "Dataset field `posts` must be a list"):
                validate_snapshot_files(dataset_path, site_stats_path)

    def test_validate_snapshot_files_raises_for_site_stats_shape_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset_path = base / "moviescenebattles_dataset.json"
            site_stats_path = base / "site_stats.json"
            _write_json(
                dataset_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": [],
                    "stats": {},
                },
            )
            _write_json(
                site_stats_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 0,
                    "stats": [],
                },
            )

            with self.assertRaisesRegex(ValueError, "Site stats field `stats` must be an object"):
                validate_snapshot_files(dataset_path, site_stats_path)

    def test_validate_snapshot_files_raises_for_out_of_sync_site_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dataset_path = base / "moviescenebattles_dataset.json"
            site_stats_path = base / "site_stats.json"
            _write_json(
                dataset_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": [{"post_id": "p1"}],
                    "stats": {"total_posts": 1},
                },
            )
            _write_json(
                site_stats_path,
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 999,
                    "stats": {"total_posts": 1},
                },
            )

            with self.assertRaisesRegex(ValueError, "out of sync"):
                validate_snapshot_files(dataset_path, site_stats_path)


if __name__ == "__main__":
    unittest.main()
