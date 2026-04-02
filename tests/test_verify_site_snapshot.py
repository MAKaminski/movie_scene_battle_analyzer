from __future__ import annotations

import importlib.util
import io
import json
import os
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


def _load_verify_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_site_snapshot = _load_verify_module()


@contextmanager
def _temporary_cwd(path: str):
    original_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_cwd)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_raises_for_missing_file(self):
        missing_path = Path("does-not-exist.json")

        with self.assertRaises(FileNotFoundError):
            verify_site_snapshot._load_json(missing_path)

    def test_assert_required_dataset_shape_rejects_missing_and_invalid_types(self):
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape(
                {"site_title": "Movie Scene Battles"}
            )

        with self.assertRaisesRegex(ValueError, "posts` must be a list"):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": "not-a-list",
                    "stats": {},
                }
            )

        with self.assertRaisesRegex(ValueError, "stats` must be an object"):
            verify_site_snapshot._assert_required_dataset_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "posts": [],
                    "stats": [],
                }
            )

    def test_assert_required_stats_shape_rejects_missing_and_invalid_types(self):
        with self.assertRaisesRegex(ValueError, "Site stats missing keys"):
            verify_site_snapshot._assert_required_stats_shape(
                {"site_title": "Movie Scene Battles"}
            )

        with self.assertRaisesRegex(ValueError, "stats` must be an object"):
            verify_site_snapshot._assert_required_stats_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://moviescenebattles.blogspot.com",
                    "generated_from_posts": 1,
                    "stats": [],
                }
            )

    def test_main_passes_when_dataset_and_stats_are_consistent(self):
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"title": "A vs B"}, {"title": "C vs D"}],
            "stats": {"total_posts": 2, "average_comments_per_post": 1.5},
        }
        expected_site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": len(dataset["posts"]),
            "stats": dataset["stats"],
        }

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            _write_json(temp_root / "data" / "moviescenebattles_dataset.json", dataset)
            _write_json(temp_root / "data" / "site_stats.json", expected_site_stats)

            output = io.StringIO()
            with _temporary_cwd(temp_dir), redirect_stdout(output):
                verify_site_snapshot.main()

        self.assertIn("Snapshot validation passed.", output.getvalue())

    def test_main_fails_when_stats_are_out_of_sync(self):
        dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "posts": [{"title": "A vs B"}, {"title": "C vs D"}],
            "stats": {"total_posts": 2, "average_comments_per_post": 1.5},
        }
        out_of_sync_site_stats = {
            "site_title": dataset["site_title"],
            "site_url": dataset["site_url"],
            "generated_from_posts": 1,
            "stats": dataset["stats"],
        }

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            _write_json(temp_root / "data" / "moviescenebattles_dataset.json", dataset)
            _write_json(temp_root / "data" / "site_stats.json", out_of_sync_site_stats)

            with _temporary_cwd(temp_dir), self.assertRaisesRegex(
                ValueError,
                "out of sync",
            ):
                verify_site_snapshot.main()


if __name__ == "__main__":
    unittest.main()
