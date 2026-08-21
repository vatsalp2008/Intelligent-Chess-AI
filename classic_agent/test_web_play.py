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

import io
import unittest

import chess
import chess.pgn

import simple_web_chess as web


class PlayTestCase(unittest.TestCase):
    """Shared setup: a fresh client and a known starting state"""

    def setUp(self):
        self.client = web.app.test_client()
        web.mode = web.WATCH_MODE
        web.reset_game()

    def tearDown(self):
        # The mode is module state shared with every other suite, so a
        # test that leaves it in play mode makes those fail instead
        web.mode = web.WATCH_MODE
        web.human_colour = chess.WHITE
        web.reset_game()

    def play(self, colour='white'):
        return self.client.post('/set_mode',
                                json={'mode': 'play', 'colour': colour})

    def any_legal(self):
        """Any move available to you right now, as UCI"""
        legal = self.board()['legal']
        self.assertTrue(legal, 'no legal moves to choose from')
        return sorted(legal.values())[0][0]

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
        # The engine picks its book reply at random, so only your own
        # moves can be named here
        self.assertEqual(len(web.move_history), 2)
        self.assertEqual(web.move_history[0], 'You: e4')
        self.assertTrue(web.move_history[1].startswith('Knightmare: '))

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


class TestSetPosition(PlayTestCase):
    """Loading a position by FEN, mostly about what it refuses"""

    # King on e1 rather than e3, so the pawn in front of it can actually
    # move and the position is worth playing from
    ENDGAME = '8/8/4k3/8/8/8/4P3/4K3 w - - 0 1'

    def load(self, fen):
        return self.client.post('/set_position', json={'fen': fen})

    def test_a_legal_position_is_accepted(self):
        self.assertEqual(self.load(self.ENDGAME).status_code, 200)
        self.assertEqual(web.game_board.fen(), self.ENDGAME)

    def test_the_normalised_fen_comes_back(self):
        self.assertEqual(self.load(self.ENDGAME).get_json()['fen'], self.ENDGAME)

    def test_it_clears_the_previous_game(self):
        self.play()
        self.send('e2e4')
        self.load(self.ENDGAME)
        self.assertEqual(web.move_history, [])
        self.assertIsNone(self.board()['engine'])

    def test_an_empty_request_is_refused(self):
        response = self.load('')
        self.assertEqual(response.status_code, 400)
        self.assertIn('No position', response.get_json()['error'])

    def test_no_body_at_all_is_refused(self):
        self.assertEqual(self.client.post('/set_position').status_code, 400)

    def test_an_unreadable_fen_is_refused(self):
        response = self.load('not a fen')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not read', response.get_json()['error'])

    def test_a_position_with_no_king_is_refused(self):
        """The search assumes it will never see one"""
        response = self.load('4k3/8/8/8/8/8/8/8 w - - 0 1')
        self.assertEqual(response.status_code, 400)
        self.assertIn('no white king', response.get_json()['error'])

    def test_a_side_already_in_check_is_refused(self):
        response = self.load('8/8/8/8/8/8/8/4Kk2 w - - 0 1')
        self.assertEqual(response.status_code, 400)
        self.assertIn('opposite check', response.get_json()['error'])

    def test_a_refused_position_leaves_the_board_alone(self):
        before = web.game_board.fen()
        self.load('not a fen')
        self.load('4k3/8/8/8/8/8/8/8 w - - 0 1')
        self.assertEqual(web.game_board.fen(), before)

    def test_the_engine_can_play_from_the_loaded_position(self):
        self.load(self.ENDGAME)
        self.client.post('/move')
        self.assertEqual(len(web.game_board.move_stack), 1)

    def test_you_can_play_from_the_loaded_position(self):
        self.play()
        self.load(self.ENDGAME)
        self.assertEqual(self.send('e2e4').get_json()['san'], 'e4')

    def test_the_legal_move_list_matches_the_loaded_position(self):
        self.play()
        self.load(self.ENDGAME)
        listed = sum(len(v) for v in self.board()['legal'].values())
        self.assertEqual(listed, web.game_board.legal_moves.count())


