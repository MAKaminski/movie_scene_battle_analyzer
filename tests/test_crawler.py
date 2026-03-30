from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from movie_scene_battle_analyzer.crawler import (
    _build_stats,
    _extract_permalink,
    _extract_text,
    _parse_datetime,
    _to_post,
    crawl_moviescenebattles,
    save_dataset,
)
from movie_scene_battle_analyzer.models import BattlePost, CrawlDataset


def _entry(
    *,
    post_id: str = "id-1",
    title: str = "Hero vs Villain",
    content: str = "<p> One&nbsp; two </p>",
    published: str = "2025-01-01T10:00:00+00:00",
    updated: str = "2025-01-02T10:00:00+00:00",
    comments: str = "3",
    categories: list[str] | None = None,
    alternate_url: str = "https://example.com/post/1",
) -> dict:
    return {
        "id": {"$t": post_id},
        "title": {"$t": title},
        "content": {"$t": content},
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": comments},
        "category": [{"term": value} for value in (categories or ["Action"])],
        "link": [
            {"rel": "self", "href": "https://example.com/self"},
            {"rel": "alternate", "href": alternate_url},
        ],
    }


class CrawlerUtilityTests(unittest.TestCase):
    def test_extract_text_strips_html_unescapes_entities_and_normalizes_spaces(self) -> None:
        html = "<div>Tom &amp; Jerry<br>   showdown</div>"
        self.assertEqual(_extract_text(html), "Tom & Jerry showdown")

    def test_parse_datetime_handles_empty_and_invalid_values(self) -> None:
        self.assertIsNone(_parse_datetime(None))
        self.assertIsNone(_parse_datetime("invalid-value"))
        parsed = _parse_datetime("2025-03-05T12:30:00+00:00")
        self.assertEqual(parsed, datetime(2025, 3, 5, 12, 30, tzinfo=timezone.utc))

    def test_extract_permalink_prefers_alternate_href(self) -> None:
        entry = {"link": [{"rel": "self", "href": "a"}, {"rel": "alternate", "href": "b"}]}
        self.assertEqual(_extract_permalink(entry), "b")
        self.assertEqual(_extract_permalink({"link": []}), "")

    def test_to_post_drops_content_when_not_requested(self) -> None:
        post = _to_post(_entry(), include_content=False)
        self.assertEqual(post.word_count, 2)
        self.assertIsNone(post.content_text)

    def test_to_post_includes_content_when_requested(self) -> None:
        post = _to_post(_entry(content="<p>A B C</p>"), include_content=True)
        self.assertEqual(post.word_count, 3)
        self.assertEqual(post.content_text, "A B C")


class CrawlerStatsTests(unittest.TestCase):
    def test_build_stats_computes_matchups_categories_years_and_highlights(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="One vs Two",
                url="u1",
                published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
                comment_count=10,
                categories=["Action", "Classic"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Three V Four",
                url="u2",
                published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
                comment_count=2,
                categories=["Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="Quiet drama",
                url="u3",
                published_at=None,
                updated_at=None,
                comment_count=5,
                categories=["Drama"],
                word_count=25,
            ),
        ]

        stats = _build_stats(posts)
        self.assertEqual(stats.total_posts, 3)
        self.assertEqual(stats.total_comments, 17)
        self.assertEqual(stats.average_comments_per_post, 5.67)
        self.assertEqual(stats.average_words_per_post, 58.33)
        self.assertEqual(stats.posts_with_explicit_matchup, 2)
        self.assertEqual(stats.posts_by_year, {"2023": 1, "2024": 1})
        self.assertEqual(stats.top_categories[0].name, "Action")
        self.assertEqual(stats.top_categories[0].count, 2)
        self.assertEqual([p.title for p in stats.most_commented_posts], ["One vs Two", "Quiet drama", "Three V Four"])
        self.assertEqual(stats.last_post_update, datetime(2024, 1, 3, tzinfo=timezone.utc))
        self.assertIsNotNone(stats.crawl_completed_at)

    def test_build_stats_handles_empty_input(self) -> None:
        stats = _build_stats([])
        self.assertEqual(stats.total_posts, 0)
        self.assertEqual(stats.average_comments_per_post, 0.0)
        self.assertEqual(stats.average_words_per_post, 0.0)
        self.assertEqual(stats.most_commented_posts, [])


class CrawlFlowTests(unittest.TestCase):
    def test_crawl_rejects_invalid_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts"):
            crawl_moviescenebattles(max_posts=0)
        with self.assertRaisesRegex(ValueError, "page_size"):
            crawl_moviescenebattles(max_posts=1, page_size=0)

    def test_crawl_paginates_and_honors_max_posts(self) -> None:
        page_1 = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _entry(post_id="1", title="A vs B", comments="1", alternate_url="https://x/1"),
                    _entry(post_id="2", title="C versus D", comments="2", alternate_url="https://x/2"),
                ],
            }
        }
        page_2 = {
            "feed": {
                "title": {"$t": "Movie Scene Battles"},
                "entry": [
                    _entry(post_id="3", title="E v F", comments="3", alternate_url="https://x/3"),
                ],
            }
        }
        calls: list[tuple[int, int, int]] = []

        def fake_fetch(start_index: int, max_results: int, timeout: int) -> dict:
            calls.append((start_index, max_results, timeout))
            return page_1 if start_index == 1 else page_2

        with patch("movie_scene_battle_analyzer.crawler._fetch_feed_page", side_effect=fake_fetch):
            dataset = crawl_moviescenebattles(max_posts=3, include_content=False, page_size=2, timeout=7)

        self.assertEqual(calls, [(1, 2, 7), (3, 1, 7)])
        self.assertEqual(len(dataset.posts), 3)
        self.assertEqual([p.post_id for p in dataset.posts], ["1", "2", "3"])
        self.assertEqual(dataset.stats.posts_with_explicit_matchup, 3)

    def test_crawl_stops_when_feed_returns_no_entries(self) -> None:
        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            return_value={"feed": {"title": {"$t": "Movie Scene Battles"}, "entry": []}},
        ):
            dataset = crawl_moviescenebattles(max_posts=5)
        self.assertEqual(dataset.posts, [])
        self.assertEqual(dataset.stats.total_posts, 0)

    def test_save_dataset_writes_json_payload(self) -> None:
        with patch(
            "movie_scene_battle_analyzer.crawler._fetch_feed_page",
            return_value={"feed": {"title": {"$t": "Movie Scene Battles"}, "entry": [_entry()]}},
        ):
            dataset: CrawlDataset = crawl_moviescenebattles(max_posts=1, include_content=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "nested" / "dataset.json"
            save_dataset(dataset, output)
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["site_title"], "Movie Scene Battles")
        self.assertEqual(len(payload["posts"]), 1)
        self.assertIn("stats", payload)


if __name__ == "__main__":
    unittest.main()
