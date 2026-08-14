#!/usr/bin/env python3
"""
Unit tests for the Knightmare evaluation and search helpers.

Run with:
    python3 -m unittest test_evaluation
"""

import unittest

import chess

from knightmare_bot import BISHOP_PAIR_BONUS, MATE_SCORE, KnightmareBot


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_starting_position_is_balanced(self):
        """Material is equal at the start, so only the mobility term applies"""
        board = chess.Board()
        mobility = len(list(board.legal_moves)) * 3
        self.assertEqual(self.bot.evaluate(board), mobility)

    def test_extra_material_favours_owner(self):
        """A side up a queen should be evaluated well ahead"""
        white_up = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        black_up = chess.Board("3qk3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertGreater(self.bot.evaluate(white_up), 0)
        self.assertLess(self.bot.evaluate(black_up), 0)

    def test_checkmate_scores_are_decisive(self):
        """Checkmate returns a large score against the side to move"""
        black_mated = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1")
        black_mated.push(chess.Move.from_uci("g8h8"))
        black_mated.push(chess.Move.from_uci("e1e8"))
        self.assertTrue(black_mated.is_checkmate())
        self.assertEqual(self.bot.evaluate(black_mated), 10000)

    def test_stalemate_is_a_draw(self):
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(board.is_stalemate())
        self.assertEqual(self.bot.evaluate(board), 0)

    def test_bishop_pair_bonus_applied(self):
        """Two bishops beat bishop plus knight by the pair bonus"""
        pair = chess.Board("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1")
        no_pair = chess.Board("4k3/8/8/8/8/8/8/2B1KN2 w - - 0 1")
        difference = self.bot.evaluate(pair) - self.bot.evaluate(no_pair)
        self.assertGreaterEqual(difference, BISHOP_PAIR_BONUS)


class TestMateScoring(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()
        # Black is mated; White delivered it
        self.mated = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")

    def test_mate_is_worth_less_the_deeper_it_is(self):
        """A mate found further away must score below a nearer one"""
        near = self.bot.evaluate(self.mated, ply=2)
        far = self.bot.evaluate(self.mated, ply=8)
        self.assertGreater(near, far)

    def test_mate_score_magnitude(self):
        self.assertEqual(self.bot.evaluate(self.mated, ply=0), MATE_SCORE)
        self.assertEqual(self.bot.evaluate(self.mated, ply=5), MATE_SCORE - 5)

    def test_being_mated_is_scored_from_the_losers_view(self):
        """White mated means a large negative score"""
        white_mated = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4r1K1 w - - 0 1")
        self.assertTrue(white_mated.is_checkmate())
        self.assertEqual(white_mated.turn, chess.WHITE)
        self.assertEqual(self.bot.evaluate(white_mated, ply=0), -MATE_SCORE)

    def test_prefers_immediate_mate_over_slower_one(self):
        """Re8# is mate now; the engine must not dawdle"""
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        self.assertEqual(self.bot.get_move(board, time_limit=1.0), chess.Move.from_uci("e1e8"))


class TestDrawDetection(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_fifty_move_position_is_drawn(self):
        """A big material lead is still a draw once the clock runs out"""
        board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 100 60")
        self.assertEqual(self.bot.evaluate(board), 0)

    def test_material_lead_scores_above_zero_before_the_clock_expires(self):
        board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        self.assertGreater(self.bot.evaluate(board), 0)

    def test_threefold_repetition_is_drawn(self):
        """Shuffling in a winning position must not look winning"""
        board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        for uci in ("d1d2", "e8e7", "d2d1", "e7e8") * 2:
            board.push(chess.Move.from_uci(uci))
        self.assertTrue(board.is_repetition(3))
        self.assertEqual(self.bot.evaluate(board), 0)


class TestMoveOrdering(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_ordering_keeps_every_move(self):
        board = chess.Board()
        moves = list(board.legal_moves)
        ordered = self.bot.order_moves(board, moves)
        self.assertCountEqual(ordered, moves)

    def test_captures_are_tried_first(self):
        """A free queen capture should be the first move considered"""
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
        ordered = self.bot.order_moves(board, list(board.legal_moves))
        self.assertEqual(ordered[0], chess.Move.from_uci("e4d5"))

    def test_record_cutoff_ignores_captures(self):
        """Only quiet moves belong in the killer move table"""
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
        self.bot.record_cutoff(board, chess.Move.from_uci("e4d5"), depth=2, ply=0)
        self.assertEqual(self.bot.killer_moves.get(0, []), [])

    def test_record_cutoff_stores_quiet_move(self):
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        self.bot.record_cutoff(board, move, depth=3, ply=1)
        self.assertIn(move, self.bot.killer_moves[1])
        self.assertEqual(self.bot.history_table[(move.from_square, move.to_square)], 3)

    def test_killer_table_keeps_at_most_two_moves(self):
        board = chess.Board()
        for uci in ("e2e4", "d2d4", "g1f3", "b1c3"):
            self.bot.record_cutoff(board, chess.Move.from_uci(uci), depth=1, ply=0)
        self.assertLessEqual(len(self.bot.killer_moves[0]), 2)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_finds_mate_in_one(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        self.assertEqual(self.bot.get_move(board, time_limit=1.0), chess.Move.from_uci("e1e8"))

    def test_search_leaves_board_untouched(self):
        board = chess.Board()
        fen_before = board.fen()
        self.bot.get_move(board, time_limit=0.5)
        self.assertEqual(board.fen(), fen_before)

    def test_returns_legal_move(self):
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        move = self.bot.get_move(board, time_limit=0.5)
        self.assertIn(move, board.legal_moves)

    def test_no_move_when_game_over(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("e1e8"))
        self.assertIsNone(self.bot.get_move(board, time_limit=0.5))


if __name__ == "__main__":
    unittest.main()
