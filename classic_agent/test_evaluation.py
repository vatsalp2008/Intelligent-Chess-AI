#!/usr/bin/env python3
"""
Unit tests for the Knightmare evaluation and search helpers.

Run with:
    python3 -m unittest test_evaluation
"""

import unittest

import chess

from knightmare_bot import (
    BISHOP_PAIR_BONUS,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MOVE_TIME,
    ISOLATED_PAWN_PENALTY,
    KING_ENDGAME_TABLE,
    MATE_SCORE,
    PASSED_PAWN_BONUS,
    MAX_MOVE_TIME,
    MAX_SEARCH_DEPTH,
    PIECE_SQUARE_TABLES,
    ROOK_HALF_OPEN_FILE_BONUS,
    ROOK_OPEN_FILE_BONUS,
    SEE_PIECE_VALUES,
    TT_MAX_ENTRIES,
    KnightmareBot,
    format_score,
    is_passed_pawn,
    parse_go,
    parse_position,
    piece_square_bonus,
    static_exchange_eval,
    cheapest_attacker_move,
)

INFINITY = float("inf")


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


class TestPieceSquareTables(unittest.TestCase):
    """Table orientation is easy to get backwards, so pin it down"""

    def setUp(self):
        self.bot = KnightmareBot()

    def test_every_table_covers_the_board(self):
        for piece_type, table in PIECE_SQUARE_TABLES.items():
            with self.subTest(piece_type=piece_type):
                self.assertEqual(len(table), 64)
        self.assertEqual(len(KING_ENDGAME_TABLE), 64)

    def test_knights_prefer_the_centre_to_the_rim(self):
        centre = piece_square_bonus(chess.KNIGHT, chess.D4, chess.WHITE)
        rim = piece_square_bonus(chess.KNIGHT, chess.A1, chess.WHITE)
        self.assertGreater(centre, rim)

    def test_advanced_pawns_score_higher(self):
        for color, near, far in (
            (chess.WHITE, chess.E2, chess.E7),
            (chess.BLACK, chess.E7, chess.E2),
        ):
            with self.subTest(color=color):
                self.assertGreater(
                    piece_square_bonus(chess.PAWN, far, color),
                    piece_square_bonus(chess.PAWN, near, color),
                )

    def test_tables_are_mirrored_for_black(self):
        """Black on the mirrored square must score exactly as White does"""
        for piece_type in PIECE_SQUARE_TABLES:
            for square in (chess.A1, chess.D4, chess.G1, chess.H7, chess.C6):
                with self.subTest(piece_type=piece_type, square=square):
                    self.assertEqual(
                        piece_square_bonus(piece_type, square, chess.WHITE),
                        piece_square_bonus(piece_type, chess.square_mirror(square), chess.BLACK),
                    )

    def test_king_swaps_shelter_for_activity_in_the_endgame(self):
        corner_mid = piece_square_bonus(chess.KING, chess.G1, chess.WHITE, endgame=False)
        corner_end = piece_square_bonus(chess.KING, chess.G1, chess.WHITE, endgame=True)
        centre_end = piece_square_bonus(chess.KING, chess.E4, chess.WHITE, endgame=True)
        self.assertGreater(corner_mid, corner_end)
        self.assertGreater(centre_end, corner_end)

    def test_evaluation_is_colour_symmetric(self):
        """A mirrored position must evaluate to exactly the opposite score"""
        for fen in (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
            "8/5k2/8/3K4/8/8/4P3/8 w - - 0 1",
        ):
            with self.subTest(fen=fen):
                board = chess.Board(fen)
                self.assertEqual(self.bot.evaluate(board), -self.bot.evaluate(board.mirror()))

    def test_developed_knight_beats_undeveloped_one(self):
        """A knight on f3 should read better than one still sat on b1

        Pawns are present so the position is not written off as
        insufficient material before the placement terms are reached.
        """
        developed = chess.Board("4k3/pppppppp/8/8/8/5N2/PPPPPPPP/4K3 w - - 0 1")
        home = chess.Board("4k3/pppppppp/8/8/8/8/PPPPPPPP/1N2K3 w - - 0 1")
        self.assertGreater(self.bot.evaluate(developed), self.bot.evaluate(home))


