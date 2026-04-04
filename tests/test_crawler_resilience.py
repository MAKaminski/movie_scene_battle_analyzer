from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import crawl_moviescenebattles


def _entry(post_id: str, title: str = "Scene A vs Scene B") -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "link": [{"rel": "alternate", "href": f"https://example.com/{post_id}"}],
        "published": {"$t": "2026-03-01T00:00:00+00:00"},
        "updated": {"$t": "2026-03-01T00:00:00+00:00"},
        "thr$total": {"$t": "0"},
        "category": [{"term": "Action"}],
        "content": {"$t": "<p>battle content</p>"},
    }


class CrawlResilienceTests(unittest.TestCase):
    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_raises_when_first_page_has_no_entries_but_total_results_present(self, mock_fetch) -> None:
        mock_fetch.return_value = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "openSearch$totalResults": {"$t": "218"},
                "entry": [],
            }
        }

        with self.assertRaisesRegex(RuntimeError, "no entries on first page"):
            crawl_moviescenebattles(max_posts=50, page_size=25)

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_raises_when_feed_truncates_before_reported_total(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "5"},
                    "entry": [_entry("1"), _entry("2"), _entry("3")],
                }
            },
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "5"},
                    "entry": [],
                }
            },
        ]

        with self.assertRaisesRegex(RuntimeError, "ended unexpectedly"):
            crawl_moviescenebattles(max_posts=5, page_size=3)

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_successful_multipage_crawl_still_works(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [_entry("1"), _entry("2"), _entry("3")],
                }
            },
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "4"},
                    "entry": [_entry("4")],
                }
            },
        ]

        dataset = crawl_moviescenebattles(max_posts=4, page_size=3)
        self.assertEqual(len(dataset.posts), 4)
        self.assertEqual(dataset.stats.total_posts, 4)
        self.assertEqual(dataset.site_title, "Movie Scene Battles")
        self.assertIsInstance(dataset.stats.crawl_completed_at, datetime)


if __name__ == "__main__":
    unittest.main()
