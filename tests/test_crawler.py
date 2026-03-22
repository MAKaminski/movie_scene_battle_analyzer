from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import _build_stats, crawl_moviescenebattles
from movie_scene_battle_analyzer.models import BattlePost


def _iso(index: int) -> str:
    return f"2024-01-{index:02d}T12:00:00+00:00"


def _make_feed_entry(index: int, *, title: str | None = None, comments: int = 0) -> dict:
    post_title = title or f"Scene {index} vs Scene {index + 1}"
    return {
        "id": {"$t": f"post-{index}"},
        "title": {"$t": post_title},
        "content": {"$t": f"<p>Entry {index} body text</p>"},
        "published": {"$t": _iso(index)},
        "updated": {"$t": _iso(index)},
        "thr$total": {"$t": str(comments)},
        "category": [{"term": "Action"}],
        "link": [{"rel": "alternate", "href": f"https://example.test/posts/{index}"}],
    }


class CrawlMovieSceneBattlesTests(unittest.TestCase):
    def test_rejects_non_positive_max_posts_and_page_size(self) -> None:
        with self.assertRaisesRegex(ValueError, r"max_posts must be greater than 0"):
            crawl_moviescenebattles(max_posts=0)

        with self.assertRaisesRegex(ValueError, r"page_size must be greater than 0"):
            crawl_moviescenebattles(page_size=0)

    def test_paginates_until_max_posts_without_network_calls(self) -> None:
        calls: list[tuple[int, int, int]] = []

        def fake_fetch(start_index: int, max_results: int, timeout: int) -> dict:
            calls.append((start_index, max_results, timeout))
            entries = [_make_feed_entry(start_index + i, comments=10 + i) for i in range(max_results)]
            return {"feed": {"title": {"$t": "Test Scene Battles"}, "entry": entries}}

        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=fake_fetch):
            dataset = crawl_moviescenebattles(max_posts=3, page_size=2, include_content=False, timeout=17)

        self.assertEqual(dataset.site_title, "Test Scene Battles")
        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual(calls, [(1, 2, 17), (3, 1, 17)])
        self.assertTrue(all(post.content_text is None for post in dataset.posts))

    def test_stops_crawling_when_feed_returns_empty_page(self) -> None:
        calls: list[tuple[int, int, int]] = []

        def fake_fetch(start_index: int, max_results: int, timeout: int) -> dict:
            calls.append((start_index, max_results, timeout))
            if start_index == 1:
                return {
                    "feed": {
                        "title": {"$t": "Movie Scene Battles"},
                        "entry": [_make_feed_entry(1), _make_feed_entry(2)],
                    }
                }
            return {"feed": {"title": {"$t": "Movie Scene Battles"}, "entry": []}}

        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=fake_fetch):
            dataset = crawl_moviescenebattles(max_posts=10, page_size=2)

        self.assertEqual(len(dataset.posts), 2)
        self.assertEqual(calls, [(1, 2, 30), (3, 2, 30)])


class BuildStatsTests(unittest.TestCase):
    def test_build_stats_tracks_matchups_averages_and_top_lists(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Neo vs Smith",
                url="https://example.test/1",
                published_at=datetime(2023, 5, 1, tzinfo=timezone.utc),
                updated_at=datetime(2023, 5, 5, tzinfo=timezone.utc),
                comment_count=50,
                categories=["Sci-Fi", "Action"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Batman v Joker",
                url="https://example.test/2",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                comment_count=20,
                categories=["Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="Best Opening Monologue",
                url="https://example.test/3",
                published_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 2, 10, tzinfo=timezone.utc),
                comment_count=5,
                categories=["Drama"],
                word_count=40,
            ),
        ]

        stats = _build_stats(posts)

        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 75)
        self.assertEqual(stats.average_comments_per_post, 25.0)
        self.assertEqual(stats.average_words_per_post, 63.33)
        self.assertEqual(stats.posts_with_explicit_matchup, 2)
        self.assertEqual(stats.posts_by_year, {"2023": 1, "2024": 2})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual(
            [post.title for post in stats.most_commented_posts],
            ["Neo vs Smith", "Batman v Joker", "Best Opening Monologue"],
        )
        self.assertEqual(stats.last_post_update, datetime(2024, 2, 10, tzinfo=timezone.utc))
        self.assertIsNotNone(stats.crawl_completed_at)

    def test_build_stats_handles_empty_post_lists(self) -> None:
        stats = _build_stats([])

        self.assertEqual(stats.total_posts, 0)
        self.assertEqual(stats.total_comments, 0)
        self.assertEqual(stats.average_comments_per_post, 0.0)
        self.assertEqual(stats.average_words_per_post, 0.0)
        self.assertEqual(stats.posts_with_explicit_matchup, 0)
        self.assertEqual(stats.posts_by_year, {})
        self.assertEqual(stats.top_categories, [])
        self.assertEqual(stats.most_commented_posts, [])
        self.assertIsNone(stats.last_post_update)
        self.assertIsNotNone(stats.crawl_completed_at)


if __name__ == "__main__":
    unittest.main()
