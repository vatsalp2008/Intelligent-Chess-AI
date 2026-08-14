#!/usr/bin/env python3
"""
Unit tests for the KnightmareFast search used by the LLM agent tournament.

Run with:
    python3 -m unittest test_knightmare
"""

import unittest

import chess

from knightmare import (
    PIECE_VALUES,
    TT_EXACT,
    TT_MAX_ENTRIES,
    KnightmareFast,
    get_piece_square_value,
)

INFINITY = float("inf")


class TestEvaluationSign(unittest.TestCase):
    """The search is a plain min/max, so scores must be White-relative"""

    def setUp(self):
        self.bot = KnightmareFast()

    def test_score_does_not_depend_on_side_to_move(self):
        """The same winning position must not flip sign with the turn"""
        white_turn = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        black_turn = chess.Board("4k3/8/8/8/8/8/8/3QK3 b - - 0 1")
        self.assertGreater(self.bot.evaluate_board(white_turn), 0)
        self.assertGreater(self.bot.evaluate_board(black_turn), 0)

    def test_mirrored_positions_score_opposite(self):
        white_up = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        black_up = chess.Board("3qk3/8/8/8/8/8/8/4K3 b - - 0 1")
        self.assertEqual(
            self.bot.evaluate_board(white_up), -self.bot.evaluate_board(black_up)
        )

    def test_checkmate_uses_the_same_convention_as_the_rest(self):
        """Black mated is a big positive score whoever is to move"""
        black_mated = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertTrue(black_mated.is_checkmate())
        self.assertGreater(self.bot.evaluate_board(black_mated), 0)

    def test_starting_position_is_roughly_balanced(self):
        board = chess.Board()
        self.assertLess(abs(self.bot.evaluate_board(board)), 200)

    def test_claimable_fifty_move_draw_is_zero(self):
        board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 100 60")
        self.assertEqual(self.bot.evaluate_board(board), 0)


