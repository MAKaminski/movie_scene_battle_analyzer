from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BattlePost:
    """Normalized Blogspot entry for one movie battle post."""

    post_id: str
    title: str
    url: str
    published_at: datetime | None
    updated_at: datetime | None
    comment_count: int
    categories: list[str] = field(default_factory=list)
    word_count: int = 0
    content_text: str | None = None


@dataclass(slots=True)
class CategoryCount:
    name: str
    count: int


@dataclass(slots=True)
class PostHighlight:
    title: str
    url: str
    comment_count: int


@dataclass(slots=True)
class SiteStats:
    """Aggregate site-level metrics built from crawled posts."""

    total_posts: int
    total_comments: int
    average_comments_per_post: float
    average_words_per_post: float
    posts_with_explicit_matchup: int
    posts_by_year: dict[str, int] = field(default_factory=dict)
    top_categories: list[CategoryCount] = field(default_factory=list)
    most_commented_posts: list[PostHighlight] = field(default_factory=list)
    last_post_update: datetime | None = None
    crawl_completed_at: datetime | None = None


@dataclass(slots=True)
class CrawlDataset:
    """Main crawl payload containing every post plus derived stats."""

    site_title: str
    site_url: str
    posts: list[BattlePost]
    stats: SiteStats

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
