#!/usr/bin/env python3
"""
End to end tests for the mistral bot's recovery escalation.

The bot tries four prompting strategies in turn and falls back to a random
legal move if all of them fail. That control flow has never been exercised:
the parsing helpers were tested, but not the decision about which strategy
to try next, when to stop, or what gets logged.

A stub stands in for Ollama, so no model server is involved and the tests
are fast and deterministic.

Run with:
    python3 -m unittest test_llm_recovery
"""

import os
import tempfile
import unittest

import chess

import knightmare_llm
import knightmare_llm_mistral

import knightmare_llm_mistral as mistral


class StubModel:
    """Returns scripted replies and records the prompts it was given"""

    def __init__(self, replies, delay=0.0):
        self.replies = list(replies)
        self.delay = delay
        self.prompts = []

    def generate(self, model, prompt):
        self.prompts.append(prompt)
        if self.delay:
            import time
            time.sleep(self.delay)
        reply = self.replies.pop(0) if self.replies else "no idea"
        return {"response": reply}


class RecoveryTestCase(unittest.TestCase):
    """Shared setup: a bot whose model and log are both stubbed out"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.log_path = os.path.join(self.tmp.name, "log.jsonl")
        self.bot = mistral.KnightmareLLMRecovery(
            model_name="stub", log_file=self.log_path
        )

        self.real_ollama = mistral.ollama
        self.addCleanup(lambda: setattr(mistral, "ollama", self.real_ollama))

    def use(self, *replies, delay=0.0):
        stub = StubModel(replies, delay=delay)
        mistral.ollama = stub
        return stub

    def log_lines(self):
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path) as handle:
            return [line for line in handle if line.strip()]


class TestStrategyEscalation(RecoveryTestCase):
    def test_a_good_first_reply_uses_one_round_trip(self):
        stub = self.use("e2e4")
        move = self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        self.assertEqual(len(stub.prompts), 1)

    def test_a_bad_first_reply_escalates_to_feedback(self):
        """The second strategy quotes the error back to the model"""
        stub = self.use("no idea", "d2d4")
        move = self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertEqual(move, chess.Move.from_uci("d2d4"))
        self.assertEqual(len(stub.prompts), 2)
        self.assertIn("You made an error", stub.prompts[1])

    def test_escalation_continues_through_every_strategy(self):
        stub = self.use("junk", "junk", "junk", "g1f3")
        move = self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertEqual(move, chess.Move.from_uci("g1f3"))
        self.assertEqual(len(stub.prompts), 4)

    def test_the_numbered_strategy_lists_the_moves(self):
        stub = self.use("junk", "junk", "b1c3")
        self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertIn("1. ", stub.prompts[2])

    def test_all_strategies_failing_falls_back_to_a_legal_move(self):
        board = chess.Board()
        self.use("junk", "junk", "junk", "junk")
        move = self.bot.get_best_move(board, max_time=10)
        self.assertIn(move, board.legal_moves)

    def test_no_more_than_four_round_trips(self):
        stub = self.use("junk", "junk", "junk", "junk", "junk", "junk")
        self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertLessEqual(len(stub.prompts), 4)


class TestShortcuts(RecoveryTestCase):
    """Cases the bot answers without asking the model at all"""

    def test_a_forced_mate_is_played_without_asking(self):
        stub = self.use("e2e4")
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        move = self.bot.get_best_move(board, max_time=10)
        self.assertEqual(move, chess.Move.from_uci("e1e8"))
        self.assertEqual(stub.prompts, [])

    def test_a_single_legal_move_is_played_without_asking(self):
        stub = self.use("e2e4")
        board = chess.Board("7k/8/8/8/8/8/5rr1/K7 w - - 0 1")
        self.assertEqual(len(list(board.legal_moves)), 1)
        self.bot.get_best_move(board, max_time=10)
        self.assertEqual(stub.prompts, [])

    def test_a_finished_game_returns_nothing(self):
        board = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertTrue(board.is_checkmate())
        self.assertIsNone(self.bot.get_best_move(board, max_time=10))

    def test_a_model_that_raises_still_yields_a_legal_move(self):
        class Exploding:
            def generate(self, model, prompt):
                raise RuntimeError("model unreachable")

        mistral.ollama = Exploding()
        board = chess.Board()
        self.assertIn(self.bot.get_best_move(board, max_time=10), board.legal_moves)


class TestTimeBudget(RecoveryTestCase):
    def test_the_budget_stops_further_round_trips(self):
        """Each strategy is a full round trip, so the clock has to be checked"""
        stub = self.use("junk", "junk", "junk", "junk", delay=0.3)
        self.bot.get_best_move(chess.Board(), max_time=0.4)
        self.assertLess(len(stub.prompts), 4)

    def test_a_generous_budget_allows_every_strategy(self):
        stub = self.use("junk", "junk", "junk", "junk", delay=0.01)
        self.bot.get_best_move(chess.Board(), max_time=30)
        self.assertEqual(len(stub.prompts), 4)


class TestLogging(RecoveryTestCase):
    def test_each_attempt_is_logged(self):
        self.use("junk", "e2e4")
        self.bot.get_best_move(chess.Board(), max_time=10)
        # One line for the failure, one for the success
        self.assertGreaterEqual(len(self.log_lines()), 2)

    def test_the_log_is_valid_json_per_line(self):
        import json

        self.use("junk", "e2e4")
        self.bot.get_best_move(chess.Board(), max_time=10)
        for line in self.log_lines():
            entry = json.loads(line)
            self.assertIn("strategy", entry)
            self.assertIn("was_valid", entry)

    def test_a_shortcut_move_is_still_logged(self):
        self.use("e2e4")
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        self.bot.get_best_move(board, max_time=10)
        self.assertGreaterEqual(len(self.log_lines()), 1)

    def test_move_numbers_advance(self):
        self.use("e2e4", "e2e4")
        board = chess.Board()
        self.bot.get_best_move(board, max_time=10)
        first = self.bot.move_number
        board.push(chess.Move.from_uci("e2e4"))
        self.bot.get_best_move(board, max_time=10)
        self.assertGreater(self.bot.move_number, first)


class TestPromptMoveList(unittest.TestCase):
    """Both bots cut the move list, and both must cut it the same way

    The recovery bot's simplified strategy shows only ten moves. In
    generation order that hid every capture past the tenth move, so a
    position with material to win could not be played well however good
    the model was.
    """

    KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

    def test_both_bots_share_one_ordering(self):
        """Not copied, so they cannot drift apart"""
        self.assertIs(knightmare_llm_mistral.moves_for_prompt,
                      knightmare_llm.moves_for_prompt)

    def test_a_ten_move_cut_still_shows_the_captures(self):
        board = chess.Board(self.KIWIPETE)
        shown = knightmare_llm.moves_for_prompt(board, limit=10)
        forcing = [m for m in board.legal_moves
                   if board.is_capture(m) or board.gives_check(m)]
        self.assertTrue(forcing, "position should have forcing moves")
        for move in forcing:
            self.assertIn(move, shown, move.uci())

    def test_generation_order_would_have_hidden_them(self):
        """Records what the bug was, so the fix is not undone as pointless"""
        board = chess.Board(self.KIWIPETE)
        naive = list(board.legal_moves)[:10]
        forcing = [m for m in board.legal_moves
                   if board.is_capture(m) or board.gives_check(m)]
        hidden = [m for m in forcing if m not in naive]
        self.assertTrue(hidden, "the old ordering hid at least one forcing move")

    def test_asking_for_every_move_returns_every_move(self):
        board = chess.Board(self.KIWIPETE)
        count = board.legal_moves.count()
        self.assertEqual(len(knightmare_llm.moves_for_prompt(board, limit=count)),
                         count)


if __name__ == "__main__":
    unittest.main()
