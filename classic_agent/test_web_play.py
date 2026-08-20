#!/usr/bin/env python3
"""
Tests for playing against the engine through the web interface.

The endpoints here take a move typed by a person, so every rejection path
matters: an unreadable move, an illegal one, a move out of turn, a move
after the game has ended. Getting any of those wrong either corrupts the
position or leaves the interface stuck with no explanation.

Run with:
    python3 -m unittest test_web_play
"""

import unittest

import chess

import simple_web_chess as web


class PlayTestCase(unittest.TestCase):
    """Shared setup: a fresh client and a known starting state"""

    def setUp(self):
        self.client = web.app.test_client()
        web.mode = web.WATCH_MODE
        web.reset_game()

    def play(self):
        return self.client.post('/set_mode', json={'mode': 'play'})

    def send(self, uci):
        return self.client.post('/human_move', json={'move': uci})

    def board(self):
        return self.client.get('/board').get_json()


class TestSetMode(PlayTestCase):
    def test_watching_is_the_default(self):
        self.assertEqual(self.board()['mode'], web.WATCH_MODE)

    def test_switching_to_play(self):
        self.assertEqual(self.play().get_json()['mode'], web.PLAY_MODE)

    def test_an_unknown_mode_is_refused(self):
        response = self.client.post('/set_mode', json={'mode': 'nonsense'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('nonsense', response.get_json()['error'])

    def test_a_refused_mode_leaves_the_old_one(self):
        self.play()
        self.client.post('/set_mode', json={'mode': 'nonsense'})
        self.assertEqual(self.board()['mode'], web.PLAY_MODE)

    def test_no_body_falls_back_to_watching(self):
        self.play()
        self.assertEqual(self.client.post('/set_mode').get_json()['mode'],
                         web.WATCH_MODE)

    def test_changing_mode_starts_a_new_game(self):
        """A half played position would leave the new side already moved"""
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

    def test_the_move_is_recorded_as_yours(self):
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
        response = self.send('e7e5')
        self.assertEqual(response.status_code, 400)
        self.assertIn('not your turn', response.get_json()['error'])

    def test_watching_means_no_human_moves(self):
        self.client.post('/set_mode', json={'mode': 'watch'})
        self.assertEqual(self.send('e2e4').status_code, 400)

    def test_a_promotion_needs_its_piece(self):
        web.game_board = chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.assertEqual(self.send('a7a8q').get_json()['san'], 'a8=Q+')

    def test_a_promotion_without_a_piece_is_refused(self):
        web.game_board = chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.assertEqual(self.send('a7a8').status_code, 400)

    def test_no_moves_once_the_game_is_over(self):
        web.game_board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
        response = self.send('h8g8')
        self.assertEqual(response.status_code, 400)
        self.assertIn('over', response.get_json()['error'])


class TestEngineReply(PlayTestCase):
    def setUp(self):
        super().setUp()
        self.play()

    def test_the_bot_will_not_move_for_you(self):
        response = self.client.post('/move')
        self.assertEqual(response.status_code, 409)
        self.assertIn('your move', response.get_json()['error'].lower())

    def test_the_engine_answers_once_you_have_moved(self):
        self.send('e2e4')
        self.assertEqual(self.client.post('/move').get_json()['success'], True)
        self.assertTrue(web.game_board.turn == chess.WHITE)

    def test_the_engine_is_the_one_answering(self):
        """Not the random bot, which is White's opponent in watch mode"""
        self.send('e2e4')
        self.client.post('/move')
        self.assertTrue(web.move_history[-1].startswith('Knightmare:'))

    def test_watch_mode_still_moves_for_both(self):
        self.client.post('/set_mode', json={'mode': 'watch'})
        for _ in range(4):
            self.assertEqual(self.client.post('/move').get_json()['success'], True)
        self.assertEqual(len(web.move_history), 4)


class TestTakeback(PlayTestCase):
    def setUp(self):
        super().setUp()
        self.play()

    def pair(self, uci):
        """Your move and the engine's reply to it"""
        self.send(uci)
        self.client.post('/move')

    def test_it_undoes_a_whole_move_pair(self):
        """Undoing only your move would just let the engine play again"""
        self.pair('e2e4')
        self.assertEqual(self.client.post('/takeback').get_json()['undone'], 2)
        self.assertEqual(web.game_board.fen(), chess.Board().fen())

    def test_it_leaves_the_turn_with_you(self):
        self.pair('e2e4')
        self.pair('d2d4')
        self.client.post('/takeback')
        self.assertTrue(web.human_to_move())

    def test_the_history_shrinks_with_the_board(self):
        self.pair('e2e4')
        self.pair('d2d4')
        self.client.post('/takeback')
        self.assertEqual(web.move_history, ['You: e4', 'Knightmare: c6'])

    def test_repeated_takebacks_reach_the_start(self):
        self.pair('e2e4')
        self.pair('d2d4')
        self.client.post('/takeback')
        self.client.post('/takeback')
        self.assertEqual(web.game_board.fen(), chess.Board().fen())
        self.assertEqual(web.move_history, [])

    def test_nothing_to_undo_is_refused(self):
        response = self.client.post('/takeback')
        self.assertEqual(response.status_code, 400)
        self.assertIn('No moves', response.get_json()['error'])

    def test_it_is_refused_while_watching(self):
        self.client.post('/set_mode', json={'mode': 'watch'})
        self.client.post('/move')
        response = self.client.post('/takeback')
        self.assertEqual(response.status_code, 400)
        self.assertIn('playing', response.get_json()['error'])

    def test_a_stale_engine_line_is_dropped(self):
        """It described a position that no longer exists"""
        self.pair('e2e4')
        self.client.post('/takeback')
        self.assertIsNone(self.board()['engine'])

    def test_a_finished_game_can_be_unwound(self):
        """Otherwise a loss leaves you stuck with no way back"""
        # Played rather than set from a FEN, because a position loaded
        # from a FEN has no history to take back
        for uci in ('f2f3', 'e7e5', 'g2g4', 'd8h4'):
            web.game_board.push(chess.Move.from_uci(uci))
            web.move_history.append(uci)
        self.assertTrue(web.game_board.is_checkmate())

        self.assertEqual(self.client.post('/takeback').get_json()['undone'], 2)
        self.assertFalse(web.game_board.is_game_over())
        self.assertTrue(web.human_to_move())

    def test_you_can_take_back_your_own_last_move(self):
        """After the engine has replied there is a pair to unwind"""
        self.pair('a2a4')
        before = len(web.game_board.move_stack)
        self.client.post('/takeback')
        self.assertEqual(len(web.game_board.move_stack), before - 2)


class TestBoardReport(PlayTestCase):
    def test_your_turn_is_reported(self):
        self.play()
        self.assertTrue(self.board()['your_turn'])
        self.send('e2e4')
        self.assertFalse(self.board()['your_turn'])

    def test_watching_is_never_your_turn(self):
        self.assertFalse(self.board()['your_turn'])

    def test_legal_moves_are_grouped_by_origin(self):
        legal = self.board()['legal']
        self.assertEqual(sorted(legal['e2']), ['e2e3', 'e2e4'])
        self.assertEqual(len(legal), 10)

    def test_every_legal_move_is_listed(self):
        listed = sum(len(v) for v in self.board()['legal'].values())
        self.assertEqual(listed, web.game_board.legal_moves.count())

    def test_promotions_are_listed_in_full(self):
        web.game_board = chess.Board('4k3/P7/8/8/8/8/8/4K3 w - - 0 1')
        self.assertEqual(sorted(self.board()['legal']['a7']),
                         ['a7a8b', 'a7a8n', 'a7a8q', 'a7a8r'])

    def test_a_finished_game_lists_nothing(self):
        web.game_board = chess.Board('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1')
        self.assertEqual(self.board()['legal'], {})

    def test_the_status_prompts_you_in_play_mode(self):
        self.play()
        self.assertEqual(self.board()['status'], 'Your move')
        self.send('e2e4')
        self.assertIn('thinking', self.board()['status'])

    def test_the_status_names_the_bots_when_watching(self):
        self.assertIn('Random', self.board()['status'])


if __name__ == '__main__':
    unittest.main()
