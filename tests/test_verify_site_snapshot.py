import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import scripts.verify_site_snapshot as verify_site_snapshot


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_assert_required_dataset_shape_rejects_missing_keys(self) -> None:
        with self.assertRaisesRegex(
            ValueError, r"Dataset missing keys: \['posts', 'stats'\]"
        ):
            verify_site_snapshot._assert_required_dataset_shape(
                {"site_title": "Movie Scene Battles", "site_url": "https://example.com"}
            )

    def test_assert_required_dataset_shape_rejects_invalid_posts_type(self) -> None:
        with self.assertRaisesRegex(
            ValueError, r"Dataset field `posts` must be a list"
        ):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.com",
                    "posts": {},
                    "stats": {},
                }
            )

    def test_assert_required_stats_shape_rejects_invalid_stats_type(self) -> None:
        with self.assertRaisesRegex(
            ValueError, r"Site stats field `stats` must be an object"
        ):
            verify_site_snapshot._assert_required_stats_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.com",
                    "generated_from_posts": 1,
                    "stats": [],
                }
            )

    def test_main_accepts_synced_snapshot_payloads(self) -> None:
        dataset_payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "post-1"}],
            "stats": {"total_posts": 1},
        }
        stats_payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 1,
            "stats": {"total_posts": 1},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset_payload), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(stats_payload), encoding="utf-8"
            )

            current_cwd = os.getcwd()
            try:
                os.chdir(base)
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    verify_site_snapshot.main()
                self.assertIn("Snapshot validation passed.", stdout.getvalue())
            finally:
                os.chdir(current_cwd)

    def test_main_rejects_out_of_sync_stats_payload(self) -> None:
        dataset_payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"id": "post-1"}],
            "stats": {"total_posts": 1},
        }
        out_of_sync_stats_payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 999,
            "stats": {"total_posts": 1},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            data_dir = base / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset_payload), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(out_of_sync_stats_payload), encoding="utf-8"
            )

            current_cwd = os.getcwd()
            try:
                os.chdir(base)
                with self.assertRaisesRegex(
                    ValueError, r"site_stats\.json is out of sync"
                ):
                    verify_site_snapshot.main()
            finally:
                os.chdir(current_cwd)


if __name__ == "__main__":
    unittest.main()
