import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import verify_site_snapshot


class VerifySiteSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp_dir.cleanup)
        self.temp_path = Path(self._temp_dir.name)

    @contextlib.contextmanager
    def _within_temp_repo(self):
        original_cwd = Path.cwd()
        os.chdir(self.temp_path)
        try:
            yield
        finally:
            os.chdir(original_cwd)

    def _write_snapshot_files(self, dataset: dict, site_stats: dict) -> None:
        data_dir = self.temp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "moviescenebattles_dataset.json").write_text(
            json.dumps(dataset),
            encoding="utf-8",
        )
        (data_dir / "site_stats.json").write_text(
            json.dumps(site_stats),
            encoding="utf-8",
        )

    def test_main_passes_for_matching_payloads(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"post_id": "1"}, {"post_id": "2"}],
            "stats": {"total_posts": 2},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 2,
            "stats": dataset["stats"],
        }
        self._write_snapshot_files(dataset, site_stats)

        with self._within_temp_repo(), io.StringIO() as stdout, contextlib.redirect_stdout(stdout):
            verify_site_snapshot.main()
            self.assertIn("Snapshot validation passed.", stdout.getvalue())

    def test_main_raises_when_site_stats_out_of_sync(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"post_id": "1"}, {"post_id": "2"}],
            "stats": {"total_posts": 2},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 1,
            "stats": dataset["stats"],
        }
        self._write_snapshot_files(dataset, site_stats)

        with self._within_temp_repo():
            with self.assertRaisesRegex(ValueError, "out of sync"):
                verify_site_snapshot.main()

    def test_main_rejects_dataset_with_non_list_posts(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": {},
            "stats": {"total_posts": 2},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 0,
            "stats": dataset["stats"],
        }
        self._write_snapshot_files(dataset, site_stats)

        with self._within_temp_repo():
            with self.assertRaisesRegex(ValueError, r"`posts` must be a list"):
                verify_site_snapshot.main()

    def test_main_rejects_site_stats_with_missing_keys(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [],
            "stats": {"total_posts": 0},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 0,
        }
        self._write_snapshot_files(dataset, site_stats)

        with self._within_temp_repo():
            with self.assertRaisesRegex(ValueError, "Site stats missing keys"):
                verify_site_snapshot.main()


if __name__ == "__main__":
    unittest.main()
