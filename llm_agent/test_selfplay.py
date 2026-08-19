#!/usr/bin/env python3
"""
Unit tests for the baseline engine's self-play harness.

Same reasoning as the classic agent's version: every strength claim about
this engine comes out of run_match, so the colour attribution has to be
right or the numbers mean nothing.

Run with:
    python3 -m unittest test_selfplay
"""

import unittest

import chess

import selfplay


class ScriptedEngine:
    """Plays the first legal move, or resigns when told to"""

    def __init__(self, resign=False):
        self.resign = resign
        self.calls = 0

    def get_best_move(self, board, seconds, depth=None):
        self.calls += 1
        if self.resign:
            return None
        return next(iter(board.legal_moves), None)


class LegacyEngine:
    """Older interface without the depth argument"""

    def get_best_move(self, board, seconds):
        return next(iter(board.legal_moves), None)


class FakeModule:
    def __init__(self, factory):
        self.factory = factory

    def KnightmareFast(self):
        return self.factory()


class TestAskMove(unittest.TestCase):
    def test_a_modern_engine_is_given_the_depth(self):
        engine = ScriptedEngine()
        move = selfplay.ask_move(engine, chess.Board(), 3)
        self.assertIn(move, chess.Board().legal_moves)

    def test_an_engine_without_a_depth_argument_still_works(self):
        """Comparing against older saved copies is the whole point"""
        move = selfplay.ask_move(LegacyEngine(), chess.Board(), 3)
        self.assertIn(move, chess.Board().legal_moves)


class TestPlayGame(unittest.TestCase):
    def test_white_resigning_is_a_win_for_black(self):
        result = selfplay.play_game(
            ScriptedEngine(resign=True), ScriptedEngine(), [], depth=1
        )
        self.assertEqual(result, "0-1")

    def test_black_resigning_is_a_win_for_white(self):
        result = selfplay.play_game(
            ScriptedEngine(), ScriptedEngine(resign=True), [], depth=1
        )
        self.assertEqual(result, "1-0")

    def test_a_long_game_is_a_draw(self):
        result = selfplay.play_game(ScriptedEngine(), ScriptedEngine(), [], depth=1)
        self.assertEqual(result, "1/2-1/2")


class TestRunMatchScoring(unittest.TestCase):
    def match(self, new_factory, old_factory):
        return selfplay.run_match(
            FakeModule(new_factory), FakeModule(old_factory), depth=1, verbose=False
        )

    def test_an_engine_that_always_resigns_scores_zero(self):
        score, games = self.match(
            lambda: ScriptedEngine(resign=True), lambda: ScriptedEngine()
        )
        self.assertEqual(score, 0.0)
        self.assertGreater(games, 0)

    def test_an_opponent_that_always_resigns_scores_full_marks(self):
        score, games = self.match(
            lambda: ScriptedEngine(), lambda: ScriptedEngine(resign=True)
        )
        self.assertEqual(score, float(games))

    def test_identical_engines_score_half(self):
        score, games = self.match(lambda: ScriptedEngine(), lambda: ScriptedEngine())
        self.assertEqual(score, games / 2)

    def test_every_opening_is_played_from_both_sides(self):
        _, games = self.match(lambda: ScriptedEngine(), lambda: ScriptedEngine())
        self.assertEqual(games, 2 * len(selfplay.OPENINGS))


class TestOpenings(unittest.TestCase):
    def test_every_opening_is_a_legal_sequence(self):
        for name, opening in selfplay.OPENINGS:
            with self.subTest(opening=name):
                board = chess.Board()
                for uci in opening:
                    move = chess.Move.from_uci(uci)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)

    def test_openings_are_distinct(self):
        sequences = [tuple(moves) for _, moves in selfplay.OPENINGS]
        self.assertEqual(len(sequences), len(set(sequences)))


if __name__ == "__main__":
    unittest.main()
