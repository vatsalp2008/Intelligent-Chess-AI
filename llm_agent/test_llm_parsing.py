#!/usr/bin/env python3
"""
Unit tests for the LLM bots' reply parsing and time handling.

These cover the pure helpers only, so no Ollama server is needed.

Run with:
    python3 -m unittest test_llm_parsing
"""

import unittest

import chess

from knightmare_llm import (
    DEFAULT_MOVE_TIME,
    MAX_MOVES_SHOWN,
    moves_for_prompt,
    parse_move,
    parse_movetime,
    replay_moves,
)
from knightmare_llm_mistral import KnightmareLLMRecovery, default_log_path


class TestParseMove(unittest.TestCase):
    def setUp(self):
        self.legal = list(chess.Board().legal_moves)

    def parse(self, text):
        return parse_move(text, self.legal)

    def test_bare_move(self):
        self.assertEqual(self.parse("e2e4"), chess.Move.from_uci("e2e4"))

    def test_move_inside_a_sentence(self):
        self.assertEqual(self.parse("I will play d2d4 here."), chess.Move.from_uci("d2d4"))

    def test_uppercase_is_accepted(self):
        self.assertEqual(self.parse("The best move is G1F3!"), chess.Move.from_uci("g1f3"))

    def test_dashed_notation_is_accepted(self):
        """Models often write e2-e4"""
        self.assertEqual(self.parse("My move is e2-e4"), chess.Move.from_uci("e2e4"))

    def test_first_move_in_the_text_wins(self):
        """Scanning follows the reply, not move generation order"""
        self.assertEqual(self.parse("d2d4 or maybe e2e4"), chess.Move.from_uci("d2d4"))
        self.assertEqual(self.parse("e2e4 or maybe d2d4"), chess.Move.from_uci("e2e4"))

    def test_illegal_candidate_is_skipped(self):
        """A well formed but illegal move must not stop the scan"""
        self.assertEqual(self.parse("a1a8 no wait d2d4"), chess.Move.from_uci("d2d4"))

    def test_algebraic_notation_is_rejected(self):
        self.assertIsNone(self.parse("Nf3"))

    def test_illegal_move_alone_returns_nothing(self):
        self.assertIsNone(self.parse("a1a8 is my move"))

    def test_empty_and_missing_replies(self):
        for text in ("", "   ", None):
            with self.subTest(text=text):
                self.assertIsNone(self.parse(text))

    def test_prose_without_a_move_returns_nothing(self):
        self.assertIsNone(self.parse("I am not sure what to play here."))

    def test_promotion_moves_are_understood(self):
        board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        legal = list(board.legal_moves)
        self.assertEqual(parse_move("a7a8q", legal), chess.Move.from_uci("a7a8q"))

    def test_returns_a_move_that_is_actually_legal(self):
        move = self.parse("Let me play g1f3")
        self.assertIn(move, self.legal)


class TestParseMovetime(unittest.TestCase):
    def test_missing_movetime_uses_the_default(self):
        self.assertEqual(parse_movetime("go"), DEFAULT_MOVE_TIME)

    def test_movetime_is_converted_to_seconds(self):
        self.assertEqual(parse_movetime("go movetime 500"), 0.5)

    def test_tiny_movetime_is_floored(self):
        self.assertEqual(parse_movetime("go movetime 1"), 0.1)

    def test_malformed_values_fall_back(self):
        for line in ("go movetime", "go movetime abc", "go wtime 1000"):
            with self.subTest(line=line):
                self.assertEqual(parse_movetime(line), DEFAULT_MOVE_TIME)

    def test_explicit_default_is_respected(self):
        self.assertEqual(parse_movetime("go", default=7.5), 7.5)


