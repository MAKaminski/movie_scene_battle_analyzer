import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


def _load_verify_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load verify_site_snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def _temporary_cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class VerifySiteSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_verify_module()

    def test_load_json_raises_for_missing_file(self):
        missing = Path("/tmp/verify-site-snapshot-does-not-exist.json")
        with self.assertRaises(FileNotFoundError):
            self.module._load_json(missing)

    def test_assert_required_dataset_shape_missing_keys(self):
        with self.assertRaises(ValueError) as error:
            self.module._assert_required_dataset_shape({"site_title": "x"})
        self.assertIn("Dataset missing keys", str(error.exception))

    def test_assert_required_dataset_shape_rejects_wrong_types(self):
        with self.assertRaises(ValueError) as posts_error:
            self.module._assert_required_dataset_shape(
                {"site_title": "x", "site_url": "u", "posts": {}, "stats": {}}
            )
        self.assertEqual(str(posts_error.exception), "Dataset field `posts` must be a list")

        with self.assertRaises(ValueError) as stats_error:
            self.module._assert_required_dataset_shape(
                {"site_title": "x", "site_url": "u", "posts": [], "stats": []}
            )
        self.assertEqual(str(stats_error.exception), "Dataset field `stats` must be an object")

    def test_assert_required_stats_shape_rejects_missing_or_wrong_type(self):
        with self.assertRaises(ValueError) as missing_error:
            self.module._assert_required_stats_shape({"site_title": "x"})
        self.assertIn("Site stats missing keys", str(missing_error.exception))

        with self.assertRaises(ValueError) as type_error:
            self.module._assert_required_stats_shape(
                {"site_title": "x", "site_url": "u", "generated_from_posts": 1, "stats": []}
            )
        self.assertEqual(str(type_error.exception), "Site stats field `stats` must be an object")

    def test_main_raises_when_site_stats_out_of_sync(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}],
                "stats": {"total_posts": 1},
            }
            stale_site_stats = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 1,
                "stats": {"total_posts": 999},
            }
            _write_json(base / "data/moviescenebattles_dataset.json", dataset)
            _write_json(base / "data/site_stats.json", stale_site_stats)

            with _temporary_cwd(base):
                with self.assertRaises(ValueError) as error:
                    self.module.main()
            self.assertIn("out of sync", str(error.exception))

    def test_main_passes_for_matching_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            dataset = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}, {"post_id": "2"}],
                "stats": {"total_posts": 2},
            }
            expected_site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": len(dataset["posts"]),
                "stats": dataset["stats"],
            }
            _write_json(base / "data/moviescenebattles_dataset.json", dataset)
            _write_json(base / "data/site_stats.json", expected_site_stats)

            output = io.StringIO()
            with _temporary_cwd(base):
                with contextlib.redirect_stdout(output):
                    self.module.main()

            self.assertIn("Snapshot validation passed.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
