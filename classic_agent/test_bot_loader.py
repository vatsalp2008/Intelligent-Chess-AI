#!/usr/bin/env python3
"""
Unit tests for the shared engine loading helpers.

Both web interfaces depend on these, and the fallback paths only run when
something has already gone wrong, so they are easy to break without
noticing. These tests exercise the failure paths deliberately.

Run with:
    python3 -m unittest test_bot_loader
"""

import unittest

import chess

from bot_loader import best_move, load_bot_class, random_move


class BrokenBot:
    """Raises whatever the caller asks for"""

    def get_move(self, board, seconds=1.0):
        raise RuntimeError("engine exploded")


class IllegalMoveBot:
    """Returns a move that is not legal in the position"""

    def get_move(self, board, seconds=1.0):
        return chess.Move.from_uci("a1a8")


class NoneReturningBot:
    def get_move(self, board, seconds=1.0):
        return None


class MinimaxOnlyBot:
    """Older interface that only exposes minimax"""

    def minimax(self, board, depth, alpha, beta, maximizing):
        return 0, next(iter(board.legal_moves))


class LegacyBot:
    """Older interface that exposes get_best_move"""

    def get_best_move(self, board, seconds=1.0):
        return next(iter(board.legal_moves))


class MutatingBot:
    """Pushes onto whatever board it is handed"""

    def get_move(self, board, seconds=1.0):
        move = next(iter(board.legal_moves))
        board.push(move)
        return move


class TestLoadBotClass(unittest.TestCase):
    def test_finds_the_engine_class(self):
        cls = load_bot_class()
        self.assertIsNotNone(cls)
        self.assertIn("Knightmare", cls.__name__)

    def test_missing_module_returns_none(self):
        self.assertIsNone(load_bot_class("definitely_not_a_module_here"))


class TestRandomMove(unittest.TestCase):
    def test_returns_a_legal_move(self):
        board = chess.Board()
        self.assertIn(random_move(board), board.legal_moves)

    def test_returns_none_when_there_are_no_moves(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("e1e8"))
        self.assertIsNone(random_move(board))


class TestBestMove(unittest.TestCase):
    def setUp(self):
        self.board = chess.Board()

    def test_real_engine_returns_a_legal_move(self):
        bot = load_bot_class()()
        self.assertIn(best_move(bot, self.board, 0.2), self.board.legal_moves)

    def test_missing_engine_falls_back_to_random(self):
        self.assertIn(best_move(None, self.board), self.board.legal_moves)

    def test_engine_that_raises_falls_back_to_random(self):
        self.assertIn(best_move(BrokenBot(), self.board), self.board.legal_moves)

    def test_illegal_move_is_replaced(self):
        """An engine bug must not put an illegal move on the board"""
        move = best_move(IllegalMoveBot(), self.board)
        self.assertIn(move, self.board.legal_moves)
        self.assertNotEqual(move, chess.Move.from_uci("a1a8"))

    def test_none_result_falls_back_to_random(self):
        self.assertIn(best_move(NoneReturningBot(), self.board), self.board.legal_moves)

    def test_legacy_get_best_move_interface_is_used(self):
        self.assertIn(best_move(LegacyBot(), self.board), self.board.legal_moves)

    def test_minimax_only_interface_is_used(self):
        self.assertIn(best_move(MinimaxOnlyBot(), self.board), self.board.legal_moves)

    def test_object_with_no_usable_method_falls_back(self):
        self.assertIn(best_move(object(), self.board), self.board.legal_moves)

    def test_callers_board_is_never_mutated(self):
        """The engine gets a copy, so the real game state is safe"""
        before = self.board.fen()
        best_move(MutatingBot(), self.board)
        self.assertEqual(self.board.fen(), before)

    def test_finished_game_returns_none(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("e1e8"))
        self.assertIsNone(best_move(None, board))


if __name__ == "__main__":
    unittest.main()