class TestPassedPawns(unittest.TestCase):
    def test_lone_pawn_is_passed(self):
        board = chess.Board("4k3/8/8/4P3/8/8/8/4K3 w - - 0 1")
        self.assertTrue(is_passed_pawn(chess.E5, chess.WHITE, board.pieces(chess.PAWN, chess.BLACK)))

    def test_enemy_pawn_ahead_on_the_same_file_blocks(self):
        board = chess.Board("4k3/4p3/8/4P3/8/8/8/4K3 w - - 0 1")
        self.assertFalse(is_passed_pawn(chess.E5, chess.WHITE, board.pieces(chess.PAWN, chess.BLACK)))

    def test_enemy_pawn_ahead_on_an_adjacent_file_blocks(self):
        board = chess.Board("4k3/5p2/8/4P3/8/8/8/4K3 w - - 0 1")
        self.assertFalse(is_passed_pawn(chess.E5, chess.WHITE, board.pieces(chess.PAWN, chess.BLACK)))

    def test_enemy_pawn_behind_does_not_block(self):
        """A pawn that has already been passed cannot come back"""
        board = chess.Board("4k3/8/8/4P3/8/4p3/8/4K3 w - - 0 1")
        self.assertTrue(is_passed_pawn(chess.E5, chess.WHITE, board.pieces(chess.PAWN, chess.BLACK)))

    def test_distant_file_does_not_block(self):
        board = chess.Board("4k3/1p6/8/4P3/8/8/8/4K3 w - - 0 1")
        self.assertTrue(is_passed_pawn(chess.E5, chess.WHITE, board.pieces(chess.PAWN, chess.BLACK)))

    def test_black_passers_are_detected_the_same_way(self):
        board = chess.Board("4k3/8/8/4p3/8/8/8/4K3 w - - 0 1")
        self.assertTrue(is_passed_pawn(chess.E5, chess.BLACK, board.pieces(chess.PAWN, chess.WHITE)))
        blocked = chess.Board("4k3/8/8/4p3/8/8/4P3/4K3 w - - 0 1")
        self.assertFalse(
            is_passed_pawn(chess.E5, chess.BLACK, blocked.pieces(chess.PAWN, chess.WHITE))
        )

    def test_advanced_passers_are_worth_more(self):
        bot = KnightmareBot()

        def score_at(square):
            board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
            board.set_piece_at(square, chess.Piece(chess.PAWN, chess.WHITE))
            return bot.pawn_structure_score(board, chess.WHITE)

        self.assertGreater(score_at(chess.E7), score_at(chess.E5))
        self.assertGreater(score_at(chess.E5), score_at(chess.E2))


