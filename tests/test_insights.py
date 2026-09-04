from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from movie_scene_battle_analyzer.crawler import parse_matchup, parse_score, parse_submitters
from movie_scene_battle_analyzer.insights import RETIREMENT_WINS, build_insights


def _post(day: int, champion: str, champion_movie: str, challenger: str, challenger_movie: str,
          battle_type: str = "defense", wins: int | None = None, month: int = 5,
          votes: tuple[int, int] | None = None, tiebreaker: bool = False,
          submitters: list[dict] | None = None) -> dict:
    score_entries = None
    if votes is not None:
        pairs = [(champion, votes[0]), (challenger, votes[1])]
        score_entries = sorted(pairs, key=lambda p: -p[1])
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
        "score_entries": score_entries,
        "tiebreaker": tiebreaker,
        "submitters": submitters or [],
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


class ParseScoreTests(unittest.TestCase):
    def test_parses_two_sided_score(self):
        parsed = parse_score("The Score: Freeway Freakout 6, An Unusual Lullaby 4 Have a suggestion?")
        self.assertEqual(parsed["score_entries"], [("Freeway Freakout", 6), ("An Unusual Lullaby", 4)])
        self.assertFalse(parsed["tiebreaker"])

    def test_parses_tiebreaker_and_star_marker(self):
        parsed = parse_score("The Score: Hooked 7*, Miss Hilly's Special Pie 6(tiebreaker used)")
        self.assertEqual(parsed["score_entries"], [("Hooked", 7), ("Miss Hilly's Special Pie", 6)])
        self.assertTrue(parsed["tiebreaker"])

    def test_handles_scene_name_containing_a_comma(self):
        parsed = parse_score("The Score: Gabriel, Revealed 9, Clever Girl 5 Have a suggestion?")
        self.assertEqual(parsed["score_entries"], [("Gabriel, Revealed", 9), ("Clever Girl", 5)])

    def test_open_poll_has_no_score(self):
        self.assertEqual(parse_score("The Score: Have a suggestion? Read the rules"), {})

    def test_submitter_credit_is_tied_to_its_case_block(self):
        text = (
            "The Case for A Friendly Warning:El Mariachi lore.(Submitted by Nicktendo)"
            "The Case for ET Meets the Siblings:Elliott hides the alien.(Submitted by Rainy)"
        )
        self.assertEqual(
            parse_submitters(text),
            [
                {"name": "Nicktendo", "scene": "A Friendly Warning"},
                {"name": "Rainy", "scene": "ET Meets the Siblings"},
            ],
        )

    def test_submitter_credit_on_a_champion_with_a_win_counter(self):
        text = "The Case for The Wrong Week to Quit Sniffing Glue (1):Never a good week.(Submitted by Rainy)"
        self.assertEqual(parse_submitters(text), [{"name": "Rainy", "scene": "The Wrong Week to Quit Sniffing Glue"}])

    def test_no_credit(self):
        self.assertEqual(parse_submitters("no credit here"), [])


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

    def test_voting_metrics_from_published_scores(self):
        posts = [
            _post(1, "A", "Film A", "B", "Film B", battle_type="fresh", votes=(8, 7)),
            _post(2, "A", "Film A", "C", "Film C", wins=1, votes=(10, 3)),
            _post(3, "A", "Film A", "D", "Film D", wins=2, votes=(5, 6), tiebreaker=True),
        ]
        v = build_insights({"site_title": "t", "site_url": "u", "posts": posts})["voting"]
        self.assertEqual(v["scored_battles"], 3)
        self.assertEqual(v["total_votes"], 15 + 13 + 11)
        self.assertEqual(v["max_turnout"], 15)
        self.assertEqual(v["one_vote_battles"], 2)
        self.assertEqual(len(v["tiebreakers"]), 1)
        self.assertEqual(v["biggest_blowouts"][0]["margin"], 7)

    def test_poll_result_cross_checks_the_chain(self):
        posts = [
            _post(1, "A", "Film A", "B", "Film B", battle_type="fresh", votes=(8, 7)),
            _post(2, "A", "Film A", "C", "Film C", wins=1, votes=(9, 4)),
            _post(3, "A", "Film A", "D", "Film D", wins=2, votes=(9, 4)),
        ]
        dq = build_insights({"site_title": "t", "site_url": "u", "posts": posts})["data_quality"]
        self.assertEqual(dq["scored_battles"], 3)
        self.assertEqual(dq["poll_vs_chain_agreement_rate"], 100.0)
        self.assertEqual(dq["poll_vs_chain_mismatches"], [])

    def test_unreadable_score_is_reported_not_guessed(self):
        post = _post(1, "A", "Film A", "B", "Film B", wins=1)
        post["score_entries"] = [("Totally Different Scene", 6), ("Another One", 4)]
        v = build_insights({"site_title": "t", "site_url": "u", "posts": [post]})
        self.assertEqual(v["voting"]["scored_battles"], 0)
        self.assertEqual(len(v["data_quality"]["unreadable_scores"]), 1)

    def test_submitter_credit_follows_its_scene_through_a_reign(self):
        # B is submitted by Rainy, beats champion A, then defends twice. The
        # credit repeats each post, riding B from challenger to champion.
        rainy = [{"name": "Rainy", "scene": "B"}]
        posts = [
            _post(1, "A", "Film A", "B", "Film B", wins=1, votes=(4, 9), submitters=rainy),
            _post(2, "B", "Film B", "C", "Film C", wins=1, votes=(9, 4), submitters=rainy),
            _post(3, "B", "Film B", "D", "Film D", wins=2, votes=(3, 9), submitters=rainy),
            # D taking the crown is what decides battle 3 against B.
            _post(4, "D", "Film D", "E", "Film E", wins=1, votes=(9, 4)),
        ]
        s = build_insights({"site_title": "t", "site_url": "u", "posts": posts})["submitters"]
        self.assertEqual(s["credited_people"], 1)
        self.assertEqual(s["credited_battles"], 3)
        person = s["people"][0]
        self.assertEqual(person["name"], "Rainy")
        # One scene, not three: the repeated credit is the same scene each time.
        self.assertEqual(person["scene_count"], 1)
        # B won as challenger, held once, then lost - two wins, one loss.
        self.assertEqual((person["wins"], person["losses"]), (2, 1))
        self.assertEqual(person["best_run"], 2)

    def test_two_credits_in_one_battle_go_to_the_right_sides(self):
        posts = [
            _post(1, "A", "Film A", "B", "Film B", wins=1, votes=(9, 4),
                  submitters=[{"name": "Nick", "scene": "A"}, {"name": "Rainy", "scene": "B"}]),
            # A returning as champion is what records the win for A's side.
            _post(2, "A", "Film A", "C", "Film C", wins=2, votes=(9, 4)),
        ]
        s = build_insights({"site_title": "t", "site_url": "u", "posts": posts})["submitters"]
        by_name = {p["name"]: p for p in s["people"]}
        self.assertEqual((by_name["Nick"]["wins"], by_name["Nick"]["losses"]), (1, 0))
        self.assertEqual((by_name["Rainy"]["wins"], by_name["Rainy"]["losses"]), (0, 1))

    def test_credit_naming_an_unknown_scene_is_skipped(self):
        posts = [_post(1, "A", "Film A", "B", "Film B", wins=1,
                       submitters=[{"name": "Ghost", "scene": "Some Other Scene Entirely"}])]
        s = build_insights({"site_title": "t", "site_url": "u", "posts": posts})["submitters"]
        self.assertEqual(s["credited_people"], 0)
        self.assertEqual(s["unmatched_credits"], 1)

    def test_empty_dataset(self):
        insights = build_insights({"site_title": "t", "site_url": "u", "posts": []})
        self.assertEqual(insights["battles"], 0)


if __name__ == "__main__":
    unittest.main()
