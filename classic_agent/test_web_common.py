#!/usr/bin/env python3
"""
Tests for the board presentation both web interfaces share.

These functions depend only on a position, so they can be tested without
starting a server. The takeback arithmetic is the part worth pinning down:
it has to count whole move pairs, work for either colour, and refuse to
unwind past the point where the asking side has nothing of its own left.

Run with:
    python3 -m unittest test_web_common
"""

import unittest

import chess

from web_common import (
    BOARD_SIZE,
    draw_text,
    game_finished,
    legal_by_origin,
    moves_by,
    player_result_text,
    plies_to_take_back,
    render_board,
)


def board_after(*ucis, fen=None):
    board = chess.Board(fen) if fen else chess.Board()
    for uci in ucis:
        board.push(chess.Move.from_uci(uci))
    return board


class TestLegalByOrigin(unittest.TestCase):
    def test_every_legal_move_is_listed(self):
        board = chess.Board()
        listed = sum(len(v) for v in legal_by_origin(board).values())
        self.assertEqual(listed, board.legal_moves.count())

    def test_moves_are_grouped_by_their_origin(self):
        self.assertEqual(sorted(legal_by_origin(chess.Board())['e2']),
                         ['e2e3', 'e2e4'])

    def test_only_squares_that_can_move_appear(self):
        """The opening position has eight pawns and two knights"""
        self.assertEqual(len(legal_by_origin(chess.Board())), 10)

    def test_promotions_are_listed_in_full(self):
        """The client has to be able to offer the choice of piece"""
        board = chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.assertEqual(sorted(legal_by_origin(board)['a7']),
                         ['a7a8b', 'a7a8n', 'a7a8q', 'a7a8r'])

    def test_a_finished_game_lists_nothing(self):
        board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertTrue(board.is_checkmate())
        self.assertEqual(legal_by_origin(board), {})

    def test_being_in_check_narrows_the_options(self):
        board = chess.Board('4k3/8/8/8/7q/8/8/4K3 w - - 0 1')
        listed = sum(len(v) for v in legal_by_origin(board).values())
        self.assertEqual(listed, board.legal_moves.count())
        self.assertLess(listed, 10)


class TestRenderBoard(unittest.TestCase):
    def test_it_produces_an_svg(self):
        self.assertIn('<svg', render_board(chess.Board()))

    def test_the_size_is_applied(self):
        self.assertIn(f'width="{BOARD_SIZE}"', render_board(chess.Board()))
        self.assertIn('width="200"', render_board(chess.Board(), size=200))

    def test_a_fresh_board_marks_no_last_move(self):
        self.assertNotIn('lastmove', render_board(chess.Board()))

    def test_the_last_move_is_marked(self):
        self.assertIn('lastmove', render_board(board_after('e2e4')))

    def test_a_king_in_check_is_marked(self):
        board = board_after('f2f3', 'e7e5', 'g2g4', 'd8h4')
        self.assertTrue(board.is_check())
        self.assertIn('check', render_board(board))

    def test_a_quiet_position_marks_no_check(self):
        self.assertNotIn('check', render_board(board_after('e2e4')))

    def test_flipping_changes_the_drawing(self):
        board = chess.Board()
        self.assertNotEqual(render_board(board), render_board(board, flipped=True))

    def test_flipping_puts_h1_at_the_top(self):
        """Squares keep their own names, so clicks still map correctly"""
        import re

        def top_left(svg):
            squares = re.findall(
                r'<rect x="(\d+)" y="(\d+)"[^>]*class="square [a-z]+ ([a-h][1-8])"', svg)
            return min(squares, key=lambda s: (int(s[1]), int(s[0])))[2]

        self.assertEqual(top_left(render_board(chess.Board())), 'a8')
        self.assertEqual(top_left(render_board(chess.Board(), flipped=True)), 'h1')

    def test_the_board_is_not_disturbed(self):
        board = board_after('e2e4', 'e7e5')
        before = board.fen()
        render_board(board)
        self.assertEqual(board.fen(), before)


class TestDrawText(unittest.TestCase):
    def test_a_live_game_is_not_drawn(self):
        self.assertIsNone(draw_text(chess.Board()))

    def test_checkmate_is_not_a_draw(self):
        board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertIsNone(draw_text(board))

    def test_stalemate_is_named(self):
        board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
        self.assertTrue(board.is_stalemate())
        self.assertIn('Stalemate', draw_text(board))

    def test_insufficient_material_is_named(self):
        self.assertIn('Insufficient',
                      draw_text(chess.Board('4k3/8/8/8/8/8/8/4K3 w - - 0 1')))

    def test_the_fifty_move_rule_is_named(self):
        board = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 100 60')
        self.assertIn('50 move', draw_text(board))

    def test_stalemate_wins_over_other_conditions(self):
        """python-chess reports several at once, and this is the useful one"""
        board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
        self.assertIn('Stalemate', draw_text(board))


