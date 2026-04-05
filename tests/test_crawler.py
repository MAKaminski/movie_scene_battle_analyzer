from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost


def _build_entry(
    post_id: str,
    title: str,
    published: str,
    updated: str,
    comments: int,
    content: str = "<p>Scene&nbsp;content</p>",
    categories: list[str] | None = None,
    url: str = "https://example.com/post",
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": str(comments)},
        "content": {"$t": content},
        "category": [{"term": name} for name in (categories or [])],
        "link": [{"rel": "alternate", "href": url}],
    }


class CrawlerHelperTests(unittest.TestCase):
    def test_extract_text_unescapes_and_normalizes_whitespace(self) -> None:
        text = crawler._extract_text("<div>One&nbsp;&amp;   Two<br/>Three</div>")
        self.assertEqual(text, "One & TwoThree")

    def test_parse_datetime_handles_invalid_values(self) -> None:
        self.assertIsNone(crawler._parse_datetime(None))
        self.assertIsNone(crawler._parse_datetime("not-a-date"))
        self.assertEqual(
            crawler._parse_datetime("2025-01-01T00:00:00+00:00"),
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        )

    def test_extract_permalink_falls_back_to_empty_string(self) -> None:
        entry = {"link": [{"rel": "self", "href": "https://example.com/self"}]}
        self.assertEqual(crawler._extract_permalink(entry), "")

    def test_to_post_hides_content_when_include_content_disabled(self) -> None:
        entry = _build_entry(
            post_id="id-1",
            title="Neo vs Agent Smith",
            published="2025-01-02T10:00:00+00:00",
            updated="2025-01-03T10:00:00+00:00",
            comments=9,
            content="<p>Hello&nbsp;world</p>",
            categories=["Action", "Sci-Fi"],
            url="https://example.com/neo-vs-smith",
        )
        post = crawler._to_post(entry, include_content=False)
        self.assertEqual(post.post_id, "id-1")
        self.assertEqual(post.word_count, 2)
        self.assertIsNone(post.content_text)
        self.assertEqual(post.categories, ["Action", "Sci-Fi"])


class StatsAndCrawlTests(unittest.TestCase):
    def test_build_stats_aggregates_matchups_categories_and_years(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Neo vs Agent Smith",
                url="u1",
                published_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 5, 2, tzinfo=timezone.utc),
                comment_count=10,
                categories=["Action", "Sci-Fi"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Batman versus Joker",
                url="u2",
                published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                comment_count=30,
                categories=["Action"],
                word_count=200,
            ),
            BattlePost(
                post_id="3",
                title="Rocky v Apollo",
                url="u3",
                published_at=None,
                updated_at=None,
                comment_count=5,
                categories=["Drama"],
                word_count=50,
            ),
        ]

        stats = crawler._build_stats(posts)
        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 45)
        self.assertEqual(stats.average_comments_per_post, 15.0)
        self.assertEqual(stats.average_words_per_post, 116.67)
        self.assertEqual(stats.posts_with_explicit_matchup, 3)
        self.assertEqual(stats.posts_by_year, {"2023": 1, "2024": 1})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual(stats.most_commented_posts[0].title, "Batman versus Joker")
        self.assertEqual(stats.last_post_update, datetime(2025, 1, 1, tzinfo=timezone.utc))
        self.assertIsNotNone(stats.crawl_completed_at)

    def test_crawl_moviescenebattles_validates_numeric_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=0)
        with self.assertRaisesRegex(ValueError, "page_size must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=1, page_size=0)

    def test_crawl_moviescenebattles_paginates_and_caps_results(self) -> None:
        pages = {
            (1, 2): {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [
                        _build_entry(
                            post_id="1",
                            title="A vs B",
                            published="2024-01-01T00:00:00+00:00",
                            updated="2024-01-01T00:00:00+00:00",
                            comments=1,
                            url="https://example.com/1",
                        ),
                        _build_entry(
                            post_id="2",
                            title="C vs D",
                            published="2024-01-02T00:00:00+00:00",
                            updated="2024-01-02T00:00:00+00:00",
                            comments=2,
                            url="https://example.com/2",
                        ),
                    ],
                }
            },
            (3, 1): {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [
                        _build_entry(
                            post_id="3",
                            title="E vs F",
                            published="2024-01-03T00:00:00+00:00",
                            updated="2024-01-03T00:00:00+00:00",
                            comments=3,
                            url="https://example.com/3",
                        )
                    ],
                }
            },
        }

        requested_pages: list[tuple[int, int, int]] = []

        def fake_fetch(start_index: int, max_results: int, timeout: int) -> dict:
            requested_pages.append((start_index, max_results, timeout))
            return pages[(start_index, max_results)]

        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=fake_fetch):
            dataset = crawler.crawl_moviescenebattles(
                max_posts=3,
                include_content=False,
                page_size=2,
                timeout=11,
            )

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual([post.post_id for post in dataset.posts], ["1", "2", "3"])
        self.assertEqual(requested_pages, [(1, 2, 11), (3, 1, 11)])
        self.assertEqual(dataset.site_title, "Movie Scene Battles")


if __name__ == "__main__":
    unittest.main()
