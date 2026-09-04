from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from movie_scene_battle_analyzer.crawler import parse_matchup
from movie_scene_battle_analyzer.insights import RETIREMENT_WINS, build_insights


def _post(day: int, champion: str, champion_movie: str, challenger: str, challenger_movie: str,
          battle_type: str = "defense", wins: int | None = None, month: int = 5) -> dict:
    return {
        "post_id": f"post-{month}-{day}",
        "title": f"{champion} vs. {challenger}",
        "url": f"https://example.test/{month}/{day}",
        "published_at": f"2026-{month:02d}-{day:02d} 21:00:00-07:00",
        "updated_at": None,
        "comment_count": 0,
        "categories": [f"{champion_movie} 1990", f"{challenger_movie} 2001"],
        "word_count": 100,
        "champion": champion,
        "champion_movie": champion_movie,
        "challenger": challenger,
        "challenger_movie": challenger_movie,
        "champion_wins_claimed": wins,
        "battle_type": battle_type,
    }


class ParseMatchupTests(unittest.TestCase):
    def test_parses_defense_with_win_counter(self):
        text = "Your ChampionSlaps(Vivacious Lady)VSYour ChallengerThe Bear(Annihilation)The Case for Slaps (1):..."
        parsed = parse_matchup(text)
        self.assertEqual(parsed["champion"], "Slaps")
        self.assertEqual(parsed["champion_movie"], "Vivacious Lady")
        self.assertEqual(parsed["challenger"], "The Bear")
        self.assertEqual(parsed["challenger_movie"], "Annihilation")
        self.assertEqual(parsed["champion_wins_claimed"], 1)
        self.assertEqual(parsed["battle_type"], "defense")

    def test_parses_fresh_matchup(self):
        text = "Your ChallengerA(Movie A)VSYour ChallengerB(Movie B)The Case for A:..."
        parsed = parse_matchup(text)
        self.assertEqual(parsed["battle_type"], "fresh")
        self.assertIsNone(parsed["champion_wins_claimed"])

    def test_returns_empty_for_non_battle(self):
        self.assertEqual(parse_matchup("Taking a day off and will return on Monday!"), {})


class BuildInsightsTests(unittest.TestCase):
    def _ladder(self) -> list[dict]:
        # Fresh matchup: A beats B, then A defends against C and loses, C reigns.
        posts = [
            _post(1, "A", "Film A", "B", "Film B", battle_type="fresh"),
            _post(2, "A", "Film A", "C", "Film C", wins=1),
            _post(3, "C", "Film C", "D", "Film D", wins=1),
            _post(4, "C", "Film C", "E", "Film E", wins=2),
        ]
        return posts

    def test_reconstructs_winners_and_reigns(self):
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": self._ladder()})
        summary = insights["summary"]
        self.assertEqual(summary["battles"], 4)
        self.assertEqual(summary["decided_battles"], 3)
        self.assertEqual(summary["pending_battles"], 1)
        self.assertEqual(summary["upsets"], 1)  # C beat A
        self.assertEqual(summary["fresh_matchups"], 1)
        self.assertEqual(insights["current_reign"]["scene"], "C")
        self.assertEqual(insights["current_reign"]["wins"], 2)
        self.assertEqual(insights["head_to_head"]["champion_wins"], 2)
        self.assertEqual(insights["data_quality"]["win_counter_agreement_rate"], 100.0)
        # The losing side of a fresh matchup never counts as a reign.
        self.assertEqual(summary["reigns"], 2)

    def test_retirement_after_seven_wins(self):
        posts = [_post(1, "A", "Film A", "B", "Film B", battle_type="fresh")]
        for day in range(2, 2 + RETIREMENT_WINS - 1):
            posts.append(_post(day, "A", "Film A", f"X{day}", f"Film X{day}", wins=day - 1))
        posts.append(_post(20, "P", "Film P", "Q", "Film Q", battle_type="fresh"))
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": posts})
        self.assertEqual(len(insights["hall_of_fame"]), 1)
        retired = insights["hall_of_fame"][0]
        self.assertEqual(retired["scene"], "A")
        self.assertEqual(retired["wins"], RETIREMENT_WINS)
        self.assertEqual(len(retired["defeated"]), RETIREMENT_WINS)

    def test_tolerates_scene_name_typos(self):
        posts = [
            _post(1, "A", "Film A", "Subway Fight", "The Matrix", wins=1),
            _post(2, "Subway Battle", "The Matrix", "D", "Film D", wins=1),
            _post(3, "Subway Fight", "The Matrix", "E", "Film E", wins=2),
        ]
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": posts})
        self.assertEqual(insights["summary"]["decided_battles"], 2)
        self.assertEqual(insights["current_reign"]["wins"], 2)
        self.assertEqual(len(insights["data_quality"]["name_drift"]), 2)

    def test_counter_mismatch_is_reported(self):
        posts = [
            _post(1, "A", "Film A", "B", "Film B", wins=1),
            _post(2, "A", "Film A", "C", "Film C", wins=5),
        ]
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": posts})
        self.assertEqual(len(insights["data_quality"]["win_counter_mismatches"]), 1)

    def test_cadence_estimates_use_trailing_average(self):
        posts = []
        for month, count in ((3, 10), (4, 20), (5, 15)):
            for day in range(1, count + 1):
                posts.append(_post(day, f"S{month}{day}", "Film", f"T{month}{day}", "Other", month=month, wins=1))
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": posts})
        monthly = {row["month"]: row for row in insights["cadence"]["monthly"]}
        self.assertEqual(monthly["2026-04"]["estimate"], 10.0)
        self.assertEqual(monthly["2026-05"]["estimate"], 15.0)
        self.assertTrue(monthly["2026-05"]["is_partial"])
        self.assertEqual(insights["cadence"]["next_month"]["month"], "2026-06")

    def test_empty_dataset(self):
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": []})
        self.assertEqual(insights["battles"], 0)


if __name__ == "__main__":
    unittest.main()
