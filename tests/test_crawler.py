from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import _build_stats, _to_post, crawl_moviescenebattles
from movie_scene_battle_analyzer.models import BattlePost


def _entry(
    *,
    entry_id: str = "post-1",
    title: str = "Hero vs Villain",
    permalink: str = "https://example.com/post-1",
    published: str = "2024-01-01T10:00:00+00:00",
    updated: str = "2024-01-02T11:00:00+00:00",
    comments: str = "3",
    categories: list[str] | None = None,
    content_html: str = "<p>One <b>two</b> three</p>",
) -> dict:
    categories = categories or ["Action"]
    return {
        "id": {"$t": entry_id},
        "title": {"$t": title},
        "link": [{"rel": "alternate", "href": permalink}],
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": comments},
        "category": [{"term": category} for category in categories],
        "content": {"$t": content_html},
    }


class ToPostTests(TestCase):
    def test_to_post_extracts_expected_fields_and_word_count(self) -> None:
        post = _to_post(_entry(), include_content=False)

        self.assertEqual(post.post_id, "post-1")
        self.assertEqual(post.title, "Hero vs Villain")
        self.assertEqual(post.url, "https://example.com/post-1")
        self.assertEqual(post.comment_count, 3)
        self.assertEqual(post.categories, ["Action"])
        self.assertEqual(post.word_count, 3)
        self.assertIsNone(post.content_text)

    def test_to_post_handles_invalid_dates_missing_permalink_and_include_content(self) -> None:
        entry = _entry(
            permalink="",
            published="not-a-date",
            updated="also-bad",
            categories=["Drama", "Classic"],
            content_html="<div>alpha&nbsp; beta</div>",
        )
        entry["link"] = [{"rel": "self", "href": "https://example.com/self"}]

        post = _to_post(entry, include_content=True)

        self.assertEqual(post.url, "")
        self.assertIsNone(post.published_at)
        self.assertIsNone(post.updated_at)
        self.assertEqual(post.content_text, "alpha beta")
        self.assertEqual(post.word_count, 2)
        self.assertEqual(post.categories, ["Drama", "Classic"])


class BuildStatsTests(TestCase):
    def test_build_stats_aggregates_categories_years_matchups_and_comments(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Neo vs Agent Smith",
                url="https://example.com/1",
                published_at=datetime(2023, 6, 1, tzinfo=timezone.utc),
                updated_at=datetime(2023, 6, 2, tzinfo=timezone.utc),
                comment_count=10,
                categories=["Action", "Sci-Fi"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Final showdown",
                url="https://example.com/2",
                published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 16, tzinfo=timezone.utc),
                comment_count=2,
                categories=["Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="Batman versus Joker",
                url="https://example.com/3",
                published_at=None,
                updated_at=None,
                comment_count=6,
                categories=["Comic"],
                word_count=70,
            ),
        ]

        stats = _build_stats(posts)

        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 18)
        self.assertEqual(stats.average_comments_per_post, 6.0)
        self.assertEqual(stats.average_words_per_post, 73.33)
        self.assertEqual(stats.posts_with_explicit_matchup, 2)
        self.assertEqual(stats.posts_by_year, {"2023": 1, "2024": 1})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual(stats.most_commented_posts[0].title, "Neo vs Agent Smith")
        self.assertEqual(stats.last_post_update, datetime(2024, 1, 16, tzinfo=timezone.utc))
        self.assertIsNotNone(stats.crawl_completed_at)

    def test_build_stats_handles_empty_post_list(self) -> None:
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


class CrawlMoviescenebattlesTests(TestCase):
    def test_rejects_invalid_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts must be greater than 0"):
            crawl_moviescenebattles(max_posts=0)
        with self.assertRaisesRegex(ValueError, "page_size must be greater than 0"):
            crawl_moviescenebattles(page_size=0)

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_stops_at_max_posts_and_paginates(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [_entry(entry_id="a"), _entry(entry_id="b")],
                }
            },
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [_entry(entry_id="c"), _entry(entry_id="d")],
                }
            },
        ]

        dataset = crawl_moviescenebattles(max_posts=3, page_size=2, include_content=False, timeout=12)

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual([post.post_id for post in dataset.posts], ["a", "b", "c"])
        self.assertEqual(dataset.stats.total_posts, 3)
        self.assertEqual(mock_fetch.call_count, 2)
        first_call = mock_fetch.call_args_list[0].kwargs
        second_call = mock_fetch.call_args_list[1].kwargs
        self.assertEqual(first_call, {"start_index": 1, "max_results": 2, "timeout": 12})
        self.assertEqual(second_call, {"start_index": 3, "max_results": 1, "timeout": 12})

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_stops_when_feed_returns_no_entries(self, mock_fetch) -> None:
        mock_fetch.return_value = {
            "feed": {"title": {"$t": "Movie Scene Battles"}, "entry": []}
        }

        dataset = crawl_moviescenebattles(max_posts=5, page_size=2)

        self.assertEqual(dataset.posts, [])
        self.assertEqual(dataset.stats.total_posts, 0)
        self.assertEqual(mock_fetch.call_count, 1)
