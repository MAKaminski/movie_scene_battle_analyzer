from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost


def _entry(
    *,
    post_id: str = "post-1",
    title: str = "Hero vs Villain",
    permalink: str = "https://example.com/post-1",
    published: str = "2025-01-01T12:00:00+00:00",
    updated: str = "2025-01-02T12:00:00+00:00",
    comments: str = "4",
    categories: list[str] | None = None,
    content_html: str = "<p>One &amp; Two</p>",
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "link": [
            {"rel": "self", "href": "https://example.com/self"},
            {"rel": "alternate", "href": permalink},
        ],
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": comments},
        "category": [{"term": item} for item in (categories or ["Action", "Drama"])],
        "content": {"$t": content_html},
    }


class ParseAndNormalizeTests(unittest.TestCase):
    def test_extract_text_unescapes_and_normalizes_whitespace(self) -> None:
        html = "<div> One &amp;   Two<br>Three </div>"
        self.assertEqual(crawler._extract_text(html), "One & TwoThree")

    def test_parse_datetime_returns_none_for_missing_or_invalid_values(self) -> None:
        self.assertIsNone(crawler._parse_datetime(None))
        self.assertIsNone(crawler._parse_datetime("not-a-date"))
        parsed = crawler._parse_datetime("2025-01-01T00:00:00+00:00")
        self.assertEqual(parsed, datetime(2025, 1, 1, tzinfo=timezone.utc))

    def test_to_post_respects_include_content_flag(self) -> None:
        entry = _entry(content_html="<p>alpha beta gamma</p>")

        with_content = crawler._to_post(entry, include_content=True)
        without_content = crawler._to_post(entry, include_content=False)

        self.assertEqual(with_content.content_text, "alpha beta gamma")
        self.assertEqual(with_content.word_count, 3)
        self.assertIsNone(without_content.content_text)
        self.assertEqual(without_content.word_count, 3)
        self.assertEqual(with_content.url, "https://example.com/post-1")


class StatsAndPaginationTests(unittest.TestCase):
    def test_build_stats_aggregates_core_fields(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Hero vs Villain",
                url="https://example.com/1",
                published_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 20, tzinfo=timezone.utc),
                comment_count=5,
                categories=["Action", "Drama"],
                word_count=120,
            ),
            BattlePost(
                post_id="2",
                title="Final Battle",
                url="https://example.com/2",
                published_at=datetime(2025, 2, 10, tzinfo=timezone.utc),
                updated_at=datetime(2025, 2, 20, tzinfo=timezone.utc),
                comment_count=7,
                categories=["Action"],
                word_count=80,
            ),
        ]

        stats = crawler._build_stats(posts)

        self.assertEqual(stats.total_posts, 2)
        self.assertEqual(stats.total_comments, 12)
        self.assertEqual(stats.average_comments_per_post, 6.0)
        self.assertEqual(stats.average_words_per_post, 100.0)
        self.assertEqual(stats.posts_with_explicit_matchup, 1)
        self.assertEqual(stats.posts_by_year, {"2024": 1, "2025": 1})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual(stats.most_commented_posts[0].title, "Final Battle")
        self.assertEqual(stats.last_post_update, datetime(2025, 2, 20, tzinfo=timezone.utc))

    def test_crawl_moviescenebattles_validates_inputs(self) -> None:
        with self.assertRaises(ValueError):
            crawler.crawl_moviescenebattles(max_posts=0)
        with self.assertRaises(ValueError):
            crawler.crawl_moviescenebattles(max_posts=1, page_size=0)

    def test_crawl_moviescenebattles_paginates_and_respects_max_posts(self) -> None:
        first_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [_entry(post_id="1"), _entry(post_id="2")],
            }
        }
        second_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [_entry(post_id="3"), _entry(post_id="4")],
            }
        }

        with patch.object(crawler, "_fetch_feed_page", side_effect=[first_page, second_page]) as mocked:
            dataset = crawler.crawl_moviescenebattles(max_posts=3, page_size=2, include_content=False)

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual(dataset.posts[0].post_id, "1")
        self.assertEqual(dataset.posts[-1].post_id, "3")
        self.assertEqual(dataset.stats.total_posts, 3)
        self.assertEqual(mocked.call_count, 2)
        first_call = mocked.call_args_list[0].kwargs
        second_call = mocked.call_args_list[1].kwargs
        self.assertEqual(first_call["start_index"], 1)
        self.assertEqual(first_call["max_results"], 2)
        self.assertEqual(second_call["start_index"], 3)
        self.assertEqual(second_call["max_results"], 1)


if __name__ == "__main__":
    unittest.main()
