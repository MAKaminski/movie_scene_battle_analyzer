from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost


def _make_entry(
    *,
    post_id: str,
    title: str,
    href: str,
    published: str = "2024-01-01T00:00:00+00:00",
    updated: str = "2024-01-01T01:00:00+00:00",
    comments: str = "0",
    categories: list[dict[str, str | None]] | None = None,
    content_html: str = "<p>alpha beta</p>",
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "link": [{"rel": "self", "href": "https://example.invalid/self"}, {"rel": "alternate", "href": href}],
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": comments},
        "category": categories if categories is not None else [{"term": "Action"}],
        "content": {"$t": content_html},
    }


class ToPostTests(unittest.TestCase):
    def test_to_post_parses_html_categories_permalink_and_comment_count(self) -> None:
        entry = _make_entry(
            post_id="post-1",
            title="  Hero vs. Villain  ",
            href="https://moviescenebattles.blogspot.com/post-1",
            comments="12",
            categories=[{"term": "Action"}, {"term": None}, {"term": "Classics"}],
            content_html="<p>Tom &amp; Jerry</p><p> Final&nbsp;Showdown </p>",
        )

        post = crawler._to_post(entry, include_content=True)

        self.assertEqual(post.post_id, "post-1")
        self.assertEqual(post.title, "Hero vs. Villain")
        self.assertEqual(post.url, "https://moviescenebattles.blogspot.com/post-1")
        self.assertEqual(post.comment_count, 12)
        self.assertEqual(post.categories, ["Action", "Classics"])
        self.assertEqual(post.content_text, "Tom & Jerry Final Showdown")
        self.assertEqual(post.word_count, 5)
        self.assertIsNotNone(post.published_at)
        self.assertIsNotNone(post.updated_at)

    def test_to_post_omits_content_text_when_include_content_false(self) -> None:
        entry = _make_entry(
            post_id="post-2",
            title="A v B",
            href="https://moviescenebattles.blogspot.com/post-2",
            content_html="<p>one two three</p>",
        )

        post = crawler._to_post(entry, include_content=False)

        self.assertIsNone(post.content_text)
        self.assertEqual(post.word_count, 3)


class CrawlMoviescenebattlesTests(unittest.TestCase):
    def test_rejects_non_positive_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts"):
            crawler.crawl_moviescenebattles(max_posts=0)

        with self.assertRaisesRegex(ValueError, "page_size"):
            crawler.crawl_moviescenebattles(max_posts=5, page_size=0)

    def test_paginates_and_respects_max_posts(self) -> None:
        page_1 = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _make_entry(post_id="1", title="A vs B", href="https://x/1", comments="3"),
                    _make_entry(post_id="2", title="C versus D", href="https://x/2", comments="4"),
                ],
            }
        }
        page_2 = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _make_entry(post_id="3", title="E v F", href="https://x/3", comments="5"),
                ],
            }
        }

        with patch.object(crawler, "_fetch_feed_page", side_effect=[page_1, page_2]) as fetch_mock:
            dataset = crawler.crawl_moviescenebattles(max_posts=3, page_size=2)

        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual([post.post_id for post in dataset.posts], ["1", "2", "3"])
        self.assertEqual(fetch_mock.call_count, 2)
        self.assertEqual(fetch_mock.call_args_list[0].kwargs["start_index"], 1)
        self.assertEqual(fetch_mock.call_args_list[0].kwargs["max_results"], 2)
        self.assertEqual(fetch_mock.call_args_list[1].kwargs["start_index"], 3)
        self.assertEqual(fetch_mock.call_args_list[1].kwargs["max_results"], 1)


class BuildStatsTests(unittest.TestCase):
    def test_detects_matchup_titles_and_aggregates_categories(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Hero v Villain",
                url="https://x/1",
                published_at=crawler._parse_datetime("2023-01-01T00:00:00+00:00"),
                updated_at=crawler._parse_datetime("2023-01-02T00:00:00+00:00"),
                comment_count=3,
                categories=["Action", "Classics"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Finale versus Opening",
                url="https://x/2",
                published_at=crawler._parse_datetime("2022-01-01T00:00:00+00:00"),
                updated_at=crawler._parse_datetime("2022-01-03T00:00:00+00:00"),
                comment_count=7,
                categories=["Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="Character study",
                url="https://x/3",
                published_at=crawler._parse_datetime("2022-02-01T00:00:00+00:00"),
                updated_at=crawler._parse_datetime("2023-02-01T00:00:00+00:00"),
                comment_count=2,
                categories=["Drama"],
                word_count=150,
            ),
        ]

        stats = crawler._build_stats(posts)

        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 12)
        self.assertEqual(stats.average_comments_per_post, 4.0)
        self.assertEqual(stats.average_words_per_post, 100.0)
        self.assertEqual(stats.posts_with_explicit_matchup, 2)
        self.assertEqual(list(stats.posts_by_year.items()), [("2022", 2), ("2023", 1)])
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual(stats.most_commented_posts[0].title, "Finale versus Opening")
        self.assertEqual(stats.last_post_update.isoformat(), "2023-02-01T00:00:00+00:00")
        self.assertIsNotNone(stats.crawl_completed_at)


if __name__ == "__main__":
    unittest.main()
