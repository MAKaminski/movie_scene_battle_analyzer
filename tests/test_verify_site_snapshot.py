from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import verify_site_snapshot


def _valid_dataset() -> dict:
    return {
        "site_title": "Movie Scene Battles",
        "site_url": "https://moviescenebattles.blogspot.com",
        "posts": [{"post_id": "a"}],
        "stats": {"total_posts": 1},
    }


class VerifySiteSnapshotHelpersTests(TestCase):
    def test_load_json_raises_when_file_missing(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Missing required file"):
            verify_site_snapshot._load_json(Path("/tmp/does-not-exist.json"))

    def test_required_dataset_shape_validation(self) -> None:
        dataset = _valid_dataset()
        verify_site_snapshot._assert_required_dataset_shape(dataset)

        invalid = dict(dataset)
        invalid.pop("stats")
        with self.assertRaisesRegex(ValueError, "Dataset missing keys"):
            verify_site_snapshot._assert_required_dataset_shape(invalid)

    def test_required_stats_shape_validation(self) -> None:
        site_stats = {
            "site_title": "Movie Scene Battles",
            "site_url": "https://moviescenebattles.blogspot.com",
            "generated_from_posts": 1,
            "stats": {"total_posts": 1},
        }
        verify_site_snapshot._assert_required_stats_shape(site_stats)

        invalid = dict(site_stats)
        invalid["stats"] = []
        with self.assertRaisesRegex(ValueError, "must be an object"):
            verify_site_snapshot._assert_required_stats_shape(invalid)


class VerifySiteSnapshotMainTests(TestCase):
    def test_main_passes_when_payloads_match(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = _valid_dataset()
            site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": len(dataset["posts"]),
                "stats": dataset["stats"],
            }
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(json.dumps(site_stats), encoding="utf-8")

            with patch.object(verify_site_snapshot, "Path", side_effect=lambda p: root / p):
                verify_site_snapshot.main()

    def test_main_raises_when_stats_out_of_sync(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            dataset = _valid_dataset()
            mismatched_site_stats = {
                "site_title": dataset["site_title"],
                "site_url": dataset["site_url"],
                "generated_from_posts": 999,
                "stats": dataset["stats"],
            }
            (data_dir / "moviescenebattles_dataset.json").write_text(
                json.dumps(dataset), encoding="utf-8"
            )
            (data_dir / "site_stats.json").write_text(
                json.dumps(mismatched_site_stats), encoding="utf-8"
            )

            with patch.object(verify_site_snapshot, "Path", side_effect=lambda p: root / p):
                with self.assertRaisesRegex(ValueError, "out of sync"):
                    verify_site_snapshot.main()