class TestPawnStructurePenalties(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def score(self, fen, color=chess.WHITE):
        return self.bot.pawn_structure_score(chess.Board(fen), color)

    def test_doubled_pawns_are_penalised(self):
        healthy = self.score("4k3/8/8/8/8/8/3PP3/4K3 w - - 0 1")
        doubled = self.score("4k3/8/8/8/3P4/8/3PP3/4K3 w - - 0 1")
        # The extra pawn adds a passer bonus, so compare against that
        extra_passer = PASSED_PAWN_BONUS[3]
        self.assertLess(doubled, healthy + extra_passer)

    def test_isolated_pawns_are_penalised(self):
        connected = self.score("4k3/8/8/8/8/8/3PP3/4K3 w - - 0 1")
        isolated = self.score("4k3/8/8/8/8/8/P6P/4K3 w - - 0 1")
        self.assertLess(isolated, connected)

    def test_a_single_pawn_counts_as_isolated(self):
        lone = self.score("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        self.assertEqual(lone, PASSED_PAWN_BONUS[1] - ISOLATED_PAWN_PENALTY)

    def test_neighbouring_pawn_prevents_isolation(self):
        self.assertEqual(
            self.score("4k3/8/8/8/8/8/3PP3/4K3 w - - 0 1"),
            2 * PASSED_PAWN_BONUS[1],
        )

    def test_structure_is_scored_the_same_for_both_colours(self):
        white = self.score("4k3/8/8/8/8/8/P6P/4K3 w - - 0 1", chess.WHITE)
        black = self.score("4k3/p6p/8/8/8/8/8/4K3 w - - 0 1", chess.BLACK)
        self.assertEqual(white, black)


class TestRookFiles(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def score(self, fen, color=chess.WHITE):
        return self.bot.rook_file_score(chess.Board(fen), color)

    def test_file_with_no_pawns_is_open(self):
        self.assertEqual(
            self.score("4k3/8/8/8/8/8/4P3/4KR2 w - - 0 1"), ROOK_OPEN_FILE_BONUS
        )

    def test_file_with_only_enemy_pawns_is_half_open(self):
        self.assertEqual(
            self.score("4k3/5p2/8/8/8/8/8/4KR2 w - - 0 1"), ROOK_HALF_OPEN_FILE_BONUS
        )

    def test_own_pawn_blocks_the_file(self):
        self.assertEqual(self.score("4k3/8/8/8/8/8/5P2/4KR2 w - - 0 1"), 0)

    def test_enemy_pawn_on_another_file_does_not_count(self):
        """Only the rook's own file matters"""
        self.assertEqual(
            self.score("4k3/4p3/8/8/8/8/8/4KR2 w - - 0 1"), ROOK_OPEN_FILE_BONUS
        )

    def test_open_file_beats_half_open(self):
        self.assertGreater(ROOK_OPEN_FILE_BONUS, ROOK_HALF_OPEN_FILE_BONUS)

    def test_each_rook_is_counted(self):
        both = self.score("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
        self.assertEqual(both, 2 * ROOK_OPEN_FILE_BONUS)

    def test_scored_the_same_for_black(self):
        white = self.score("4k3/8/8/8/8/8/8/4KR2 w - - 0 1", chess.WHITE)
        black = self.score("4kr2/8/8/8/8/8/8/4K3 w - - 0 1", chess.BLACK)
        self.assertEqual(white, black)

    def test_no_rooks_scores_nothing(self):
        self.assertEqual(self.score("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"), 0)


class TestEndgameDetection(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_opening_is_not_an_endgame(self):
        self.assertFalse(self.bot.is_endgame(chess.Board()))

    def test_position_without_queens_is_an_endgame(self):
        self.assertTrue(self.bot.is_endgame(chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")))

    def test_queens_with_few_pieces_is_an_endgame(self):
        self.assertTrue(self.bot.is_endgame(chess.Board("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")))

    def test_queens_with_a_full_board_is_not(self):
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        self.assertFalse(self.bot.is_endgame(chess.Board(fen)))


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


class TestStaticExchangeEvaluation(unittest.TestCase):
    """Playing an exchange out is easy to get subtly wrong"""

    def see(self, fen, uci):
        board = chess.Board(fen)
        before = board.fen()
        value = static_exchange_eval(board, chess.Move.from_uci(uci))
        self.assertEqual(board.fen(), before, "SEE must not mutate the board")
        return value

    def test_capturing_a_free_queen_wins_a_queen(self):
        self.assertEqual(
            self.see("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1", "e4d5"),
            SEE_PIECE_VALUES[chess.QUEEN],
        )

    def test_capturing_a_free_pawn_wins_a_pawn(self):
        self.assertEqual(
            self.see("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5"),
            SEE_PIECE_VALUES[chess.PAWN],
        )

    def test_even_pawn_trade_is_worth_nothing(self):
        self.assertEqual(self.see("4k3/8/2p5/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5"), 0)

    def test_queen_takes_defended_pawn_loses_material(self):
        """QxP with the pawn defended drops the queen for a pawn"""
        value = self.see("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1", "d1d5")
        self.assertEqual(
            value, SEE_PIECE_VALUES[chess.PAWN] - SEE_PIECE_VALUES[chess.QUEEN]
        )

    def test_rook_takes_defended_pawn_loses_material(self):
        value = self.see("4k3/3r4/8/3p4/8/8/8/3RK3 w - - 0 1", "d1d5")
        self.assertEqual(
            value, SEE_PIECE_VALUES[chess.PAWN] - SEE_PIECE_VALUES[chess.ROOK]
        )

    def test_cheapest_attacker_recaptures_first(self):
        """White has just captured on d5; Black should recapture with the pawn

        Both the c6 pawn and the d7 rook can take, and the pawn is the
        cheaper piece to commit to the exchange.
        """
        board = chess.Board("4k3/3r4/2p5/3P4/8/8/8/3RK3 b - - 0 1")
        move = cheapest_attacker_move(board, chess.D5, chess.BLACK)
        self.assertEqual(move, chess.Move.from_uci("c6d5"))

    def test_only_attacker_is_used_when_there_is_one_choice(self):
        board = chess.Board("4k3/3r4/8/3P4/8/8/8/4K3 b - - 0 1")
        move = cheapest_attacker_move(board, chess.D5, chess.BLACK)
        self.assertEqual(move, chess.Move.from_uci("d7d5"))

    def test_no_attacker_returns_nothing(self):
        board = chess.Board("4k3/8/8/3p4/8/8/8/4K3 w - - 0 1")
        self.assertIsNone(cheapest_attacker_move(board, chess.D5, chess.WHITE))

    def test_own_piece_on_the_square_is_not_capturable(self):
        """A side cannot capture its own piece, so there is no recapture"""
        board = chess.Board("4k3/3r4/2p5/3p4/8/8/8/3RK3 b - - 0 1")
        self.assertIsNone(cheapest_attacker_move(board, chess.D5, chess.BLACK))

    def test_non_capture_scores_zero(self):
        self.assertEqual(self.see("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1", "e2e4"), 0)

    def test_losing_captures_sort_below_quiet_moves(self):
        """The whole point: QxP defended must not be tried first"""
        bot = KnightmareBot()
        board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
        ordered = bot.order_moves(board, list(board.legal_moves))
        self.assertEqual(ordered[-1], chess.Move.from_uci("d1d5"))

    def test_winning_captures_sort_first(self):
        bot = KnightmareBot()
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
        ordered = bot.order_moves(board, list(board.legal_moves))
        self.assertEqual(ordered[0], chess.Move.from_uci("e4d5"))

    def test_quiescence_skips_losing_captures(self):
        """Resolving a capture the side to move would never play is wasted"""
        bot = KnightmareBot()
        board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
        quiet = bot.quiesce(board, -INFINITY, INFINITY, 0)
        self.assertEqual(quiet, bot.evaluate(board, 0))


class TestQuiescence(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()
        # Qxd5 wins a pawn but loses the queen to cxd5
        self.after_bad_capture = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
        self.after_bad_capture.push(chess.Move.from_uci("d1d5"))

    def test_resolves_recapture_the_static_eval_misses(self):
        static = self.bot.evaluate(self.after_bad_capture, 1)
        quiet = self.bot.quiesce(self.after_bad_capture, -INFINITY, INFINITY, 1)
        self.assertGreater(static, 0, "static eval should look good for White")
        self.assertLess(quiet, static, "quiescence should see the queen falling")

    def test_avoids_the_losing_capture(self):
        board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
        self.assertNotEqual(self.bot.get_move(board, time_limit=1.0), chess.Move.from_uci("d1d5"))

    def test_quiet_position_returns_static_eval(self):
        """With no captures available there is nothing to resolve"""
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(
            self.bot.quiesce(board, -INFINITY, INFINITY, 0),
            self.bot.evaluate(board, 0),
        )

    def test_leaves_board_unchanged(self):
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        fen_before = board.fen()
        self.bot.quiesce(board, -INFINITY, INFINITY, 0)
        self.assertEqual(board.fen(), fen_before)


class TestTranspositionTable(unittest.TestCase):
    FENS = [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "8/5k2/8/3K4/8/8/4P3/8 w - - 0 1",
    ]

    def search(self, board, depth, use_tt):
        bot = KnightmareBot()
        if not use_tt:
            bot.store_tt = lambda *args, **kwargs: None
        score, _ = bot.minimax(board.copy(), depth, -INFINITY, INFINITY, board.turn == chess.WHITE)
        return score, bot.nodes

    def test_table_does_not_change_the_score(self):
        """Cached bounds must only ever be reused when they are still valid"""
        for fen in self.FENS:
            with self.subTest(fen=fen):
                board = chess.Board(fen)
                with_tt, _ = self.search(board, 4, use_tt=True)
                without_tt, _ = self.search(board, 4, use_tt=False)
                self.assertEqual(with_tt, without_tt)

    def test_table_saves_work(self):
        board = chess.Board(self.FENS[0])
        _, nodes_with = self.search(board, 4, use_tt=True)
        _, nodes_without = self.search(board, 4, use_tt=False)
        self.assertLess(nodes_with, nodes_without)

    def test_mate_scores_are_not_cached(self):
        """Mate scores are ply-relative and would be wrong elsewhere"""
        bot = KnightmareBot()
        bot.store_tt(("key",), MATE_SCORE - 3, None, "exact")
        self.assertEqual(bot.transposition_table, {})

    def test_ordinary_scores_are_cached(self):
        bot = KnightmareBot()
        bot.store_tt(("key",), 120, None, "exact")
        self.assertIn(("key",), bot.transposition_table)

    def test_table_stops_growing_at_the_cap(self):
        bot = KnightmareBot()
        bot.transposition_table = {i: (0, None, "exact") for i in range(TT_MAX_ENTRIES)}
        bot.store_tt(("overflow",), 10, None, "exact")
        self.assertNotIn(("overflow",), bot.transposition_table)


class TestPrincipalVariation(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_pv_moves_are_legal_in_sequence(self):
        board = chess.Board()
        self.bot.get_move(board, 60.0, 3)

        scratch = board.copy()
        for move in self.bot.extract_pv(board, 3):
            self.assertIn(move, scratch.legal_moves)
            scratch.push(move)

    def test_pv_starts_with_the_chosen_move(self):
        board = chess.Board()
        best = self.bot.get_move(board, 60.0, 3)
        pv = self.bot.extract_pv(board, 3)
        self.assertTrue(pv)
        self.assertEqual(pv[0], best)

    def test_pv_is_no_longer_than_the_depth(self):
        board = chess.Board()
        self.bot.get_move(board, 60.0, 3)
        self.assertLessEqual(len(self.bot.extract_pv(board, 3)), 3)

    def test_extraction_does_not_change_the_board(self):
        board = chess.Board()
        self.bot.get_move(board, 60.0, 3)
        before = board.fen()
        self.bot.extract_pv(board, 3)
        self.assertEqual(board.fen(), before)

    def test_empty_table_gives_an_empty_line(self):
        self.assertEqual(self.bot.extract_pv(chess.Board(), 4), [])

    def test_extraction_stops_on_a_repeated_position(self):
        """A cycle in the table must not loop forever"""
        board = chess.Board()
        key = board._transposition_key()
        # Point every depth at a move that returns to the same position type
        for depth in range(1, 5):
            self.bot.transposition_table[(key, depth)] = (
                0, chess.Move.from_uci("g1f3"), "exact"
            )
        pv = self.bot.extract_pv(board, 4)
        self.assertLessEqual(len(pv), 4)

    def test_ignores_a_stored_move_that_is_not_legal(self):
        board = chess.Board()
        key = board._transposition_key()
        self.bot.transposition_table[(key, 2)] = (0, chess.Move.from_uci("a1a8"), "exact")
        self.assertEqual(self.bot.extract_pv(board, 2), [])


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


class TestGoParsing(unittest.TestCase):
    def test_bare_go_uses_defaults(self):
        self.assertEqual(parse_go("go"), (DEFAULT_MOVE_TIME, DEFAULT_MAX_DEPTH))

    def test_movetime_is_converted_to_seconds(self):
        self.assertEqual(parse_go("go movetime 500")[0], 0.5)

    def test_movetime_is_clamped(self):
        self.assertEqual(parse_go("go movetime 1")[0], 0.1)
        self.assertEqual(parse_go("go movetime 99999")[0], MAX_MOVE_TIME)

    def test_depth_is_honoured_and_capped(self):
        self.assertEqual(parse_go("go depth 2")[1], 2)
        self.assertEqual(parse_go("go depth 999")[1], MAX_SEARCH_DEPTH)

    def test_movetime_wins_over_depth_clock(self):
        """An explicit movetime still bounds an explicit depth request"""
        self.assertEqual(parse_go("go depth 3 movetime 2000"), (2.0, 3))

    def test_malformed_tokens_fall_back_to_defaults(self):
        for line in ("go depth", "go depth abc", "go movetime", "go depth 0", "go movetime x"):
            with self.subTest(line=line):
                self.assertEqual(parse_go(line), (DEFAULT_MOVE_TIME, DEFAULT_MAX_DEPTH))

    def test_infinite_thinks_for_the_maximum(self):
        self.assertEqual(parse_go("go infinite")[0], MAX_MOVE_TIME)

    def test_clock_is_split_across_expected_moves(self):
        """60s with 30 moves to go is about 2s per move"""
        self.assertAlmostEqual(parse_go("go wtime 60000 btime 60000", True)[0], 2.0, places=2)

    def test_uses_the_clock_of_the_side_to_move(self):
        line = "go wtime 300000 btime 60000"
        white_budget = parse_go(line, white_to_move=True)[0]
        black_budget = parse_go(line, white_to_move=False)[0]
        self.assertGreater(white_budget, black_budget)

    def test_low_clock_produces_a_short_search(self):
        """Almost out of time means move quickly rather than flag"""
        self.assertLess(parse_go("go wtime 2000 btime 300000", True)[0], 1.0)

    def test_never_spends_most_of_the_remaining_clock(self):
        budget = parse_go("go wtime 1000 btime 1000 movestogo 1", True)[0]
        self.assertLessEqual(budget, 0.4)

    def test_increment_is_added_to_the_budget(self):
        without = parse_go("go wtime 60000 btime 60000", True)[0]
        with_inc = parse_go("go wtime 60000 btime 60000 winc 5000", True)[0]
        self.assertGreater(with_inc, without)


class TestScoreFormatting(unittest.TestCase):
    def test_centipawn_scores(self):
        self.assertEqual(format_score(0), "cp 0")
        self.assertEqual(format_score(-240), "cp -240")

    def test_mate_scores_are_reported_in_moves(self):
        self.assertEqual(format_score(MATE_SCORE), "mate 1")
        self.assertEqual(format_score(MATE_SCORE - 3), "mate 2")

    def test_getting_mated_is_negative(self):
        self.assertTrue(format_score(-(MATE_SCORE - 3)).startswith("mate -"))


class TestPositionParsing(unittest.TestCase):
    def test_startpos(self):
        self.assertEqual(parse_position("position startpos").fen(), chess.Board().fen())

    def test_startpos_with_moves(self):
        board = parse_position("position startpos moves e2e4 e7e5")
        self.assertEqual(board.piece_at(chess.E4), chess.Piece(chess.PAWN, chess.WHITE))
        self.assertEqual(board.piece_at(chess.E5), chess.Piece(chess.PAWN, chess.BLACK))

    def test_fen_position(self):
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        self.assertEqual(parse_position(f"position fen {fen}").fen(), fen)

    def test_illegal_move_stops_replay(self):
        """A bogus move must not corrupt the board"""
        board = parse_position("position startpos moves e2e4 e2e4")
        self.assertEqual(board.piece_at(chess.E4), chess.Piece(chess.PAWN, chess.WHITE))
        self.assertEqual(len(board.move_stack), 1)

    def test_invalid_fen_falls_back_to_startpos(self):
        self.assertEqual(parse_position("position fen total-nonsense").fen(), chess.Board().fen())


if __name__ == "__main__":
    unittest.main()
