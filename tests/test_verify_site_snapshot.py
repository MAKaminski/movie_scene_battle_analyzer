from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_verify_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_site_snapshot.py"
    spec = importlib.util.spec_from_file_location("verify_site_snapshot", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load verify_site_snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_site_snapshot = _load_verify_module()


class VerifySnapshotShapeTests(unittest.TestCase):
    def test_dataset_shape_validation_rejects_missing_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape(
                {"site_title": "Movie Scene Battles", "site_url": "https://example.invalid"}
            )

    def test_stats_shape_validation_rejects_non_object_stats(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be an object"):
            verify_site_snapshot._assert_required_stats_shape(
                {
                    "site_title": "Movie Scene Battles",
                    "site_url": "https://example.invalid",
                    "generated_from_posts": 1,
                    "stats": [],
                }
            )


class VerifySnapshotConsistencyTests(unittest.TestCase):
    def test_main_raises_when_site_stats_are_out_of_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset_payload = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "posts": [{"post_id": "1"}],
                "stats": {"total_posts": 1},
            }
            # generated_from_posts intentionally mismatched to trigger guardrail.
            site_stats_payload = {
                "site_title": "Movie Scene Battles",
                "site_url": "https://moviescenebattles.blogspot.com",
                "generated_from_posts": 99,
                "stats": {"total_posts": 1},
            }

            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset_payload), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats_payload), encoding="utf-8")

            previous_cwd = Path.cwd()
            try:
                # main() uses relative data paths; run it in an isolated temp tree.
                import os

                os.chdir(root)
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify_site_snapshot.main()
            finally:
                os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
