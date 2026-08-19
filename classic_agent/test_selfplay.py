#!/usr/bin/env python3
"""
Unit tests for the self-play harness's bookkeeping.

Every strength claim about this engine comes out of run_match, so a bug in
how it attributes results would quietly invalidate all of them. The colour
swapping is the easy thing to get backwards: the same PGN result string
means opposite things depending on which side the new engine played.

Run with:
    python3 -m unittest test_selfplay
"""

import unittest

import chess

import selfplay


class ScriptedEngine:
    """Plays from a fixed list, then resigns by returning None"""

    def __init__(self, moves=None, resign_after=None):
        self.moves = list(moves or [])
        self.resign_after = resign_after
        self.calls = 0

    def get_move(self, board, seconds, depth):
        self.calls += 1
        if self.resign_after is not None and self.calls > self.resign_after:
            return None
        while self.moves:
            candidate = chess.Move.from_uci(self.moves.pop(0))
            if candidate in board.legal_moves:
                return candidate
        return next(iter(board.legal_moves), None)


class FakeModule:
    """Stands in for an engine module, handing out scripted engines"""

    def __init__(self, factory):
        self.factory = factory

    def KnightmareBot(self):
        return self.factory()


class TestPlayGame(unittest.TestCase):
    def test_an_engine_that_cannot_move_loses(self):
        """White resigning immediately is a win for Black"""
        result = selfplay.play_game(
            ScriptedEngine(resign_after=0), ScriptedEngine(), [], depth=1
        )
        self.assertEqual(result, "0-1")

    def test_black_resigning_is_a_win_for_white(self):
        result = selfplay.play_game(
            ScriptedEngine(), ScriptedEngine(resign_after=0), [], depth=1
        )
        self.assertEqual(result, "1-0")

    def test_a_capped_game_is_a_draw(self):
        result = selfplay.play_game(
            ScriptedEngine(), ScriptedEngine(), [], depth=1, max_plies=4
        )
        self.assertEqual(result, "1/2-1/2")

    def test_the_opening_is_played_before_the_engines_move(self):
        white = ScriptedEngine()
        selfplay.play_game(white, ScriptedEngine(), ["e2e4", "e7e5"], depth=1, max_plies=3)
        # The two opening moves are on the board before either engine is asked
        self.assertGreaterEqual(white.calls, 1)

    def test_a_real_checkmate_is_reported(self):
        """Scripted into the shortest mate, so the result is unambiguous"""
        white = ScriptedEngine(["f2f3", "g2g4"])
        black = ScriptedEngine(["e7e5", "d8h4"])
        result = selfplay.play_game(white, black, [], depth=1, max_plies=4)
        self.assertEqual(result, "0-1")


class TestRunMatchScoring(unittest.TestCase):
    """The colour swap is the part most likely to be wrong"""

    def match(self, new_factory, old_factory):
        return selfplay.run_match(
            FakeModule(new_factory), FakeModule(old_factory), depth=1, verbose=False
        )

    def test_an_engine_that_always_resigns_scores_zero(self):
        score, games = self.match(
            lambda: ScriptedEngine(resign_after=0), lambda: ScriptedEngine()
        )
        self.assertEqual(score, 0.0)
        self.assertGreater(games, 0)

    def test_an_opponent_that_always_resigns_scores_full_marks(self):
        score, games = self.match(
            lambda: ScriptedEngine(), lambda: ScriptedEngine(resign_after=0)
        )
        self.assertEqual(score, float(games))

    def test_identical_engines_score_half(self):
        """The sanity check the harness is trusted on"""
        score, games = self.match(lambda: ScriptedEngine(), lambda: ScriptedEngine())
        self.assertEqual(score, games / 2)

    def test_every_opening_is_played_from_both_sides(self):
        _, games = self.match(lambda: ScriptedEngine(), lambda: ScriptedEngine())
        self.assertEqual(games, 2 * len(selfplay.OPENINGS))

    def test_scores_never_exceed_the_games_played(self):
        score, games = self.match(
            lambda: ScriptedEngine(), lambda: ScriptedEngine(resign_after=1)
        )
        self.assertLessEqual(score, games)
        self.assertGreaterEqual(score, 0)


class TestOpenings(unittest.TestCase):
    def test_every_opening_is_a_legal_sequence(self):
        for name, opening in selfplay.OPENINGS:
            with self.subTest(opening=name):
                board = chess.Board()
                for uci in opening:
                    move = chess.Move.from_uci(uci)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)

    def test_no_opening_is_already_finished(self):
        for name, opening in selfplay.OPENINGS:
            with self.subTest(opening=name):
                board = chess.Board()
                for uci in opening:
                    board.push(chess.Move.from_uci(uci))
                self.assertFalse(board.is_game_over())

    def test_openings_are_distinct(self):
        sequences = [tuple(moves) for _, moves in selfplay.OPENINGS]
        self.assertEqual(len(sequences), len(set(sequences)))


if __name__ == "__main__":
    unittest.main()
