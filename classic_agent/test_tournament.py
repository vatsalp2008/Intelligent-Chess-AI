#!/usr/bin/env python3
"""
Unit tests for the tournament runner's engine handling and scoring.

The result mapping and the dead-engine paths are the parts most likely to
be wrong and least likely to be noticed, since a tournament that silently
mis-scores still looks like it worked.

Run with:
    python3 -m unittest test_tournament
"""

import os
import subprocess
import tempfile
import unittest
import unittest.mock

import chess

from simple_tournament import (
    ChessEngine,
    EngineDied,
    parse_args,
    play_game,
    save_games,
)

# An engine that exits immediately without speaking UCI
DEAD_ENGINE = "import sys\nsys.exit(1)\n"

# An engine that answers uci but never answers go
# Iterating sys.stdin read-ahead buffers, so read a line at a time
MUTE_ENGINE = """
import sys
while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if line == "uci":
        print("id name Mute"); print("uciok"); sys.stdout.flush()
    elif line == "isready":
        print("readyok"); sys.stdout.flush()
    elif line == "quit":
        break
"""


class FakeEngine:
    """Plays a scripted list of moves, then resigns by returning None"""

    def __init__(self, name, moves=None):
        self.name = name
        self.moves = list(moves or [])

    def get_move(self, board, time_ms=1000):
        while self.moves:
            candidate = chess.Move.from_uci(self.moves.pop(0))
            if candidate in board.legal_moves:
                return candidate
        # Otherwise just play something legal
        legal = list(board.legal_moves)
        return legal[0] if legal else None


class ResigningEngine:
    def __init__(self, name):
        self.name = name

    def get_move(self, board, time_ms=1000):
        return None


def write_engine(directory, name, source):
    path = os.path.join(directory, name)
    with open(path, "w") as handle:
        handle.write(source)
    return path


class TestEngineFailures(unittest.TestCase):
    def test_engine_that_exits_is_reported(self):
        """A dead engine must be detected, not waited on"""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_engine(tmp, "dead.py", DEAD_ENGINE)
            engine = ChessEngine(path, "DeadBot")
            with self.assertRaises(EngineDied):
                engine.start()

    def test_engine_that_never_answers_go_times_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_engine(tmp, "mute.py", MUTE_ENGINE)
            engine = ChessEngine(path, "MuteBot")
            engine.start()
            try:
                self.assertIsNone(engine.get_move(chess.Board(), time_ms=100))
            finally:
                engine.quit()

    def test_sending_to_a_closed_engine_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_engine(tmp, "mute.py", MUTE_ENGINE)
            engine = ChessEngine(path, "MuteBot")
            engine.start()
            engine.quit()
            with self.assertRaises(EngineDied):
                engine.send("isready")


class TestBookSetting(unittest.TestCase):
    """The handshake has to actually carry the setting

    The book chooses between replies at random, so a tournament that leaves
    it on gives a different result each run and lets the book rather than
    either engine decide the opening.
    """

    class Recorder(ChessEngine):
        """Records the handshake instead of talking to a real engine"""

        def __init__(self):
            super().__init__("./nothing.py", "Recorder")
            self.sent = []

        def send(self, command):
            self.sent.append(command)

        def wait_for(self, token, timeout=5):
            return [token]

    def handshake(self, use_book):
        """The commands start() sends, with no subprocess involved

        Popen is replaced rather than pointed at a real script: without
        this, each test would launch a python3 process on a file that does
        not exist and leave it behind.
        """
        engine = self.Recorder()
        fake = unittest.mock.MagicMock()
        fake.stdout = iter(())
        with unittest.mock.patch.object(subprocess, "Popen", return_value=fake):
            engine.start(use_book=use_book)
        return engine.sent

    def test_the_option_is_sent_when_the_book_is_off(self):
        self.assertIn("setoption name OwnBook value false", self.handshake(False))

    def test_the_option_is_not_sent_when_the_book_is_on(self):
        self.assertNotIn("setoption name OwnBook value false", self.handshake(True))

    def test_it_comes_after_uciok_and_before_isready(self):
        """A host sets options between the handshake and the ready check"""
        sent = self.handshake(False)
        option = sent.index("setoption name OwnBook value false")
        self.assertLess(sent.index("uci"), option)
        self.assertLess(option, sent.index("isready"))

    def test_the_book_is_off_by_default_in_a_tournament(self):
        with unittest.mock.patch("sys.argv", ["simple_tournament.py"]):
            self.assertFalse(parse_args().book)


class TestShutdown(unittest.TestCase):
    """Cleanup runs from finally blocks, so it must not raise"""

    def engine(self, tmp):
        path = write_engine(tmp, "mute.py", MUTE_ENGINE)
        engine = ChessEngine(path, "MuteBot")
        engine.start()
        return engine

    def test_quitting_twice_does_not_raise(self):
        """A second quit used to raise and skip the rest of the cleanup"""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self.engine(tmp)
            engine.quit()
            engine.quit()  # must be a no-op, not a broken pipe

    def test_the_process_is_reaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = self.engine(tmp)
            engine.quit()
            self.assertIsNotNone(engine.process.poll())

    def test_quitting_an_unstarted_engine_does_nothing(self):
        engine = ChessEngine("never_started.py", "Ghost")
        engine.quit()

    def test_a_dead_engine_can_still_be_quit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_engine(tmp, "mute.py", MUTE_ENGINE)
            engine = ChessEngine(path, "MuteBot")
            engine.start()
            engine.process.kill()
            engine.process.wait(timeout=5)
            engine.quit()  # already dead, still must not raise


class TestGameResults(unittest.TestCase):
    def test_resigning_engine_loses(self):
        """Returning no move hands the game to the opponent"""
        result, game = play_game(ResigningEngine("W"), FakeEngine("B"), max_moves=10)
        self.assertEqual(result, "incomplete")
        self.assertEqual(game.headers["Result"], "*")

    def test_played_moves_are_recorded_in_the_pgn(self):
        white = FakeEngine("White", ["e2e4", "g1f3"])
        black = FakeEngine("Black", ["e7e5", "b8c6"])
        _, game = play_game(white, black, max_moves=4)
        self.assertGreater(len(list(game.mainline_moves())), 0)

    def test_headers_name_both_engines(self):
        _, game = play_game(FakeEngine("Alice"), FakeEngine("Bob"), max_moves=2)
        self.assertEqual(game.headers["White"], "Alice")
        self.assertEqual(game.headers["Black"], "Bob")

    def test_move_cap_produces_a_draw(self):
        result, game = play_game(FakeEngine("W"), FakeEngine("B"), max_moves=4)
        self.assertEqual(result, "draw")
        self.assertEqual(game.headers["Result"], "1/2-1/2")

    def test_result_and_game_are_returned_together(self):
        outcome = play_game(FakeEngine("W"), FakeEngine("B"), max_moves=2)
        self.assertEqual(len(outcome), 2)


class TestSaveGames(unittest.TestCase):
    def test_games_are_written(self):
        _, game = play_game(FakeEngine("W"), FakeEngine("B"), max_moves=2)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pgn")
            save_games([game], path)
            with open(path) as handle:
                text = handle.read()
        self.assertIn("[White \"W\"]", text)

    def test_no_games_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pgn")
            save_games([], path)
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
