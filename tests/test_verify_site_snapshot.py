from __future__ import annotations

import json
import os
import runpy
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
SCRIPT_GLOBALS = runpy.run_path(str(SCRIPT_PATH))

_load_json = SCRIPT_GLOBALS["_load_json"]
_assert_required_dataset_shape = SCRIPT_GLOBALS["_assert_required_dataset_shape"]
_assert_required_stats_shape = SCRIPT_GLOBALS["_assert_required_stats_shape"]
main = SCRIPT_GLOBALS["main"]


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self) -> None:
        missing_file = Path("does-not-exist.json")

        with self.assertRaises(FileNotFoundError):
            _load_json(missing_file)

    def test_assert_required_dataset_shape_rejects_missing_keys(self) -> None:
        with self.assertRaises(ValueError) as context:
            _assert_required_dataset_shape({"site_title": "Movie Scene Battles", "posts": []})

        self.assertIn("Dataset missing keys", str(context.exception))

    def test_assert_required_stats_shape_rejects_non_object_stats(self) -> None:
        payload = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 1,
            "stats": [],
        }

        with self.assertRaises(ValueError) as context:
            _assert_required_stats_shape(payload)

        self.assertEqual("Site stats field `stats` must be an object", str(context.exception))

    def test_main_accepts_consistent_snapshot_payload(self) -> None:
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"post_id": "1"}],
            "stats": {"total_posts": 1},
        }
        site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": len(dataset["posts"]),
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(site_stats),
                encoding="utf-8",
            )

            with _working_directory(Path(temp_dir)):
                main()

    def test_main_raises_when_site_stats_are_out_of_sync(self) -> None:
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
            "stats": dataset["stats"],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset),
                encoding="utf-8",
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(stale_site_stats),
                encoding="utf-8",
            )

            with _working_directory(Path(temp_dir)):
                with self.assertRaises(ValueError) as context:
                    main()

        self.assertIn("site_stats.json is out of sync", str(context.exception))


if __name__ == "__main__":
    unittest.main()
