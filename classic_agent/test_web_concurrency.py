#!/usr/bin/env python3
"""
Concurrency tests for the web interface.

The Flask development server is threaded, so two overlapping POST /move
requests used to each read the same position and both push a move for the
same side. That produced impossible games, for example five consecutive
Black moves. Auto play triggered it routinely, because a move can take
longer than the interval the browser fired on.

These tests drive the Flask app directly through its test client, so no
server or free port is needed.

Run with:
    python3 -m unittest test_web_concurrency
"""

import threading
import unittest

import chess

import simple_web_chess as web


class TestConcurrentMoves(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        # These tests expect both sides to be played by bots. A new game
        # does not change the mode, so say so rather than inheriting
        # whatever the last suite left behind.
        web.mode = web.WATCH_MODE
        self.client.post("/new_game")

    def play_concurrently(self, count):
        """Fire count POST /move requests from separate threads at once"""
        ready = threading.Barrier(count)
        errors = []

        def worker():
            try:
                ready.wait(timeout=30)
                # Each thread needs its own client
                web.app.test_client().post("/move")
            except Exception as exc:  # pragma: no cover - surfaced by asserts
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(errors, [], f"requests raised: {errors}")
        return self.client.get("/board").get_json()["moves"]

    def test_sides_alternate_under_concurrent_requests(self):
        """The heart of the bug: two threads must not both move for Black"""
        moves = self.play_concurrently(6)
        players = [entry.split(":")[0] for entry in moves]
        expected = ["Random", "Knightmare"] * len(players)
        self.assertEqual(
            players,
            expected[:len(players)],
            f"sides did not alternate: {players}",
        )

    def test_no_more_moves_than_requests(self):
        moves = self.play_concurrently(4)
        self.assertLessEqual(len(moves), 4)

    def test_recorded_game_is_legal(self):
        """Replay the history to prove the position was never corrupted"""
        moves = self.play_concurrently(6)
        board = chess.Board()
        for entry in moves:
            san = entry.split(":", 1)[1].strip()
            board.push_san(san)  # raises if the game is not legal

    def test_board_matches_the_move_count(self):
        moves = self.play_concurrently(4)
        self.assertEqual(len(web.game_board.move_stack), len(moves))


class TestSequentialMoves(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        # These tests expect both sides to be played by bots. A new game
        # does not change the mode, so say so rather than inheriting
        # whatever the last suite left behind.
        web.mode = web.WATCH_MODE
        self.client.post("/new_game")

    def test_a_single_move_is_played(self):
        self.assertEqual(self.client.post("/move").status_code, 200)
        self.assertEqual(len(self.client.get("/board").get_json()["moves"]), 1)

    def test_new_game_clears_the_history(self):
        self.client.post("/move")
        self.client.post("/new_game")
        self.assertEqual(self.client.get("/board").get_json()["moves"], [])

    def test_board_endpoint_reports_the_side_to_move(self):
        data = self.client.get("/board").get_json()
        self.assertTrue(data["white_to_move"])
        self.client.post("/move")
        self.assertFalse(self.client.get("/board").get_json()["white_to_move"])


if __name__ == "__main__":
    unittest.main()
