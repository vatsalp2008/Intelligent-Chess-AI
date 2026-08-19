#!/usr/bin/env python3
"""
End to end tests for the llama bot's retry loop.

Its parsing was covered, but not the loop around it: how many times it asks
the model, when the time budget cuts that short, and what happens when the
model is unreachable or never says anything usable.

A stub stands in for Ollama, so no model server is involved.

Run with:
    python3 -m unittest test_llm_retry
"""

import unittest

import chess

import knightmare_llm as llama


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
        return {"response": self.replies.pop(0) if self.replies else "no idea"}


class RetryTestCase(unittest.TestCase):
    def setUp(self):
        self.bot = llama.LLMChessBot(model_name="stub")
        self.real_ollama = llama.ollama
        self.addCleanup(lambda: setattr(llama, "ollama", self.real_ollama))

    def use(self, *replies, delay=0.0):
        stub = StubModel(replies, delay=delay)
        llama.ollama = stub
        return stub


class TestRetryLoop(RetryTestCase):
    def test_a_good_reply_uses_one_round_trip(self):
        stub = self.use("e2e4")
        move = self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertEqual(move, chess.Move.from_uci("e2e4"))
        self.assertEqual(len(stub.prompts), 1)

    def test_a_bad_reply_is_retried(self):
        stub = self.use("junk", "d2d4")
        move = self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertEqual(move, chess.Move.from_uci("d2d4"))
        self.assertEqual(len(stub.prompts), 2)

    def test_retries_stop_at_the_limit(self):
        stub = self.use("junk", "junk", "junk", "junk", "junk")
        self.bot.get_best_move(chess.Board(), max_time=30)
        self.assertEqual(len(stub.prompts), llama.MAX_ATTEMPTS)

    def test_giving_up_still_returns_a_legal_move(self):
        board = chess.Board()
        self.use("junk", "junk", "junk")
        self.assertIn(self.bot.get_best_move(board, max_time=30), board.legal_moves)

    def test_the_prompt_lists_legal_moves(self):
        stub = self.use("e2e4")
        self.bot.get_best_move(chess.Board(), max_time=10)
        self.assertIn("e2e4", stub.prompts[0])

    def test_the_prompt_is_capped_in_length(self):
        """Long move lists were found to confuse the model"""
        stub = self.use("e2e4")
        self.bot.get_best_move(chess.Board(), max_time=10)
        listed = stub.prompts[0].split("list: ")[1].split("\n")[0]
        self.assertLessEqual(len(listed.split(", ")), llama.MAX_MOVES_SHOWN)


class TestShortcuts(RetryTestCase):
    def test_a_forced_mate_is_played_without_asking(self):
        stub = self.use("e2e4")
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        self.assertEqual(self.bot.get_best_move(board, max_time=10),
                         chess.Move.from_uci("e1e8"))
        self.assertEqual(stub.prompts, [])

    def test_a_single_legal_move_is_played_without_asking(self):
        stub = self.use("e2e4")
        board = chess.Board("7k/8/8/8/8/8/5rr1/K7 w - - 0 1")
        self.bot.get_best_move(board, max_time=10)
        self.assertEqual(stub.prompts, [])

    def test_a_finished_game_returns_nothing(self):
        board = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertIsNone(self.bot.get_best_move(board, max_time=10))

    def test_an_unreachable_model_still_yields_a_legal_move(self):
        class Exploding:
            def generate(self, model, prompt):
                raise RuntimeError("model unreachable")

        llama.ollama = Exploding()
        board = chess.Board()
        self.assertIn(self.bot.get_best_move(board, max_time=10), board.legal_moves)

    def test_a_missing_ollama_plays_randomly(self):
        llama.ollama = None
        board = chess.Board()
        self.assertIn(self.bot.get_best_move(board, max_time=10), board.legal_moves)


class TestTimeBudget(RetryTestCase):
    def test_the_budget_stops_further_retries(self):
        stub = self.use("junk", "junk", "junk", delay=0.3)
        self.bot.get_best_move(chess.Board(), max_time=0.4)
        self.assertLess(len(stub.prompts), llama.MAX_ATTEMPTS)

    def test_a_generous_budget_allows_every_retry(self):
        stub = self.use("junk", "junk", "junk", delay=0.01)
        self.bot.get_best_move(chess.Board(), max_time=30)
        self.assertEqual(len(stub.prompts), llama.MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
