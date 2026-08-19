#!/usr/bin/env python3
"""
Unit tests for the LLM bots' reply parsing and time handling.

These cover the pure helpers only, so no Ollama server is needed.

Run with:
    python3 -m unittest test_llm_parsing
"""

import unittest

import chess

from knightmare_llm import DEFAULT_MOVE_TIME, parse_move, parse_movetime
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


if __name__ == "__main__":
    unittest.main()
