#!/usr/bin/env python3
"""
Unit tests for the baseline engine's Stockfish benchmark harness.

The external strength figures come out of play_game, and its result
attribution is easy to get backwards: the same board state means a win or a
loss depending on which colour we were playing. A stub stands in for
Stockfish so no engine binary is needed.

Run with:
    python3 -m unittest test_benchmark
"""

import os
import unittest

import chess

import benchmark_stockfish as bench


class StubResult:
    def __init__(self, move):
        self.move = move


class StubStockfish:
    """Plays the first legal move, or resigns when told to"""

    def __init__(self, resign=False):
        self.resign = resign
        self.configured = []

    def configure(self, options):
        self.configured.append(options)

    def play(self, board, limit):
        if self.resign:
            return StubResult(None)
        return StubResult(next(iter(board.legal_moves), None))


class StubBot:
    """Our side: plays the first legal move, or fails when told to"""

    def __init__(self, fail=False):
        self.fail = fail

    def get_best_move(self, board, seconds, depth=None):
        if self.fail:
            return None
        return next(iter(board.legal_moves), None)


class TestFindStockfish(unittest.TestCase):
    def test_the_environment_variable_wins_when_it_points_at_a_file(self):
        os.environ["STOCKFISH_PATH"] = __file__
        try:
            self.assertEqual(bench.find_stockfish(), __file__)
        finally:
            del os.environ["STOCKFISH_PATH"]

    def test_a_bogus_environment_variable_is_ignored(self):
        os.environ["STOCKFISH_PATH"] = "/definitely/not/here"
        try:
            found = bench.find_stockfish()
        finally:
            del os.environ["STOCKFISH_PATH"]
        self.assertNotEqual(found, "/definitely/not/here")


class TestPlayGame(unittest.TestCase):
    """A game is scored from our engine's point of view"""

    def test_failing_to_move_is_a_loss(self):
        score = bench.play_game(
            StubBot(fail=True), StubStockfish(), [], chess.WHITE, skill_depth=1
        )
        self.assertEqual(score, 0.0)

    def test_the_opponent_failing_to_move_is_a_win(self):
        score = bench.play_game(
            StubBot(), StubStockfish(resign=True), [], chess.WHITE, skill_depth=1
        )
        self.assertEqual(score, 1.0)

    def test_a_long_game_is_a_draw(self):
        score = bench.play_game(
            StubBot(), StubStockfish(), [], chess.WHITE, skill_depth=1
        )
        self.assertIn(score, (0.0, 0.5, 1.0))

    def test_playing_black_still_scores_from_our_side(self):
        """Our engine resigns, so the score is zero whichever colour it had"""
        score = bench.play_game(
            StubBot(fail=True), StubStockfish(), [], chess.BLACK, skill_depth=1
        )
        self.assertEqual(score, 0.0)

    def test_the_opening_is_applied_before_play(self):
        score = bench.play_game(
            StubBot(fail=True), StubStockfish(), ["e2e4", "e7e5"],
            chess.WHITE, skill_depth=1,
        )
        self.assertEqual(score, 0.0)


class TestRunMatch(unittest.TestCase):
    def test_the_skill_level_is_configured_once(self):
        engine = StubStockfish()
        bench.run_match(StubBot, engine, level=7, skill_depth=1, games=2, verbose=False)
        self.assertEqual(engine.configured, [{"Skill Level": 7}])

    def test_the_requested_number_of_games_is_played(self):
        _, played = bench.run_match(
            StubBot, StubStockfish(), level=20, skill_depth=1, games=3, verbose=False
        )
        self.assertEqual(played, 3)

    def test_an_engine_that_always_fails_scores_nothing(self):
        score, played = bench.run_match(
            lambda: StubBot(fail=True), StubStockfish(),
            level=20, skill_depth=1, games=4, verbose=False,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(played, 4)

    def test_scores_stay_within_the_games_played(self):
        score, played = bench.run_match(
            StubBot, StubStockfish(), level=20, skill_depth=1, games=4, verbose=False
        )
        self.assertLessEqual(score, played)
        self.assertGreaterEqual(score, 0)


class TestOpenings(unittest.TestCase):
    def test_every_opening_is_legal(self):
        for name, opening in bench.OPENINGS:
            with self.subTest(opening=name):
                board = chess.Board()
                for uci in opening:
                    move = chess.Move.from_uci(uci)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)


if __name__ == "__main__":
    unittest.main()
