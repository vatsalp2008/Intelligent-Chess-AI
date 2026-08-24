#!/usr/bin/env python3
"""
Tests for playing a game yourself in the Stockfish interface.

These endpoints take a move typed by a person, so every rejection path
matters: an unreadable move, an illegal one, a move out of turn, a move
after the game has ended. Getting any of those wrong either corrupts the
position or leaves the interface stuck with no explanation.

Stockfish itself is not needed: when the binary is missing the interface
falls back to random legal moves, which is enough to exercise the turn
taking. The tests that would depend on its strength are not here.

Run with:
    python3 -m unittest test_stockfish_play
"""

import io
import unittest

import chess
import chess.pgn

import knightmare_vs_stockfish as web


class PlayTestCase(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        web.mode = web.WATCH_MODE
        web.human_colour = chess.WHITE
        web.reset_game()

    def tearDown(self):
        # Module state shared with the other suites, so a test that leaves
        # it in play mode makes those fail instead
        web.mode = web.WATCH_MODE
        web.human_colour = chess.WHITE
        web.reset_game()

    def play(self, colour='white'):
        return self.client.post('/set_mode',
                                json={'mode': 'play', 'colour': colour})

    def send(self, uci):
        return self.client.post('/human_move', json={'move': uci})

    def board(self):
        return self.client.get('/board').get_json()

    def any_legal(self):
        legal = self.board()['legal']
        self.assertTrue(legal, 'no legal moves to choose from')
        return sorted(legal.values())[0][0]


class TestSetMode(PlayTestCase):
    def test_watching_is_the_default(self):
        self.assertEqual(self.board()['mode'], web.WATCH_MODE)

    def test_switching_to_play(self):
        self.assertEqual(self.play().get_json()['mode'], web.PLAY_MODE)

    def test_a_colour_can_be_chosen(self):
        self.assertEqual(self.play('black').get_json()['colour'], 'black')

    def test_an_unknown_mode_is_refused(self):
        response = self.client.post('/set_mode', json={'mode': 'nonsense'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('nonsense', response.get_json()['error'])

    def test_an_unknown_colour_is_refused(self):
        response = self.client.post('/set_mode',
                                    json={'mode': 'play', 'colour': 'green'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('green', response.get_json()['error'])

    def test_changing_mode_starts_a_new_game(self):
        self.client.post('/move')
        self.play()
        self.assertEqual(web.game_board.fen(), chess.Board().fen())
        self.assertEqual(web.move_history, [])


class TestHumanMove(PlayTestCase):
    def setUp(self):
        super().setUp()
        self.play()

    def test_a_legal_move_is_played(self):
        self.assertEqual(self.send('e2e4').get_json()['san'], 'e4')
        self.assertEqual(web.game_board.piece_at(chess.E4),
                         chess.Piece(chess.PAWN, chess.WHITE))

    def test_it_is_recorded_as_yours(self):
        self.send('e2e4')
        self.assertEqual(web.move_history, ['You: e4'])

    def test_an_illegal_move_is_refused(self):
        response = self.send('e2e5')
        self.assertEqual(response.status_code, 400)
        self.assertIn('not legal', response.get_json()['error'])

    def test_an_unreadable_move_is_refused(self):
        response = self.send('zzz')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not read', response.get_json()['error'])

    def test_a_refused_move_leaves_the_position_alone(self):
        before = web.game_board.fen()
        self.send('e2e5')
        self.send('not a move')
        self.assertEqual(web.game_board.fen(), before)

    def test_moving_out_of_turn_is_refused(self):
        self.send('e2e4')
        self.assertEqual(self.send('e7e5').status_code, 400)

    def test_watching_means_no_human_moves(self):
        self.client.post('/set_mode', json={'mode': 'watch'})
        self.assertEqual(self.send('e2e4').status_code, 400)

    def test_a_promotion_needs_its_piece(self):
        web.game_board = chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.assertEqual(self.send('a7a8q').get_json()['san'], 'a8=Q+')

    def test_no_moves_once_the_game_is_over(self):
        web.game_board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        web.human_colour = chess.BLACK
        response = self.send('g8h8')
        self.assertEqual(response.status_code, 400)
        self.assertIn('over', response.get_json()['error'])


class TestOpponent(PlayTestCase):
    def test_the_engine_will_not_move_for_you(self):
        self.play()
        response = self.client.post('/move')
        self.assertEqual(response.status_code, 409)
        self.assertIn('your move', response.get_json()['error'].lower())

    def test_it_answers_once_you_have_moved(self):
        self.play()
        self.send('e2e4')
        self.assertEqual(self.client.post('/move').get_json()['success'], True)
        self.assertTrue(web.human_to_move())

    def test_stockfish_is_the_opponent_not_knightmare(self):
        """Picking the engine by colour would hand Black the wrong one"""
        self.play('black')
        self.client.post('/move')
        self.assertTrue(web.move_history[0].startswith('Stockfish'))

    def test_it_opens_when_you_take_black(self):
        self.play('black')
        self.assertFalse(self.board()['your_turn'])
        self.client.post('/move')
        self.assertTrue(self.board()['your_turn'])

    def test_watching_still_plays_both_sides(self):
        for _ in range(4):
            self.assertEqual(self.client.post('/move').get_json()['success'], True)
        self.assertEqual(len(web.move_history), 4)

    def test_watch_history_is_unnamed(self):
        """It reads as a game record rather than a conversation"""
        self.client.post('/move')
        self.assertNotIn(':', web.move_history[0])


class TestTakeback(PlayTestCase):
    def pair(self, uci):
        self.send(uci)
        self.client.post('/move')

    def test_it_undoes_a_whole_pair(self):
        self.play()
        self.pair('e2e4')
        self.assertEqual(self.client.post('/takeback').get_json()['undone'], 2)
        self.assertEqual(web.game_board.fen(), chess.Board().fen())

    def test_it_leaves_the_turn_with_you(self):
        self.play('black')
        self.client.post('/move')
        self.send(self.any_legal())
        self.client.post('/move')
        self.client.post('/takeback')
        self.assertTrue(web.human_to_move())

    def test_it_is_refused_while_watching(self):
        self.client.post('/move')
        response = self.client.post('/takeback')
        self.assertEqual(response.status_code, 400)
        self.assertIn('playing', response.get_json()['error'])

    def test_nothing_of_yours_is_refused(self):
        self.play('black')
        self.client.post('/move')
        self.assertEqual(self.client.post('/takeback').status_code, 400)

    def test_a_stale_engine_line_is_dropped(self):
        self.play()
        self.pair('e2e4')
        self.client.post('/takeback')
        self.assertIsNone(self.board()['engine'])


class TestSetPosition(PlayTestCase):
    ENDGAME = '8/8/4k3/8/8/8/4P3/4K3 w - - 0 1'

    def load(self, fen):
        return self.client.post('/set_position', json={'fen': fen})

    def test_a_legal_position_is_accepted(self):
        self.assertEqual(self.load(self.ENDGAME).status_code, 200)
        self.assertEqual(web.game_board.fen(), self.ENDGAME)

    def test_an_empty_request_is_refused(self):
        self.assertEqual(self.load('').status_code, 400)

    def test_an_unreadable_fen_is_refused(self):
        self.assertIn('Could not read', self.load('nope').get_json()['error'])

    def test_a_position_with_no_king_is_refused(self):
        response = self.load('4k3/8/8/8/8/8/8/8 w - - 0 1')
        self.assertEqual(response.status_code, 400)
        self.assertIn('no white king', response.get_json()['error'])

    def test_a_refused_position_leaves_the_board_alone(self):
        before = web.game_board.fen()
        self.load('nope')
        self.assertEqual(web.game_board.fen(), before)

    def test_you_can_play_on_from_it(self):
        self.play()
        self.load(self.ENDGAME)
        self.assertEqual(self.send('e2e4').get_json()['san'], 'e4')


class TestBoardReport(PlayTestCase):
    def test_your_turn_is_reported(self):
        self.play()
        self.assertTrue(self.board()['your_turn'])
        self.send('e2e4')
        self.assertFalse(self.board()['your_turn'])

    def test_watching_is_never_your_turn(self):
        self.assertFalse(self.board()['your_turn'])

    def test_every_legal_move_is_listed(self):
        listed = sum(len(v) for v in self.board()['legal'].values())
        self.assertEqual(listed, web.game_board.legal_moves.count())

    def test_the_status_prompts_you(self):
        self.play()
        self.assertEqual(self.board()['status'], 'Your move')
        self.send('e2e4')
        self.assertIn('thinking', self.board()['status'])

    def test_the_status_names_the_engines_when_watching(self):
        self.assertIn('Stockfish', self.board()['status'])

    def test_losing_says_you_lost(self):
        self.play('black')
        web.game_board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertEqual(self.board()['status'], 'Checkmate - you lost')

    def test_the_board_is_drawn_from_your_side(self):
        self.play('black')
        black_view = self.board()['svg']
        self.play('white')
        self.assertNotEqual(black_view, self.board()['svg'])


class TestPgn(PlayTestCase):
    def headers(self):
        text = self.client.get('/pgn').get_data(as_text=True)
        return chess.pgn.read_game(io.StringIO(text)).headers

    def test_it_names_you_when_playing_white(self):
        self.play()
        self.assertEqual(self.headers()['White'], 'Human')
        self.assertIn('Stockfish', self.headers()['Black'])

    def test_it_names_you_when_playing_black(self):
        self.play('black')
        self.assertEqual(self.headers()['Black'], 'Human')
        self.assertIn('Stockfish', self.headers()['White'])

    def test_watching_names_both_engines(self):
        names = self.headers()
        self.assertIn('Knightmare', (names['White'], names['Black']))
        self.assertNotIn('Human', (names['White'], names['Black']))


class TestClaimableDraws(unittest.TestCase):
    """A drawn position must not still be offering moves

    is_game_over() says False for the fifty move rule and threefold
    repetition, because those are claims a player makes rather than
    automatic. Trusting it reported a draw in the status line while auto
    play kept grinding away in the position.
    """

    FIFTY_MOVE_FEN = '4k3/8/8/8/8/8/4P3/4K3 w - - 100 60'

    def setUp(self):
        self.client = web.app.test_client()
        web.mode = web.WATCH_MODE
        web.reset_game()

    def tearDown(self):
        web.mode = web.WATCH_MODE
        web.reset_game()

    def load_fifty_move(self):
        web.game_board = chess.Board(self.FIFTY_MOVE_FEN)
        # The library agrees it is claimable but not automatic
        self.assertFalse(web.game_board.is_game_over())
        self.assertTrue(web.game_board.is_fifty_moves())

    def test_the_status_says_it_is_drawn(self):
        self.load_fifty_move()
        self.assertIn('50 move', self.client.get('/board').get_json()['status'])

    def test_the_board_reports_the_game_as_over(self):
        self.load_fifty_move()
        self.assertTrue(self.client.get('/board').get_json()['game_over'])

    def test_no_further_moves_are_played(self):
        self.load_fifty_move()
        before = web.game_board.fen()
        self.assertIn('error', self.client.post('/move').get_json())
        self.assertEqual(web.game_board.fen(), before)

    def test_a_repetition_also_ends_it(self):
        """Shuffling kings back to the same position three times"""
        # No castling rights in the FEN: the rook's first move would
        # forfeit them, so the starting position would never recur
        web.game_board = chess.Board('4k3/8/8/8/8/8/8/R3K3 w - - 0 1')
        for uci in ('a1a2', 'e8e7', 'a2a1', 'e7e8',
                    'a1a2', 'e8e7', 'a2a1', 'e7e8'):
            web.game_board.push(chess.Move.from_uci(uci))
        self.assertTrue(web.game_board.is_repetition(3))
        self.assertTrue(self.client.get('/board').get_json()['game_over'])


if __name__ == '__main__':
    unittest.main()
