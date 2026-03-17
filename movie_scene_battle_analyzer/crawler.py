from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import BattlePost, CategoryCount, CrawlDataset, PostHighlight, SiteStats

SITE_URL = "https://moviescenebattles.blogspot.com"
FEED_URL = f"{SITE_URL}/feeds/posts/default"


class _HTMLTextExtractor(HTMLParser):
    """Converts HTML fragments into plain text for word counts/analysis."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _fetch_feed_page(start_index: int, max_results: int, timeout: int) -> dict[str, Any]:
    params = urlencode(
        {
            "alt": "json",
            "start-index": start_index,
            "max-results": max_results,
        }
    )
    request = Request(
        f"{FEED_URL}?{params}",
        headers={"User-Agent": "movie-scene-battle-analyzer/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _extract_text(html_blob: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html_blob)
    text = unescape(parser.get_text())
    return re.sub(r"\s+", " ", text).strip()


def _parse_datetime(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _extract_permalink(entry: dict[str, Any]) -> str:
    for link in entry.get("link", []):
        if link.get("rel") == "alternate" and link.get("href"):
            return str(link["href"])
    return ""


def _to_post(entry: dict[str, Any], include_content: bool) -> BattlePost:
    content_html = entry.get("content", {}).get("$t", "")
    content_text = _extract_text(content_html) if content_html else ""
    categories = [str(tag.get("term")) for tag in entry.get("category", []) if tag.get("term")]
    comments = int(entry.get("thr$total", {}).get("$t", 0))

    return BattlePost(
        post_id=str(entry.get("id", {}).get("$t", "")),
        title=str(entry.get("title", {}).get("$t", "")).strip(),
        url=_extract_permalink(entry),
        published_at=_parse_datetime(entry.get("published", {}).get("$t")),
        updated_at=_parse_datetime(entry.get("updated", {}).get("$t")),
        comment_count=comments,
        categories=categories,
        word_count=len(content_text.split()),
        content_text=content_text if include_content else None,
    )


def _build_stats(posts: list[BattlePost]) -> SiteStats:
    total_posts = len(posts)
    total_comments = sum(post.comment_count for post in posts)
    total_words = sum(post.word_count for post in posts)

    posts_by_year: dict[str, int] = defaultdict(int)
    categories = Counter()
    matchup_pattern = re.compile(r"\b(vs\.?|versus|v)\b", flags=re.IGNORECASE)
    posts_with_explicit_matchup = 0
    last_post_update: datetime | None = None

    for post in posts:
        if post.published_at:
            posts_by_year[str(post.published_at.year)] += 1
        categories.update(post.categories)
        if matchup_pattern.search(post.title):
            posts_with_explicit_matchup += 1
        if post.updated_at and (last_post_update is None or post.updated_at > last_post_update):
            last_post_update = post.updated_at

    top_categories = [
        CategoryCount(name=name, count=count)
        for name, count in categories.most_common(10)
    ]
    most_commented_posts = [
        PostHighlight(title=post.title, url=post.url, comment_count=post.comment_count)
        for post in sorted(posts, key=lambda item: item.comment_count, reverse=True)[:5]
    ]

    return SiteStats(
        total_posts=total_posts,
        total_comments=total_comments,
        average_comments_per_post=round(total_comments / total_posts, 2) if total_posts else 0.0,
        average_words_per_post=round(total_words / total_posts, 2) if total_posts else 0.0,
        posts_with_explicit_matchup=posts_with_explicit_matchup,
        posts_by_year=dict(sorted(posts_by_year.items(), key=lambda item: item[0])),
        top_categories=top_categories,
        most_commented_posts=most_commented_posts,
        last_post_update=last_post_update,
        crawl_completed_at=datetime.now().astimezone(),
    )


def crawl_moviescenebattles(
    max_posts: int = 500,
    include_content: bool = False,
    page_size: int = 150,
    timeout: int = 30,
) -> CrawlDataset:
    """
    Crawl Movie Scene Battles Blogspot feed and return normalized data + stats.

    Blogspot feeds support pagination with `start-index` and `max-results`.
    This function fetches pages until `max_posts` is reached or no more entries exist.
    """
    if max_posts <= 0:
        raise ValueError("max_posts must be greater than 0")
    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    all_posts: list[BattlePost] = []
    start_index = 1
    site_title = "Movie Scene Battles"

    while len(all_posts) < max_posts:
        request_size = min(page_size, max_posts - len(all_posts))
        data = _fetch_feed_page(start_index=start_index, max_results=request_size, timeout=timeout)
        feed = data.get("feed", {})
        site_title = str(feed.get("title", {}).get("$t", site_title))
        entries = feed.get("entry", [])

        if not entries:
            break

        parsed_posts = [_to_post(entry, include_content=include_content) for entry in entries]
        all_posts.extend(parsed_posts)

        if len(entries) < request_size:
            break
        start_index += len(entries)

    posts = all_posts[:max_posts]
    stats = _build_stats(posts)
    return CrawlDataset(site_title=site_title, site_url=SITE_URL, posts=posts, stats=stats)


def save_dataset(dataset: CrawlDataset, output_path: str | Path) -> None:
    """Persist a crawl dataset to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset.to_dict(), indent=2, default=str), encoding="utf-8")