class TestRecoveryParsing(unittest.TestCase):
    """The mistral bot's multi-strategy parser"""

    def setUp(self):
        # Built without touching __init__ so no log file is created
        self.bot = KnightmareLLMRecovery.__new__(KnightmareLLMRecovery)
        self.legal = list(chess.Board().legal_moves)

    def parse(self, text):
        return self.bot.parse_move_with_recovery(text, self.legal)

    def test_bare_move(self):
        move, error = self.parse("e2e4")
        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        self.assertIsNone(error)

    def test_move_inside_prose(self):
        move, error = self.parse("I think the strongest continuation is g1f3 here.")
        self.assertEqual(move, chess.Move.from_uci("g1f3"))
        self.assertIsNone(error)

    def test_dashed_move_in_first_token(self):
        move, _ = self.parse("e2-e4")
        self.assertEqual(move, chess.Move.from_uci("e2e4"))

    def test_empty_reply_is_reported(self):
        move, error = self.parse("")
        self.assertIsNone(move)
        self.assertEqual(error, "Empty response")

    def test_unparseable_reply_is_reported(self):
        move, error = self.parse("Nf3 is best")
        self.assertIsNone(move)
        self.assertIn("Could not parse", error)

    def test_illegal_move_is_not_returned(self):
        move, error = self.parse("a1a8")
        self.assertIsNone(move)
        self.assertIsNotNone(error)

    def test_dashed_move_mid_sentence(self):
        """Models often write e2-e4, and not always as the first word"""
        for text in ("I will play e2-e4", "My move: e2-e4 looks best"):
            with self.subTest(text=text):
                move, error = self.parse(text)
                self.assertEqual(move, chess.Move.from_uci("e2e4"))
                self.assertIsNone(error)

    def test_dashed_move_as_the_first_token(self):
        move, _ = self.parse("e2-e4")
        self.assertEqual(move, chess.Move.from_uci("e2e4"))

    def test_first_legal_move_in_the_text_wins(self):
        move, _ = self.parse("d2d4 or perhaps e2e4")
        self.assertEqual(move, chess.Move.from_uci("d2d4"))

    def test_an_illegal_candidate_does_not_stop_the_scan(self):
        move, _ = self.parse("a1a8 no wait d2d4")
        self.assertEqual(move, chess.Move.from_uci("d2d4"))

    def test_every_legal_move_is_reachable_by_the_pattern(self):
        """The removed third strategy relied on this being false

        It searched for each legal move as a substring, which could never
        find anything the pattern above had not already found.
        """
        from knightmare_llm_mistral import UCI_PATTERN
        for move in self.legal:
            with self.subTest(move=move.uci()):
                self.assertTrue(UCI_PATTERN.fullmatch(move.uci()))

    def test_promotions_are_understood(self):
        board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        legal = list(board.legal_moves)
        move, _ = self.bot.parse_move_with_recovery("I play a7a8q", legal)
        self.assertEqual(move, chess.Move.from_uci("a7a8q"))