class TestGameFinished(unittest.TestCase):
    """Claimable draws are still the end of the game"""

    def test_a_live_game_is_not_finished(self):
        self.assertFalse(game_finished(chess.Board()))

    def test_checkmate_finishes_it(self):
        self.assertTrue(game_finished(
            chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')))

    def test_stalemate_finishes_it(self):
        self.assertTrue(game_finished(chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')))

    def test_the_fifty_move_rule_finishes_it(self):
        """is_game_over() alone says False here, because it is claimable"""
        board = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 100 60')
        self.assertFalse(board.is_game_over())
        self.assertTrue(game_finished(board))


class TestPlayerResultText(unittest.TestCase):
    def test_a_live_game_has_no_result(self):
        self.assertIsNone(player_result_text(chess.Board(), chess.WHITE))

    def test_being_mated_says_you_lost(self):
        board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertEqual(player_result_text(board, chess.BLACK),
                         'Checkmate - you lost')

    def test_mating_says_you_won(self):
        board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertEqual(player_result_text(board, chess.WHITE),
                         'Checkmate - you win!')

    def test_a_draw_is_not_a_result_here(self):
        board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
        self.assertIsNone(player_result_text(board, chess.WHITE))


class TestMovesBy(unittest.TestCase):
    def test_a_fresh_board_has_none(self):
        self.assertEqual(moves_by(chess.Board(), chess.WHITE), 0)
        self.assertEqual(moves_by(chess.Board(), chess.BLACK), 0)

    def test_it_counts_each_side(self):
        board = board_after('e2e4', 'e7e5', 'g1f3')
        self.assertEqual(moves_by(board, chess.WHITE), 2)
        self.assertEqual(moves_by(board, chess.BLACK), 1)

    def test_a_game_starting_on_black_is_counted_correctly(self):
        """Index alone would credit the first move to White"""
        board = board_after('e6d6', 'e2e4',
                            fen='8/8/4k3/8/8/8/4P3/4K3 b - - 4 20')
        self.assertEqual(moves_by(board, chess.BLACK), 1)
        self.assertEqual(moves_by(board, chess.WHITE), 1)

    def test_a_position_loaded_from_a_fen_has_no_history(self):
        board = chess.Board('8/8/4k3/8/8/8/4P3/4K3 w - - 0 1')
        self.assertEqual(moves_by(board, chess.WHITE), 0)


class TestPliesToTakeBack(unittest.TestCase):
    def test_nothing_played_means_nothing_to_undo(self):
        self.assertEqual(plies_to_take_back(chess.Board(), chess.WHITE), 0)

    def test_your_own_single_move_comes_back(self):
        self.assertEqual(plies_to_take_back(board_after('e2e4'), chess.WHITE), 1)

    def test_a_whole_pair_is_unwound(self):
        """Undoing only your own move would let the opponent play again"""
        board = board_after('e2e4', 'e7e5', 'g1f3', 'b8c6')
        self.assertEqual(plies_to_take_back(board, chess.WHITE), 2)

    def test_it_stops_when_the_turn_is_yours(self):
        board = board_after('e2e4', 'e7e5', 'g1f3', 'b8c6')
        popped = plies_to_take_back(board, chess.WHITE)
        scratch = board.copy()
        for _ in range(popped):
            scratch.pop()
        self.assertEqual(scratch.turn, chess.WHITE)

    def test_it_works_from_black_s_side(self):
        board = board_after('e2e4', 'e7e5', 'g1f3')
        popped = plies_to_take_back(board, chess.BLACK)
        scratch = board.copy()
        for _ in range(popped):
            scratch.pop()
        self.assertEqual(scratch.turn, chess.BLACK)

    def test_the_opponent_s_opening_move_is_not_unwound(self):
        """That would leave them to move with nothing prompting them"""
        self.assertEqual(plies_to_take_back(board_after('e2e4'), chess.BLACK), 0)

    def test_a_finished_game_can_still_be_unwound(self):
        board = board_after('f2f3', 'e7e5', 'g2g4', 'd8h4')
        self.assertTrue(board.is_checkmate())
        self.assertEqual(plies_to_take_back(board, chess.WHITE), 2)

    def test_it_never_asks_for_more_than_is_there(self):
        for board in (chess.Board(), board_after('e2e4'), board_after('e2e4', 'e7e5')):
            for colour in (chess.WHITE, chess.BLACK):
                with self.subTest(fen=board.fen(), colour=colour):
                    self.assertLessEqual(plies_to_take_back(board, colour),
                                         len(board.move_stack))

    def test_the_board_is_not_disturbed(self):
        board = board_after('e2e4', 'e7e5')
        before = board.fen()
        plies_to_take_back(board, chess.WHITE)
        self.assertEqual(board.fen(), before)
        self.assertEqual(len(board.move_stack), 2)


if __name__ == '__main__':
    unittest.main()
