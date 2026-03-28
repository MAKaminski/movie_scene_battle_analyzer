import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_site_snapshot.py"
_SPEC = importlib.util.spec_from_file_location("verify_site_snapshot", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
verify_site_snapshot = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify_site_snapshot)


@contextmanager
def working_directory(path: str):
    original = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


class VerifySiteSnapshotTests(unittest.TestCase):
    def test_load_json_missing_file_raises(self):
        with TemporaryDirectory() as temp_dir:
            missing_file = Path(temp_dir) / "does_not_exist.json"
            with self.assertRaises(FileNotFoundError):
                verify_site_snapshot._load_json(missing_file)

    def test_assert_required_dataset_shape_rejects_missing_keys(self):
        invalid_dataset = {"site_title": "Movie Scene Battles", "site_url": "https://example.com"}
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape(invalid_dataset)

    def test_assert_required_dataset_shape_rejects_wrong_types(self):
        invalid_dataset = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://example.com",
            "posts": {},
            "stats": [],
        }
        with self.assertRaisesRegex(ValueError, "posts"):
            verify_site_snapshot._assert_required_dataset_shape(invalid_dataset)

    def test_assert_required_stats_shape_rejects_missing_keys(self):
        invalid_site_stats = {"site_title": "Movie Scene Battles"}
        with self.assertRaisesRegex(ValueError, "Site stats missing keys"):
            verify_site_snapshot._assert_required_stats_shape(invalid_site_stats)

    def test_assert_required_stats_shape_rejects_wrong_stats_type(self):
        invalid_site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://example.com",
            "generated_from_posts": 1,
            "stats": [],
        }
        with self.assertRaisesRegex(ValueError, "Site stats field `stats` must be an object"):
            verify_site_snapshot._assert_required_stats_shape(invalid_site_stats)

    def test_main_passes_for_consistent_files(self):
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

        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            with working_directory(temp_dir):
                verify_site_snapshot.main()

    def test_main_rejects_out_of_sync_payload(self):
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

        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            with working_directory(temp_dir):
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify_site_snapshot.main()


if __name__ == "__main__":
    unittest.main()
