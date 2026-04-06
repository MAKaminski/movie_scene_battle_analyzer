from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import call, patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost


class CrawlMoviesceneBattlesTests(unittest.TestCase):
    def test_extract_text_normalizes_whitespace_and_entities(self) -> None:
        html = "<p>Hello&nbsp;world</p>  <p>from <b>battle</b> analyzer</p>"
        self.assertEqual(crawler._extract_text(html), "Hello world from battle analyzer")

    def test_to_post_honors_include_content_flag(self) -> None:
        entry = {
            "id": {"$t": "post-123"},
            "title": {"$t": " Hero vs Villain "},
            "link": [
                {"rel": "related", "href": "https://example.com/related"},
                {"rel": "alternate", "href": "https://example.com/post-123"},
            ],
            "published": {"$t": "2025-01-02T03:04:05+00:00"},
            "updated": {"$t": "2025-01-03T03:04:05+00:00"},
            "thr$total": {"$t": "7"},
            "category": [{"term": "Action"}, {"term": "Drama"}, {"foo": "ignored"}],
            "content": {"$t": "<p>Hello&nbsp;world</p> <p>Again</p>"},
        }

        with_content = crawler._to_post(entry, include_content=True)
        without_content = crawler._to_post(entry, include_content=False)

        self.assertEqual(with_content.post_id, "post-123")
        self.assertEqual(with_content.title, "Hero vs Villain")
        self.assertEqual(with_content.url, "https://example.com/post-123")
        self.assertEqual(with_content.comment_count, 7)
        self.assertEqual(with_content.categories, ["Action", "Drama"])
        self.assertEqual(with_content.word_count, 3)
        self.assertEqual(with_content.content_text, "Hello world Again")
        self.assertIsNone(without_content.content_text)
        # Word count should still be computed even when content is omitted from output.
        self.assertEqual(without_content.word_count, 3)

    def test_build_stats_aggregates_and_tracks_latest_update(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Hero vs Villain",
                url="https://example.com/1",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                comment_count=10,
                categories=["Action", "Classic"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Detective versus Mastermind",
                url="https://example.com/2",
                published_at=datetime(2023, 5, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 2, 2, tzinfo=timezone.utc),
                comment_count=2,
                categories=["Drama", "Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="Comedy v Tragedy",
                url="https://example.com/3",
                published_at=datetime(2023, 8, 1, tzinfo=timezone.utc),
                updated_at=None,
                comment_count=5,
                categories=["Action"],
                word_count=150,
            ),
        ]

        stats = crawler._build_stats(posts)

        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 17)
        self.assertEqual(stats.average_comments_per_post, round(17 / 3, 2))
        self.assertEqual(stats.average_words_per_post, 100.0)
        self.assertEqual(stats.posts_with_explicit_matchup, 3)
        self.assertEqual(stats.posts_by_year, {"2023": 2, "2024": 1})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 3)
        self.assertEqual(stats.most_commented_posts[0].title, "Hero vs Villain")
        self.assertEqual(stats.most_commented_posts[0].comment_count, 10)
        self.assertEqual(stats.last_post_update, datetime(2024, 2, 2, tzinfo=timezone.utc))
        self.assertIsNotNone(stats.crawl_completed_at)

    def test_crawl_moviescenebattles_paginates_until_max_posts(self) -> None:
        page_one = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    {
                        "id": {"$t": "1"},
                        "title": {"$t": "A vs B"},
                        "thr$total": {"$t": "1"},
                        "content": {"$t": "Alpha"},
                    },
                    {
                        "id": {"$t": "2"},
                        "title": {"$t": "C vs D"},
                        "thr$total": {"$t": "2"},
                        "content": {"$t": "Beta"},
                    },
                ],
            }
        }
        page_two = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    {
                        "id": {"$t": "3"},
                        "title": {"$t": "E vs F"},
                        "thr$total": {"$t": "3"},
                        "content": {"$t": "Gamma"},
                    }
                ],
            }
        }

        with patch.object(crawler, "_fetch_feed_page", side_effect=[page_one, page_two]) as fetch_mock:
            dataset = crawler.crawl_moviescenebattles(max_posts=3, page_size=2, include_content=False)

        self.assertEqual(fetch_mock.call_args_list, [call(start_index=1, max_results=2, timeout=30), call(start_index=3, max_results=1, timeout=30)])
        self.assertEqual(dataset.site_title, "Movie Scene Battles")
        self.assertEqual(len(dataset.posts), 3)
        self.assertTrue(all(post.content_text is None for post in dataset.posts))
        self.assertEqual(dataset.stats.total_posts, 3)

    def test_crawl_moviescenebattles_validates_numeric_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=0)
        with self.assertRaisesRegex(ValueError, "page_size must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=1, page_size=0)


if __name__ == "__main__":
    unittest.main()
