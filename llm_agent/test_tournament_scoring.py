#!/usr/bin/env python3
"""
Unit tests for the LLM tournament's scoring.

The scoring used to run at import time, so it could not be tested at all.
A tournament that mis-scores still looks like it worked, which is exactly
the kind of bug worth pinning down.

These tests need chester only for the import, not for any games.

Run with:
    python3 -m unittest test_tournament_scoring
"""

import unittest

from tournament import PLAYERS, RESULT_POINTS, score_game


class FakePgn:
    """Just enough of a chess.pgn.Game to carry headers"""

    def __init__(self, white, black, result):
        self.headers = {"White": white, "Black": black, "Result": result}


class TestResultPoints(unittest.TestCase):
    def test_a_win_is_worth_one_point(self):
        self.assertEqual(RESULT_POINTS["1-0"], (1.0, 0.0))
        self.assertEqual(RESULT_POINTS["0-1"], (0.0, 1.0))

    def test_a_draw_splits_the_point(self):
        self.assertEqual(RESULT_POINTS["1/2-1/2"], (0.5, 0.5))

    def test_every_pairing_sums_to_one(self):
        for result, (white, black) in RESULT_POINTS.items():
            with self.subTest(result=result):
                self.assertEqual(white + black, 1.0)

    def test_unfinished_games_have_no_entry(self):
        self.assertNotIn("*", RESULT_POINTS)


class TestScoreGame(unittest.TestCase):
    def setUp(self):
        self.scores = {}
        self.counts = {}

    def score(self, white, black, result):
        return score_game(FakePgn(white, black, result), self.scores, self.counts)

    def test_white_win_is_credited_to_white(self):
        self.assertTrue(self.score("alice", "bob", "1-0"))
        self.assertEqual(self.scores, {"alice": 1.0, "bob": 0.0})

    def test_black_win_is_credited_to_black(self):
        self.assertTrue(self.score("alice", "bob", "0-1"))
        self.assertEqual(self.scores, {"alice": 0.0, "bob": 1.0})

    def test_draw_splits_the_point(self):
        self.assertTrue(self.score("alice", "bob", "1/2-1/2"))
        self.assertEqual(self.scores, {"alice": 0.5, "bob": 0.5})

    def test_unfinished_game_is_skipped(self):
        self.assertFalse(self.score("alice", "bob", "*"))
        self.assertEqual(self.counts, {"alice": 0, "bob": 0})

    def test_unfinished_game_still_registers_the_players(self):
        """They should appear in the table on zero, not vanish"""
        self.score("alice", "bob", "*")
        self.assertIn("alice", self.scores)
        self.assertIn("bob", self.scores)

    def test_game_counts_track_played_games(self):
        self.score("alice", "bob", "1-0")
        self.score("bob", "alice", "1-0")
        self.assertEqual(self.counts, {"alice": 2, "bob": 2})

    def test_scores_accumulate_across_games(self):
        self.score("alice", "bob", "1-0")
        self.score("alice", "bob", "1/2-1/2")
        self.assertEqual(self.scores["alice"], 1.5)
        self.assertEqual(self.scores["bob"], 0.5)

    def test_total_points_match_games_counted(self):
        """Every counted game must hand out exactly one point"""
        for result in ("1-0", "0-1", "1/2-1/2", "*"):
            self.score("alice", "bob", result)

        counted = self.counts["alice"]
        self.assertEqual(sum(self.scores.values()), counted)

    def test_a_third_player_does_not_disturb_the_others(self):
        self.score("alice", "bob", "1-0")
        self.score("carol", "alice", "1-0")
        self.assertEqual(self.scores["bob"], 0.0)
        self.assertEqual(self.scores["carol"], 1.0)
        self.assertEqual(self.scores["alice"], 1.0)


class TestPlayers(unittest.TestCase):
    def test_all_four_bots_are_entered(self):
        self.assertEqual(len(PLAYERS), 4)

    def test_entries_are_scripts(self):
        for player in PLAYERS:
            with self.subTest(player=player):
                self.assertTrue(player.endswith(".py"))


if __name__ == "__main__":
    unittest.main()
