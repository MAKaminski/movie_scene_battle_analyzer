from __future__ import annotations

import argparse

from .crawler import crawl_moviescenebattles, save_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl and analyze Movie Scene Battles.")
    parser.add_argument("--max-posts", type=int, default=500, help="Maximum number of posts to crawl.")
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Store post body text in the output dataset.",
    )
    parser.add_argument(
        "--output",
        default="data/moviescenebattles_dataset.json",
        help="Path for the generated JSON dataset.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dataset = crawl_moviescenebattles(max_posts=args.max_posts, include_content=args.include_content)
    save_dataset(dataset, args.output)
    print(f"Saved {len(dataset.posts)} posts and aggregate stats to {args.output}")


if __name__ == "__main__":
    main()
