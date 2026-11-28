from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost


def _make_entry(
    *,
    post_id: str,
    title: str,
    content_html: str,
    comment_count: str,
    published_at: str,
    updated_at: str,
    url: str,
    categories: list[str],
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "content": {"$t": content_html},
        "thr$total": {"$t": comment_count},
        "published": {"$t": published_at},
        "updated": {"$t": updated_at},
        "link": [{"rel": "alternate", "href": url}],
        "category": [{"term": category} for category in categories],
    }


class CrawlMovieSceneBattlesTests(unittest.TestCase):
    def test_crawl_moviescenebattles_paginates_and_enforces_max_posts(self) -> None:
        first_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _make_entry(
                        post_id="1",
                        title="Hero vs Villain",
                        content_html="<p>One two</p>",
                        comment_count="3",
                        published_at="2022-01-01T10:00:00+00:00",
                        updated_at="2022-01-02T10:00:00+00:00",
                        url="https://example.com/1",
                        categories=["Action"],
                    ),
                    _make_entry(
                        post_id="2",
                        title="Mentor v Student",
                        content_html="<p>Three four five</p>",
                        comment_count="4",
                        published_at="2022-02-01T10:00:00+00:00",
                        updated_at="2022-02-02T10:00:00+00:00",
                        url="https://example.com/2",
                        categories=["Drama"],
                    ),
                ],
            }
        }
        second_page = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _make_entry(
                        post_id="3",
                        title="Final showdown",
                        content_html="<p>Six seven</p>",
                        comment_count="5",
                        published_at="2022-03-01T10:00:00+00:00",
                        updated_at="2022-03-02T10:00:00+00:00",
                        url="https://example.com/3",
                        categories=["Action"],
                    )
                ],
            }
        }

        calls: list[tuple[int, int, int]] = []

        def fake_fetch(start_index: int, max_results: int, timeout: int) -> dict:
            calls.append((start_index, max_results, timeout))
            if start_index == 1:
                return first_page
            if start_index == 3:
                return second_page
            raise AssertionError(f"Unexpected start_index: {start_index}")

        with patch.object(crawler, "_fetch_feed_page", side_effect=fake_fetch):
            dataset = crawler.crawl_moviescenebattles(
                max_posts=3,
                include_content=False,
                page_size=2,
                timeout=7,
            )

        self.assertEqual(calls, [(1, 2, 7), (3, 1, 7)])
        self.assertEqual(dataset.site_title, "Movie Scene Battles")
        self.assertEqual(len(dataset.posts), 3)
        self.assertIsNone(dataset.posts[0].content_text)
        self.assertEqual(dataset.posts[0].word_count, 2)

    def test_to_post_extracts_plain_text_and_handles_invalid_datetimes(self) -> None:
        entry = _make_entry(
            post_id="42",
            title="Alpha versus Beta",
            content_html="<p>Alpha &amp; <b>Beta</b></p>\n<p>Gamma</p>",
            comment_count="12",
            published_at="not-a-date",
            updated_at="2025-01-01T12:00:00+00:00",
            url="https://example.com/42",
            categories=["Classic", "Drama"],
        )

        post = crawler._to_post(entry, include_content=True)

        self.assertIsNone(post.published_at)
        self.assertEqual(post.updated_at, datetime.fromisoformat("2025-01-01T12:00:00+00:00"))
        self.assertEqual(post.word_count, 4)
        self.assertEqual(post.content_text, "Alpha & Beta Gamma")
        self.assertEqual(post.comment_count, 12)
        self.assertEqual(post.categories, ["Classic", "Drama"])

    def test_build_stats_detects_matchups_and_caps_highlights(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="A v B",
                url="https://example.com/1",
                published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2020, 1, 2, tzinfo=timezone.utc),
                comment_count=5,
                categories=["Action", "Classic"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="A vs B",
                url="https://example.com/2",
                published_at=datetime(2020, 2, 1, tzinfo=timezone.utc),
                updated_at=datetime(2020, 2, 2, tzinfo=timezone.utc),
                comment_count=7,
                categories=["Action"],
                word_count=120,
            ),
            BattlePost(
                post_id="3",
                title="A versus B",
                url="https://example.com/3",
                published_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2021, 1, 2, tzinfo=timezone.utc),
                comment_count=1,
                categories=["Drama"],
                word_count=80,
            ),
            BattlePost(
                post_id="4",
                title="No matchup language",
                url="https://example.com/4",
                published_at=datetime(2021, 2, 1, tzinfo=timezone.utc),
                updated_at=datetime(2021, 2, 2, tzinfo=timezone.utc),
                comment_count=9,
                categories=["Action"],
                word_count=90,
            ),
            BattlePost(
                post_id="5",
                title="Another post",
                url="https://example.com/5",
                published_at=datetime(2021, 3, 1, tzinfo=timezone.utc),
                updated_at=datetime(2021, 3, 2, tzinfo=timezone.utc),
                comment_count=3,
                categories=["Comedy"],
                word_count=70,
            ),
            BattlePost(
                post_id="6",
                title="One more",
                url="https://example.com/6",
                published_at=datetime(2021, 4, 1, tzinfo=timezone.utc),
                updated_at=datetime(2021, 4, 2, tzinfo=timezone.utc),
                comment_count=4,
                categories=["Action"],
                word_count=60,
            ),
        ]

        stats = crawler._build_stats(posts)

        self.assertEqual(stats.total_posts, 6)
        self.assertEqual(stats.posts_with_explicit_matchup, 3)
        self.assertEqual(stats.average_comments_per_post, 4.83)
        self.assertEqual(stats.posts_by_year, {"2020": 2, "2021": 4})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 4)
        self.assertEqual(len(stats.most_commented_posts), 5)
        self.assertEqual(stats.most_commented_posts[0].comment_count, 9)
        self.assertEqual(stats.last_post_update, datetime(2021, 4, 2, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