class TestSearchQuality(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareFast()

    def test_takes_free_material_as_white(self):
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
        self.assertEqual(self.bot.get_best_move(board, 2.0), chess.Move.from_uci("e4d5"))

    def test_takes_free_material_as_black(self):
        board = chess.Board("4k3/4q3/8/8/8/8/4Q3/4K3 b - - 0 1")
        self.assertEqual(self.bot.get_best_move(board, 2.0), chess.Move.from_uci("e7e2"))

    def test_declines_a_capture_that_loses_the_queen(self):
        """Qxd5 wins a pawn and drops the queen to cxd5"""
        board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
        self.assertNotEqual(
            self.bot.get_best_move(board, 2.0), chess.Move.from_uci("d1d5")
        )

    def test_finds_mate_in_one(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        self.assertEqual(self.bot.get_best_move(board, 2.0), chess.Move.from_uci("e1e8"))

    def test_returns_a_legal_move(self):
        board = chess.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        self.assertIn(self.bot.get_best_move(board, 2.0), board.legal_moves)

    def test_search_leaves_the_caller_board_untouched(self):
        board = chess.Board()
        fen_before = board.fen()
        self.bot.get_best_move(board, 1.0)
        self.assertEqual(board.fen(), fen_before)

    def test_no_move_when_the_game_is_over(self):
        board = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertIsNone(self.bot.get_best_move(board, 1.0))


class TestMoveOrdering(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareFast()

    def test_ordering_preserves_every_move(self):
        board = chess.Board()
        moves = list(board.legal_moves)
        self.assertCountEqual(self.bot.order_moves(board, moves), moves)

    def test_valuable_captures_come_first(self):
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
        ordered = self.bot.order_moves(board, list(board.legal_moves))
        self.assertEqual(ordered[0], chess.Move.from_uci("e4d5"))

    def test_shallow_search_keeps_the_best_capture(self):
        """The depth<=2 trim must run on ordered moves, not raw ones"""
        board = chess.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        best_capture = chess.Move.from_uci("e2a6")
        raw = list(board.legal_moves)
        self.assertNotIn(best_capture, raw[:10], "position no longer exercises the trim")
        self.assertIn(best_capture, self.bot.order_moves(board, raw)[:10])

    def test_ordering_leaves_board_unchanged(self):
        board = chess.Board()
        fen_before = board.fen()
        self.bot.order_moves(board, list(board.legal_moves))
        self.assertEqual(board.fen(), fen_before)


class TestTranspositionTable(unittest.TestCase):
    FENS = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    ]

    def search(self, fen, depth, use_tt):
        board = chess.Board(fen)
        bot = KnightmareFast()
        if not use_tt:
            bot.store_tt = lambda *args, **kwargs: None
        score, _ = bot.minimax(board, depth, -INFINITY, INFINITY, board.turn == chess.WHITE)
        return score, bot.nodes

    def test_cached_bounds_do_not_change_the_result(self):
        for fen in self.FENS:
            with self.subTest(fen=fen):
                self.assertEqual(
                    self.search(fen, 4, use_tt=True)[0],
                    self.search(fen, 4, use_tt=False)[0],
                )

    def test_table_is_actually_populated(self):
        bot = KnightmareFast()
        board = chess.Board()
        bot.minimax(board, 3, -INFINITY, INFINITY, True)
        self.assertGreater(len(bot.transposition_table), 0)

    def test_table_stops_growing_at_the_cap(self):
        bot = KnightmareFast()
        bot.transposition_table = {i: (0, None, TT_EXACT) for i in range(TT_MAX_ENTRIES)}
        bot.store_tt(("overflow",), 10, None, TT_EXACT)
        self.assertNotIn(("overflow",), bot.transposition_table)

    def test_reset_clears_the_table(self):
        bot = KnightmareFast()
        bot.store_tt(("key",), 1, None, TT_EXACT)
        bot.reset()
        self.assertEqual(bot.transposition_table, {})


class TestPieceSquareValues(unittest.TestCase):
    def test_pawns_are_rewarded_for_advancing(self):
        near = get_piece_square_value(chess.PAWN, chess.A2, chess.WHITE)
        far = get_piece_square_value(chess.PAWN, chess.A7, chess.WHITE)
        self.assertGreater(far, near)

    def test_pawn_advancement_is_mirrored_for_black(self):
        white = get_piece_square_value(chess.PAWN, chess.A7, chess.WHITE)
        black = get_piece_square_value(chess.PAWN, chess.A2, chess.BLACK)
        self.assertEqual(white, black)

    def test_knights_prefer_the_centre(self):
        centre = get_piece_square_value(chess.KNIGHT, chess.D4, chess.WHITE)
        corner = get_piece_square_value(chess.KNIGHT, chess.A1, chess.WHITE)
        self.assertGreater(centre, corner)

    def test_king_seeks_the_centre_only_in_the_endgame(self):
        middlegame = get_piece_square_value(chess.KING, chess.D4, chess.WHITE, endgame=False)
        endgame = get_piece_square_value(chess.KING, chess.D4, chess.WHITE, endgame=True)
        self.assertGreater(endgame, middlegame)

    def test_piece_values_are_ordered_sensibly(self):
        self.assertLess(PIECE_VALUES[chess.PAWN], PIECE_VALUES[chess.KNIGHT])
        self.assertLess(PIECE_VALUES[chess.KNIGHT], PIECE_VALUES[chess.ROOK])
        self.assertLess(PIECE_VALUES[chess.ROOK], PIECE_VALUES[chess.QUEEN])
        self.assertLess(PIECE_VALUES[chess.QUEEN], PIECE_VALUES[chess.KING])


class TestEndgameDetection(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareFast()

    def test_opening_is_not_endgame(self):
        self.assertFalse(self.bot.is_endgame(chess.Board()))

    def test_bare_kings_and_pawns_is_endgame(self):
        self.assertTrue(self.bot.is_endgame(chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")))


if __name__ == "__main__":
    unittest.main()