class TestLogPath(unittest.TestCase):
    def test_default_is_a_relative_jsonl_file(self):
        path = default_log_path()
        self.assertTrue(path.endswith(".jsonl"))
        self.assertTrue(path.startswith("llm_log_recovery_"))

    def test_log_dir_environment_variable_is_used(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["KNIGHTMARE_LOG_DIR"] = tmp
            try:
                path = default_log_path()
            finally:
                del os.environ["KNIGHTMARE_LOG_DIR"]
            self.assertTrue(path.startswith(tmp))


class TestMovesForPrompt(unittest.TestCase):
    """Which moves the model is shown, when the list has to be cut

    The list used to be cut in python-chess generation order, which is by
    piece and square and has nothing to do with how good a move is. In the
    standard "kiwipete" position that hid three of the eight captures,
    including the one the search engine picks, so the model could not have
    chosen it however well it played.
    """

    KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
    MIDDLEGAME = "r2q1rk1/pb1nbppp/1p2pn2/2pp4/2PP4/1PN1PN2/PB3PPP/R2QKB1R w KQ - 0 10"

    def forcing(self, board):
        return [m for m in board.legal_moves
                if board.is_capture(m) or board.gives_check(m) or m.promotion]

    def test_it_never_offers_more_than_the_limit(self):
        board = chess.Board(self.KIWIPETE)
        self.assertEqual(len(moves_for_prompt(board)), MAX_MOVES_SHOWN)

    def test_a_short_list_is_offered_whole(self):
        board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        self.assertEqual(len(moves_for_prompt(board)),
                         board.legal_moves.count())

    def test_every_move_offered_is_legal(self):
        board = chess.Board(self.KIWIPETE)
        for move in moves_for_prompt(board):
            self.assertIn(move, board.legal_moves)

    def test_no_forcing_move_is_hidden(self):
        """The point of the change: captures and checks survive the cut"""
        for fen in (self.KIWIPETE, self.MIDDLEGAME):
            with self.subTest(fen=fen):
                board = chess.Board(fen)
                shown = moves_for_prompt(board)
                for move in self.forcing(board):
                    self.assertIn(move, shown, move.uci())

    def test_captures_come_before_quiet_moves(self):
        board = chess.Board(self.KIWIPETE)
        shown = moves_for_prompt(board)
        first_quiet = next(
            i for i, m in enumerate(shown)
            if not (board.is_capture(m) or board.gives_check(m) or m.promotion)
        )
        last_forcing = max(
            i for i, m in enumerate(shown)
            if board.is_capture(m) or board.gives_check(m) or m.promotion
        )
        self.assertLess(last_forcing, first_quiet)

    def test_the_bigger_capture_comes_first(self):
        """Taking a queen is offered ahead of taking a pawn"""
        board = chess.Board("4k3/8/8/3q4/4P3/8/6B1/4K3 w - - 0 1")
        shown = [m.uci() for m in moves_for_prompt(board)]
        self.assertEqual(shown[0], "e4d5")

    def test_an_en_passant_capture_is_ranked_as_a_capture(self):
        """Nothing stands on the target square, but a pawn is still taken"""
        board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
        capture = chess.Move.from_uci("e5d6")
        self.assertTrue(board.is_en_passant(capture))
        self.assertEqual(moves_for_prompt(board)[0], capture)

    def test_promotions_are_offered(self):
        board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        shown = moves_for_prompt(board)
        self.assertIn(chess.Move.from_uci("a7a8q"), shown)

    def test_the_order_is_the_same_every_time(self):
        """Retrying must not reshuffle the prompt under the model"""
        board = chess.Board(self.KIWIPETE)
        first = [m.uci() for m in moves_for_prompt(board)]
        for _ in range(5):
            self.assertEqual([m.uci() for m in moves_for_prompt(board)], first)

    def test_a_finished_game_offers_nothing(self):
        board = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertEqual(moves_for_prompt(board), [])

    def test_the_board_is_not_disturbed(self):
        board = chess.Board(self.KIWIPETE)
        before = board.fen()
        moves_for_prompt(board)
        self.assertEqual(board.fen(), before)


class TestReplayMoves(unittest.TestCase):
    """Replaying the move list a host sends with a position command

    A move that will not apply used to be skipped and the rest played
    anyway. That is worse than it sounds: the board silently stops being
    the game the host described, and later moves can be legal in the wrong
    position, so the engine analyses a game nobody is playing.
    """

    def test_a_clean_list_plays_through(self):
        board = replay_moves(chess.Board(), "e2e4 e7e5 g1f3 b8c6")
        self.assertEqual([m.uci() for m in board.move_stack],
                         ["e2e4", "e7e5", "g1f3", "b8c6"])

    def test_an_empty_list_leaves_the_board_alone(self):
        self.assertEqual(replay_moves(chess.Board(), "").fen(),
                         chess.STARTING_FEN)

    def test_it_stops_at_an_illegal_move(self):
        board = replay_moves(chess.Board(), "e2e4 e7e5 g1f3 e7e5 b8c6")
        self.assertEqual([m.uci() for m in board.move_stack],
                         ["e2e4", "e7e5", "g1f3"])

    def test_it_stops_at_an_unreadable_move(self):
        board = replay_moves(chess.Board(), "e2e4 zzz e7e5")
        self.assertEqual([m.uci() for m in board.move_stack], ["e2e4"])

    def test_skipping_would_have_played_a_different_game(self):
        """Why stopping matters rather than being merely tidier

        d7d5 is illegal after d7d6, and skipping it leaves White to move
        again - so the White move that follows is perfectly legal, and the
        result is a real-looking game the host never described. A skipped
        move only stays harmless when the next move happens to be the same
        colour, which is exactly what cannot be relied on.
        """
        text = "e2e4 d7d6 d7d5 g1f3"
        stopped = replay_moves(chess.Board(), text)

        skipping = chess.Board()
        for uci in text.split():
            move = chess.Move.from_uci(uci)
            if move in skipping.legal_moves:
                skipping.push(move)

        self.assertNotEqual(stopped.fen(), skipping.fen())
        self.assertEqual(len(stopped.move_stack), 2)
        self.assertEqual(len(skipping.move_stack), 3)

    def test_the_result_is_always_a_prefix_of_what_was_asked_for(self):
        for text in ("e2e4 e7e5", "e2e4 zzz", "e2e4 e7e5 e7e5", "not a move"):
            with self.subTest(text=text):
                board = replay_moves(chess.Board(), text)
                played = [m.uci() for m in board.move_stack]
                self.assertEqual(played, text.split()[:len(played)])

    def test_it_works_from_a_position_other_than_the_start(self):
        start = chess.Board("8/8/4k3/8/8/8/4P3/4K3 w - - 0 1")
        board = replay_moves(start, "e2e4 e6d6")
        self.assertEqual([m.uci() for m in board.move_stack], ["e2e4", "e6d6"])


if __name__ == "__main__":
    unittest.main()
