import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import verify_site_snapshot as verify_snapshot


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_assert_required_dataset_shape_rejects_missing_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, r"Dataset missing keys: \['posts', 'stats'\]"):
            verify_snapshot._assert_required_dataset_shape(
                {"site_title": "Movie Scene Battles", "site_url": "https://example.test"}
            )

    def test_assert_required_dataset_shape_rejects_invalid_types(self) -> None:
        with self.assertRaisesRegex(ValueError, r"Dataset field `posts` must be a list"):
            verify_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.test",
                    "posts": {},
                    "stats": {},
                }
            )

        with self.assertRaisesRegex(ValueError, r"Dataset field `stats` must be an object"):
            verify_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.test",
                    "posts": [],
                    "stats": [],
                }
            )

    def test_assert_required_stats_shape_rejects_invalid_payload(self) -> None:
        with self.assertRaisesRegex(
            ValueError, r"Site stats missing keys: \['generated_from_posts', 'stats'\]"
        ):
            verify_snapshot._assert_required_stats_shape(
                {"site_title": "Movie Scene Battles", "site_url": "https://example.test"}
            )

        with self.assertRaisesRegex(ValueError, r"Site stats field `stats` must be an object"):
            verify_snapshot._assert_required_stats_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.test",
                    "generated_from_posts": 1,
                    "stats": [],
                }
            )

    def test_main_passes_when_snapshot_matches_dataset(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://example.test",
            "posts": [{"id": 1}, {"id": 2}],
            "stats": {"total_posts": 2},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": len(dataset["posts"]),
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_snapshot_files(Path(tmpdir), dataset, site_stats)
            self._run_main_in_directory(tmpdir)

    def test_main_raises_when_site_stats_is_out_of_sync(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://example.test",
            "posts": [{"id": 1}],
            "stats": {"total_posts": 1},
        }
        stale_site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 999,
            "stats": {"total_posts": 999},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_snapshot_files(Path(tmpdir), dataset, stale_site_stats)
            with self.assertRaisesRegex(
                ValueError,
                r"site_stats\.json is out of sync with moviescenebattles_dataset\.json",
            ):
                self._run_main_in_directory(tmpdir)

    def _write_snapshot_files(self, root: Path, dataset: dict, site_stats: dict) -> None:
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "moviescenebattles_dataset.json").write_text(
            json.dumps(dataset), encoding="utf-8"
        )
        (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

    def _run_main_in_directory(self, tmpdir: str) -> None:
        previous_dir = os.getcwd()
        os.chdir(tmpdir)
        try:
            verify_snapshot.main()
        finally:
            os.chdir(previous_dir)


if __name__ == "__main__":
    unittest.main()
