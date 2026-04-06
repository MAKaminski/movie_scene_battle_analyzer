from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import crawl_moviescenebattles


def _make_entry(entry_id: str, title: str) -> dict:
    return {
        "id": {"$t": entry_id},
        "title": {"$t": title},
        "link": [{"rel": "alternate", "href": f"https://example.com/{entry_id}"}],
        "published": {"$t": "2026-01-01T00:00:00+00:00"},
        "updated": {"$t": "2026-01-02T00:00:00+00:00"},
        "thr$total": {"$t": "5"},
        "category": [{"term": "Battle"}],
        "content": {"$t": "<p>Sample content words here</p>"},
    }


class CrawlResilienceTests(unittest.TestCase):
    def test_raises_when_first_page_empty_but_feed_reports_posts(self) -> None:
        def fake_fetch_feed_page(start_index: int, max_results: int, timeout: int) -> dict:
            self.assertEqual(start_index, 1)
            return {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "25"},
                    "entry": [],
                }
            }

        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            side_effect=fake_fetch_feed_page,
        ):
            with self.assertRaisesRegex(RuntimeError, "partial dataset"):
                crawl_moviescenebattles(max_posts=10, include_content=False)

    def test_raises_when_pagination_truncates_before_reported_total(self) -> None:
        calls = 0

        def fake_fetch_feed_page(start_index: int, max_results: int, timeout: int) -> dict:
            nonlocal calls
            calls += 1
            if calls == 1:
                self.assertEqual(start_index, 1)
                return {
                    "feed": {
                        "title": {"$t": "Movie Scene Battles"},
                        "openSearch$totalResults": {"$t": "12"},
                        "entry": [_make_entry("post-1", "A vs B"), _make_entry("post-2", "C vs D")],
                    }
                }
            if calls == 2:
                self.assertEqual(start_index, 3)
                return {
                    "feed": {
                        "title": {"$t": "Movie Scene Battles"},
                        "openSearch$totalResults": {"$t": "12"},
                        "entry": [],
                    }
                }
            raise AssertionError("unexpected extra pagination request")

        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            side_effect=fake_fetch_feed_page,
        ):
            with self.assertRaisesRegex(RuntimeError, "partial dataset"):
                crawl_moviescenebattles(max_posts=12, include_content=False, page_size=2)

    def test_returns_posts_for_healthy_multipage_feed(self) -> None:
        pages = {
            1: {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "3"},
                    "entry": [_make_entry("post-1", "A vs B"), _make_entry("post-2", "C vs D")],
                }
            },
            3: {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "openSearch$totalResults": {"$t": "3"},
                    "entry": [_make_entry("post-3", "E vs F")],
                }
            },
        }

        def fake_fetch_feed_page(start_index: int, max_results: int, timeout: int) -> dict:
            return pages[start_index]

        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            side_effect=fake_fetch_feed_page,
        ):
            dataset = crawl_moviescenebattles(max_posts=3, include_content=False, page_size=2)

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual(dataset.stats.total_posts, 3)


if __name__ == "__main__":
    unittest.main()
