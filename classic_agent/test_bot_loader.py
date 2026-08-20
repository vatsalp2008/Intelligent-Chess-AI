#!/usr/bin/env python3
"""
Unit tests for the shared engine loading helpers.

Both web interfaces depend on these, and the fallback paths only run when
something has already gone wrong, so they are easy to break without
noticing. These tests exercise the failure paths deliberately.

Run with:
    python3 -m unittest test_bot_loader
"""

import io
import unittest

import chess
import chess.pgn

from bot_loader import (
    ask_engine,
    best_move,
    describe_info,
    game_pgn,
    load_bot_class,
    parse_info,
    random_move,
)


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

    def test_repeated_calls_do_not_grow_sys_path(self):
        """It used to insert the directory on every call"""
        import sys

        load_bot_class()
        before = len(sys.path)
        for _ in range(20):
            load_bot_class()
        self.assertEqual(len(sys.path), before)


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


class TestDescribeInfo(unittest.TestCase):
    """Raw UCI is unreadable at a glance, so it gets translated"""

    def setUp(self):
        self.board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        )

    def describe(self, score="cp 0", pv=""):
        return describe_info({"depth": 3, "score": score, "pv": pv}, self.board)

    def test_centipawns_become_pawns(self):
        self.assertEqual(self.describe(score="cp -104")["score_text"], "-1.04")
        self.assertEqual(self.describe(score="cp 250")["score_text"], "+2.50")

    def test_zero_keeps_its_sign(self):
        self.assertEqual(self.describe(score="cp 0")["score_text"], "+0.00")

    def test_mate_scores_are_spelled_out(self):
        self.assertEqual(self.describe(score="mate 2")["score_text"], "mate in 2")

    def test_being_mated_says_so(self):
        self.assertIn("opponent", self.describe(score="mate -3")["score_text"])

    def test_the_line_becomes_algebraic(self):
        self.assertEqual(self.describe(pv="b1c3 f8c5 d2d4")["pv_text"], "Nc3 Bc5 d4")

    def test_the_raw_values_are_kept_too(self):
        described = self.describe(score="cp -104", pv="b1c3")
        self.assertEqual(described["score"], "cp -104")
        self.assertEqual(described["pv"], "b1c3")

    def test_an_illegal_line_stops_where_it_breaks(self):
        """A stale line must not be reported as if it were playable"""
        self.assertEqual(self.describe(pv="b1c3 a1a8 d2d4")["pv_text"], "Nc3")

    def test_a_malformed_line_is_survived(self):
        self.assertEqual(self.describe(pv="not-a-move")["pv_text"], "")

    def test_an_empty_line_gives_empty_text(self):
        self.assertEqual(self.describe(pv="")["pv_text"], "")

    def test_nothing_in_gives_nothing_out(self):
        self.assertIsNone(describe_info(None, self.board))

    def test_the_board_is_not_disturbed(self):
        before = self.board.fen()
        self.describe(pv="b1c3 f8c5 d2d4")
        self.assertEqual(self.board.fen(), before)

    def test_an_unexpected_score_format_is_passed_through(self):
        self.assertEqual(self.describe(score="lowerbound")["score_text"], "lowerbound")


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


class TestGamePgn(unittest.TestCase):
    """Writing a game out in a form other chess software will read"""

    def board_after(self, *ucis, fen=None):
        board = chess.Board(fen) if fen else chess.Board()
        for uci in ucis:
            board.push(chess.Move.from_uci(uci))
        return board

    def pgn(self, board, white="White", black="Black"):
        return game_pgn(board, white, black)

    def parsed(self, board, **names):
        return chess.pgn.read_game(io.StringIO(self.pgn(board, **names)))

    def test_an_empty_game_is_still_valid_pgn(self):
        self.assertIsNotNone(self.parsed(chess.Board()))

    def test_the_moves_read_back_to_the_same_position(self):
        board = self.board_after("e2e4", "e7e5", "g1f3", "b8c6", "f1b5")
        self.assertEqual(self.parsed(board).end().board().fen(), board.fen())

    def test_moves_are_written_in_algebraic(self):
        board = self.board_after("e2e4", "e7e5", "g1f3")
        self.assertIn("1. e4 e5 2. Nf3", self.pgn(board))

    def test_the_players_are_named(self):
        headers = self.parsed(chess.Board(), white="Alice", black="Bob").headers
        self.assertEqual(headers["White"], "Alice")
        self.assertEqual(headers["Black"], "Bob")

    def test_an_unfinished_game_has_no_result(self):
        self.assertIn('[Result "*"]', self.pgn(self.board_after("e2e4")))

    def test_a_win_is_recorded(self):
        board = self.board_after("f2f3", "e7e5", "g2g4", "d8h4")
        self.assertIn('[Result "0-1"]', self.pgn(board))

    def test_a_stalemate_is_a_draw(self):
        board = self.board_after("f7g6", fen="7k/5Q2/8/8/8/8/8/6K1 w - - 0 1")
        self.assertTrue(board.is_stalemate())
        self.assertIn('[Result "1/2-1/2"]', self.pgn(board))

    def test_a_game_from_a_fen_records_where_it_started(self):
        """The moves alone would replay from the wrong position"""
        fen = "8/8/4k3/8/8/8/4P3/4K3 w - - 0 1"
        board = self.board_after("e2e4", fen=fen)
        game = self.parsed(board)
        self.assertEqual(game.headers["FEN"], fen)
        self.assertEqual(game.headers["SetUp"], "1")
        self.assertEqual(game.end().board().fen(), board.fen())

    def test_a_game_from_a_fen_numbers_from_that_move(self):
        board = self.board_after("e6d6", fen="8/8/4k3/8/8/8/4P3/4K3 b - - 4 20")
        self.assertIn("20... Kd6", self.pgn(board))

    def test_a_normal_game_records_no_starting_position(self):
        text = self.pgn(self.board_after("e2e4"))
        self.assertNotIn("FEN", text)
        self.assertNotIn("SetUp", text)

    def test_lines_are_wrapped_at_eighty_columns(self):
        board = chess.Board()
        for _ in range(60):
            board.push(next(iter(board.legal_moves)))
        for line in self.pgn(board).splitlines():
            self.assertLessEqual(len(line), 80, line)

    def test_a_blank_line_separates_headers_from_moves(self):
        lines = self.pgn(self.board_after("e2e4")).splitlines()
        self.assertIn("", lines)
        self.assertTrue(lines[lines.index("") - 1].startswith("["))

    def test_it_ends_with_a_newline(self):
        self.assertTrue(self.pgn(chess.Board()).endswith("\n"))

    def test_the_board_is_not_disturbed(self):
        board = self.board_after("e2e4", "e7e5")
        before = board.fen()
        depth = len(board.move_stack)
        self.pgn(board)
        self.assertEqual(board.fen(), before)
        self.assertEqual(len(board.move_stack), depth)


if __name__ == "__main__":
    unittest.main()
