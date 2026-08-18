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

from bot_loader import ask_engine, best_move, load_bot_class, parse_info, random_move


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


class TestParseInfo(unittest.TestCase):
    """Reading back what the engine reported on its info lines"""

    def test_a_single_info_line(self):
        info = parse_info("info depth 4 score cp 35 nodes 100 time 5 nps 20000 pv e2e4 e7e5")
        self.assertEqual(info["depth"], 4)
        self.assertEqual(info["score"], "cp 35")
        self.assertEqual(info["pv"], "e2e4 e7e5")

    def test_the_deepest_line_wins(self):
        text = (
            "info depth 1 score cp 10 nodes 5 time 1 nps 5000 pv a2a3\n"
            "info depth 3 score cp 40 nodes 90 time 4 nps 22500 pv e2e4 e7e5 g1f3\n"
        )
        self.assertEqual(parse_info(text)["depth"], 3)

    def test_negative_scores(self):
        self.assertEqual(
            parse_info("info depth 2 score cp -120 nodes 9 time 1 nps 9000 pv d2d4")["score"],
            "cp -120",
        )

    def test_mate_scores(self):
        self.assertEqual(
            parse_info("info depth 3 score mate 2 nodes 9 time 1 nps 9000 pv e1e8")["score"],
            "mate 2",
        )

    def test_a_book_move_reports_nothing(self):
        """Book moves and the random bot never search, so there is no info"""
        self.assertIsNone(parse_info("info string book move e2e4"))

    def test_empty_output_reports_nothing(self):
        self.assertIsNone(parse_info(""))

    def test_unrelated_output_is_ignored(self):
        self.assertIsNone(parse_info("readyok\nbestmove e2e4\n"))


class TestAskEngine(unittest.TestCase):
    def setUp(self):
        self.board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        )

    def test_a_searched_move_comes_with_info(self):
        bot = load_bot_class()()
        move, info = ask_engine(bot, self.board, 0.4)
        self.assertIn(move, self.board.legal_moves)
        self.assertIsNotNone(info)
        self.assertIn("depth", info)

    def test_no_engine_gives_a_move_and_no_info(self):
        move, info = ask_engine(None, self.board)
        self.assertIn(move, self.board.legal_moves)
        self.assertIsNone(info)

    def test_a_broken_engine_gives_a_move_and_no_info(self):
        move, info = ask_engine(BrokenBot(), self.board)
        self.assertIn(move, self.board.legal_moves)
        self.assertIsNone(info)

    def test_an_illegal_move_is_replaced_and_reports_no_info(self):
        move, info = ask_engine(IllegalMoveBot(), self.board)
        self.assertIn(move, self.board.legal_moves)
        self.assertIsNone(info)

    def test_the_callers_board_is_still_untouched(self):
        before = self.board.fen()
        ask_engine(MutatingBot(), self.board)
        self.assertEqual(self.board.fen(), before)


if __name__ == "__main__":
    unittest.main()
