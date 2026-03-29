from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from movie_scene_battle_analyzer import crawler
from movie_scene_battle_analyzer.models import BattlePost, CrawlDataset, SiteStats


def _make_entry(
    *,
    idx: int,
    title: str,
    comments: int = 0,
    published: str = "2024-01-01T00:00:00+00:00",
    updated: str = "2024-01-02T00:00:00+00:00",
    categories: list[str] | None = None,
    content_html: str = "<p>Some content</p>",
) -> dict:
    return {
        "id": {"$t": f"id-{idx}"},
        "title": {"$t": title},
        "published": {"$t": published},
        "updated": {"$t": updated},
        "thr$total": {"$t": str(comments)},
        "category": [{"term": name} for name in (categories or [])],
        "content": {"$t": content_html},
        "link": [
            {"rel": "self", "href": f"https://example.com/self-{idx}"},
            {"rel": "alternate", "href": f"https://example.com/post-{idx}"},
        ],
    }


class CrawlerTests(unittest.TestCase):
    def test_to_post_content_flag_controls_content_storage(self) -> None:
        entry = _make_entry(
            idx=1,
            title="Hero vs Villain",
            comments=7,
            categories=["Action", "Classics"],
            content_html="<div>Hero &amp; Villain <b>Finale</b></div>",
        )

        post_without_content = crawler._to_post(entry, include_content=False)
        post_with_content = crawler._to_post(entry, include_content=True)

        self.assertIsNone(post_without_content.content_text)
        self.assertEqual("Hero & Villain Finale", post_with_content.content_text)
        self.assertEqual(4, post_with_content.word_count)
        self.assertEqual(7, post_with_content.comment_count)
        self.assertEqual(["Action", "Classics"], post_with_content.categories)
        self.assertEqual("https://example.com/post-1", post_with_content.url)

    def test_build_stats_captures_matchups_and_sorts_year_buckets(self) -> None:
        posts = [
            BattlePost(
                post_id="1",
                title="Movie A vs Movie B",
                url="https://example.com/1",
                published_at=datetime(2022, 1, 1),
                updated_at=datetime(2022, 1, 3),
                comment_count=5,
                categories=["Action", "Drama"],
                word_count=100,
            ),
            BattlePost(
                post_id="2",
                title="Movie C v Movie D",
                url="https://example.com/2",
                published_at=datetime(2021, 6, 1),
                updated_at=datetime(2022, 2, 1),
                comment_count=15,
                categories=["Action"],
                word_count=50,
            ),
            BattlePost(
                post_id="3",
                title="A quieter analysis",
                url="https://example.com/3",
                published_at=datetime(2021, 8, 1),
                updated_at=datetime(2021, 8, 2),
                comment_count=1,
                categories=["Drama"],
                word_count=25,
            ),
        ]

        stats = crawler._build_stats(posts)

        self.assertEqual(3, stats.total_posts)
        self.assertEqual(21, stats.total_comments)
        self.assertEqual(7.0, stats.average_comments_per_post)
        self.assertEqual(58.33, stats.average_words_per_post)
        self.assertEqual(2, stats.posts_with_explicit_matchup)
        self.assertEqual({"2021": 2, "2022": 1}, stats.posts_by_year)
        self.assertEqual("Action", stats.top_categories[0].name)
        self.assertEqual(2, stats.top_categories[0].count)
        self.assertEqual("Movie C v Movie D", stats.most_commented_posts[0].title)
        self.assertEqual(15, stats.most_commented_posts[0].comment_count)
        self.assertEqual(datetime(2022, 2, 1), stats.last_post_update)

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_crawl_moviescenebattles_paginates_and_caps_post_count(self, mock_fetch) -> None:
        mock_fetch.side_effect = [
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [
                        _make_entry(idx=1, title="One vs Two", comments=10),
                        _make_entry(idx=2, title="Three vs Four", comments=20),
                    ],
                }
            },
            {
                "feed": {
                    "title": {"$t": "Movie Scene Battles"},
                    "entry": [_make_entry(idx=3, title="Five vs Six", comments=30)],
                }
            },
        ]

        dataset = crawler.crawl_moviescenebattles(
            max_posts=3,
            include_content=False,
            page_size=2,
            timeout=11,
        )

        self.assertEqual(3, len(dataset.posts))
        self.assertEqual(
            [
                {"start_index": 1, "max_results": 2, "timeout": 11},
                {"start_index": 3, "max_results": 1, "timeout": 11},
            ],
            [call.kwargs for call in mock_fetch.call_args_list],
        )
        self.assertEqual("Movie Scene Battles", dataset.site_title)

    @patch("movie_scene_battle_analyzer.crawler._fetch_feed_page")
    def test_crawl_moviescenebattles_stops_when_feed_has_no_entries(self, mock_fetch) -> None:
        mock_fetch.return_value = {"feed": {"title": {"$t": "Movie Scene Battles"}, "entry": []}}

        dataset = crawler.crawl_moviescenebattles(max_posts=5, page_size=2)

        self.assertEqual(0, len(dataset.posts))
        self.assertEqual(0, dataset.stats.total_posts)
        self.assertEqual(1, mock_fetch.call_count)

    def test_crawl_moviescenebattles_validates_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_posts must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=0)
        with self.assertRaisesRegex(ValueError, "page_size must be greater than 0"):
            crawler.crawl_moviescenebattles(max_posts=1, page_size=0)

    def test_save_dataset_writes_json_output(self) -> None:
        dataset = CrawlDataset(
            site_title="Movie Scene Battles",
            site_url="https://moviescenebattles.blogspot.com",
            posts=[],
            stats=SiteStats(
                total_posts=0,
                total_comments=0,
                average_comments_per_post=0.0,
                average_words_per_post=0.0,
                posts_with_explicit_matchup=0,
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "dataset.json"
            crawler.save_dataset(dataset, output)

            self.assertTrue(output.exists())
            payload = output.read_text(encoding="utf-8")
            self.assertIn('"site_title": "Movie Scene Battles"', payload)


if __name__ == "__main__":
    unittest.main()
