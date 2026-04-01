import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import (
    _extract_permalink,
    _extract_text,
    crawl_moviescenebattles,
)


def _entry(
    *,
    post_id: str,
    title: str,
    url: str,
    published: str,
    updated: str,
    comments: int,
    categories: list[str],
    content_html: str,
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "link": [{"rel": "alternate", "href": url}],
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": str(comments)},
        "category": [{"term": category} for category in categories],
        "content": {"$t": content_html},
    }


class CrawlerTests(unittest.TestCase):
    def test_extract_text_normalizes_html_entities_and_whitespace(self):
        text = _extract_text("<p>Tom &amp; Jerry</p><div>  The  Show </div>")
        self.assertEqual(text, "Tom & Jerry The Show")

    def test_extract_permalink_returns_empty_string_without_alternate_link(self):
        entry = {"link": [{"rel": "self", "href": "https://example.test/feed"}]}
        self.assertEqual(_extract_permalink(entry), "")

    def test_crawl_moviescenebattles_paginates_and_builds_expected_stats(self):
        first_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _entry(
                        post_id="1",
                        title="Heat vs The Dark Knight",
                        url="https://moviescenebattles.blogspot.com/1",
                        published="2024-01-01T00:00:00+00:00",
                        updated="2024-01-02T00:00:00+00:00",
                        comments=12,
                        categories=["Action", "Classics"],
                        content_html="<p>One two three</p>",
                    ),
                    _entry(
                        post_id="2",
                        title="Alien v Predator",
                        url="https://moviescenebattles.blogspot.com/2",
                        published="2024-02-01T00:00:00+00:00",
                        updated="2024-02-03T00:00:00+00:00",
                        comments=5,
                        categories=["Action"],
                        content_html="<p>four five</p>",
                    ),
                ],
            }
        }
        second_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _entry(
                        post_id="3",
                        title="Best Finale",
                        url="https://moviescenebattles.blogspot.com/3",
                        published="2025-01-01T00:00:00+00:00",
                        updated="2025-01-04T00:00:00+00:00",
                        comments=27,
                        categories=["Drama"],
                        content_html="<p>six seven eight nine</p>",
                    )
                ],
            }
        }

        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page") as fetch_mock:
            fetch_mock.side_effect = [first_page, second_page]
            dataset = crawl_moviescenebattles(
                max_posts=3, include_content=False, page_size=2, timeout=11
            )

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual(dataset.stats.total_posts, 3)
        self.assertEqual(dataset.stats.total_comments, 44)
        self.assertEqual(dataset.stats.posts_with_explicit_matchup, 2)
        self.assertEqual(dataset.stats.posts_by_year, {"2024": 2, "2025": 1})
        self.assertIsNotNone(dataset.stats.crawl_completed_at)
        self.assertEqual(dataset.stats.last_post_update.isoformat(), "2025-01-04T00:00:00+00:00")

        # Most commented post should be first.
        self.assertEqual(dataset.stats.most_commented_posts[0].title, "Best Finale")
        self.assertEqual(dataset.stats.most_commented_posts[0].comment_count, 27)

        # "Action" appears twice and should lead category counts.
        self.assertEqual(dataset.stats.top_categories[0].name, "Action")
        self.assertEqual(dataset.stats.top_categories[0].count, 2)

        # content_text should be omitted when include_content=False.
        self.assertTrue(all(post.content_text is None for post in dataset.posts))

        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(
            fetch_mock.call_args_list[0].kwargs,
            {"start_index": 1, "max_results": 2, "timeout": 11},
        )
        self.assertEqual(
            fetch_mock.call_args_list[1].kwargs,
            {"start_index": 3, "max_results": 1, "timeout": 11},
        )

    def test_include_content_true_keeps_plaintext_body(self):
        page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _entry(
                        post_id="99",
                        title="Final Showdown",
                        url="https://moviescenebattles.blogspot.com/99",
                        published="2025-03-01T00:00:00+00:00",
                        updated="2025-03-01T00:00:00+00:00",
                        comments=1,
                        categories=["Showdown"],
                        content_html="<div>Alpha   beta</div>",
                    )
                ],
            }
        }
        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", return_value=page):
            dataset = crawl_moviescenebattles(max_posts=1, include_content=True, page_size=5)

        post = dataset.posts[0]
        self.assertEqual(post.content_text, "Alpha beta")
        self.assertEqual(post.word_count, 2)

    def test_crawl_moviescenebattles_validates_positive_limits(self):
        with self.assertRaises(ValueError):
            crawl_moviescenebattles(max_posts=0)
        with self.assertRaises(ValueError):
            crawl_moviescenebattles(max_posts=1, page_size=0)


if __name__ == "__main__":
    unittest.main()
