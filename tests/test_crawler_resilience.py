from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import crawl_moviescenebattles


def _entry(post_id: int) -> dict:
    return {
        "id": {"$t": f"post-{post_id}"},
        "title": {"$t": f"Battle {post_id}"},
        "link": [{"rel": "alternate", "href": f"https://example.com/{post_id}"}],
        "published": {"$t": "2026-01-01T00:00:00+00:00"},
        "updated": {"$t": "2026-01-01T00:00:00+00:00"},
        "thr$total": {"$t": "0"},
        "category": [],
    }


class CrawlResilienceTests(unittest.TestCase):
    def test_raises_when_feed_reports_posts_but_returns_none(self) -> None:
        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            return_value={"feed": {"openSearch$totalResults": {"$t": "10"}, "entry": []}},
        ):
            with self.assertRaises(RuntimeError):
                crawl_moviescenebattles(max_posts=5)

    def test_raises_on_early_termination_before_reported_total(self) -> None:
        responses = [
            {
                "feed": {
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [_entry(1), _entry(2)],
                    "title": {"$t": "Movie Scene Battles"},
                }
            },
            {
                "feed": {
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [],
                    "title": {"$t": "Movie Scene Battles"},
                }
            },
        ]
        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=responses):
            with self.assertRaises(RuntimeError):
                crawl_moviescenebattles(max_posts=10, page_size=2)

    def test_successful_multi_page_crawl_still_works(self) -> None:
        responses = [
            {
                "feed": {
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [_entry(1), _entry(2)],
                    "title": {"$t": "Movie Scene Battles"},
                }
            },
            {
                "feed": {
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [_entry(3), _entry(4)],
                    "title": {"$t": "Movie Scene Battles"},
                }
            },
            {
                "feed": {
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [],
                    "title": {"$t": "Movie Scene Battles"},
                }
            },
        ]
        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=responses):
            dataset = crawl_moviescenebattles(max_posts=10, page_size=2)
        self.assertEqual(4, len(dataset.posts))


if __name__ == "__main__":
    unittest.main()