class TestPlayingAsBlack(PlayTestCase):
    """The interface assumed you were White in several places"""

    def test_the_colour_is_accepted_and_reported(self):
        self.assertEqual(self.play('black').get_json()['colour'], 'black')
        self.assertEqual(self.board()['colour'], 'black')

    def test_white_is_the_default(self):
        self.assertEqual(self.play().get_json()['colour'], 'white')

    def test_an_unknown_colour_is_refused(self):
        response = self.client.post('/set_mode',
                                    json={'mode': 'play', 'colour': 'purple'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('purple', response.get_json()['error'])

    def test_the_engine_moves_first(self):
        self.play('black')
        self.assertFalse(self.board()['your_turn'])
        self.assertEqual(self.client.post('/move').get_json()['success'], True)
        self.assertTrue(self.board()['your_turn'])

    def test_the_opponent_is_the_engine_not_the_random_bot(self):
        """Picking the bot by colour used to hand Black the random bot"""
        self.play('black')
        self.client.post('/move')
        self.assertTrue(web.move_history[0].startswith('Knightmare:'))

    def test_you_cannot_move_before_the_engine_has(self):
        self.play('black')
        self.assertEqual(self.send('e7e5').status_code, 400)

    def test_you_can_move_once_it_has(self):
        self.play('black')
        self.client.post('/move')
        self.assertEqual(self.send(self.any_legal()).status_code, 200)

    def test_the_move_is_still_recorded_as_yours(self):
        self.play('black')
        self.client.post('/move')
        self.send(self.any_legal())
        self.assertTrue(web.move_history[-1].startswith('You: '))

    def test_the_board_is_drawn_from_your_side(self):
        """Every chess interface flips for Black"""
        self.play('black')
        self.assertIn('flipped', web.chess.svg.board.__doc__ or 'flipped')
        black_view = self.board()['svg']
        self.play('white')
        white_view = self.board()['svg']
        self.assertNotEqual(black_view, white_view)

    def test_takeback_returns_the_turn_to_you(self):
        """Stopping at White would leave the engine to move"""
        self.play('black')
        self.client.post('/move')
        self.send(self.any_legal())
        self.client.post('/move')
        self.assertEqual(self.client.post('/takeback').get_json()['undone'], 2)
        self.assertTrue(web.human_to_move())

    def test_it_will_not_unwind_the_engine_s_opening_move(self):
        """That would leave an empty board with the engine to move"""
        self.play('black')
        self.client.post('/move')
        self.send(self.any_legal())
        self.client.post('/move')
        self.client.post('/takeback')

        response = self.client.post('/takeback')
        self.assertEqual(response.status_code, 400)
        self.assertIn('No moves', response.get_json()['error'])
        self.assertEqual(len(web.game_board.move_stack), 1)
        self.assertTrue(web.human_to_move())

    def test_nothing_of_yours_to_undo_is_refused(self):
        self.play('black')
        self.client.post('/move')
        self.assertEqual(self.client.post('/takeback').status_code, 400)

    def test_the_pgn_names_you_as_black(self):
        self.play('black')
        game = chess.pgn.read_game(io.StringIO(self.client.get('/pgn').get_data(as_text=True)))
        self.assertEqual(game.headers['Black'], 'Human')
        self.assertEqual(game.headers['White'], 'Knightmare')

    def test_losing_says_you_lost(self):
        """Naming the colour leaves you to work out which side you were"""
        self.play('black')
        # A back rank mate: Re8 covers f8 and h8, and the king's own
        # pawns block the rest. 7k/5Q2/6K1 looks like a mate but is
        # stalemate, because the king there is not attacked at all.
        web.game_board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertTrue(web.game_board.is_checkmate())
        self.assertEqual(self.board()['status'], 'Checkmate - you lost')

    def test_winning_says_you_won(self):
        self.play('black')
        web.game_board = chess.Board('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3')
        self.assertEqual(self.board()['status'], 'Checkmate - you win!')

    def test_watching_still_names_the_bots(self):
        # Black is the side mated here, so White is the side that wins
        web.game_board = chess.Board('4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1')
        self.assertIn('White (Random)', self.board()['status'])


class TestPgnExport(PlayTestCase):
    """A game is only worth playing if it can be taken away and studied"""

    def pgn(self):
        response = self.client.get('/pgn')
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def parsed(self):
        return chess.pgn.read_game(io.StringIO(self.pgn()))

    def test_it_is_offered_as_a_file(self):
        headers = self.client.get('/pgn').headers
        self.assertIn('chess-pgn', headers['Content-Type'])
        self.assertIn('attachment', headers['Content-Disposition'])
        self.assertIn('.pgn', headers['Content-Disposition'])

    def test_a_game_that_has_not_started_is_still_valid(self):
        self.assertIsNotNone(self.parsed())

    def test_it_reads_back_as_the_same_position(self):
        self.play()
        for uci in ('e2e4', 'd2d4', 'g1f3'):
            self.send(uci)
            self.client.post('/move')
        self.assertEqual(self.parsed().end().board().fen(), web.game_board.fen())

    def test_the_moves_are_numbered_from_one(self):
        self.play()
        self.send('e2e4')
        self.assertIn('1. e4', self.pgn())

    def test_it_names_you_when_you_are_playing(self):
        self.play()
        self.assertEqual(self.parsed().headers['White'], 'Human')

    def test_it_names_the_bot_when_watching(self):
        self.assertEqual(self.parsed().headers['White'], 'Random bot')

    def test_black_is_always_the_engine(self):
        self.assertEqual(self.parsed().headers['Black'], 'Knightmare')

    def test_an_unfinished_game_has_no_result(self):
        self.play()
        self.send('e2e4')
        self.assertEqual(self.parsed().headers['Result'], '*')

    def test_a_finished_game_records_who_won(self):
        for uci in ('f2f3', 'e7e5', 'g2g4', 'd8h4'):
            web.game_board.push(chess.Move.from_uci(uci))
        self.assertEqual(self.parsed().headers['Result'], '0-1')

    def test_a_position_set_up_by_hand_carries_its_fen(self):
        """The moves alone would not reproduce where the game started"""
        fen = '4k3/8/8/8/8/8/4P3/4K3 w - - 0 1'
        web.game_board = chess.Board(fen)
        web.game_board.push(chess.Move.from_uci('e2e4'))
        game = self.parsed()
        self.assertEqual(game.headers['FEN'], fen)
        self.assertEqual(game.headers['SetUp'], '1')
        self.assertEqual(game.end().board().fen(), web.game_board.fen())

    def test_a_normal_game_carries_no_fen(self):
        self.assertNotIn('FEN', self.parsed().headers)

    def test_long_games_are_wrapped(self):
        """The PGN standard asks for lines of at most 80 characters"""
        board = web.game_board
        for _ in range(30):
            board.push(next(iter(board.legal_moves)))
        for line in self.pgn().splitlines():
            self.assertLessEqual(len(line), 80, line)

    def test_the_board_is_not_disturbed_by_exporting(self):
        self.play()
        self.send('e2e4')
        before = web.game_board.fen()
        self.pgn()
        self.assertEqual(web.game_board.fen(), before)


if __name__ == '__main__':
    unittest.main()
