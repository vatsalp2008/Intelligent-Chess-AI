#!/usr/bin/env python3
"""
Unit tests for the per-position diagnostic script.

Its whole job is to survive misbehaving engines, so the failure paths are
the point: an engine that never speaks, one that dies mid-test, one that
answers normally. Each case is a real subprocess, driven from a temporary
script.

Run with:
    python3 -m unittest test_diagnose
"""

import os
import subprocess
import tempfile
import time
import unittest

import diagnose_knight

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Exits before saying anything
DEAD = "import sys\nsys.exit(1)\n"

# Answers uci and isready, then goes quiet
MUTE = """
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

# A minimal but complete engine
WORKING = """
import sys, chess
board = chess.Board()
while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if line == "uci":
        print("id name Tiny"); print("uciok"); sys.stdout.flush()
    elif line == "isready":
        print("readyok"); sys.stdout.flush()
    elif line.startswith("position fen "):
        board = chess.Board(line[len("position fen "):])
    elif line == "ucinewgame":
        board = chess.Board()
    elif line.startswith("go"):
        print(f"bestmove {next(iter(board.legal_moves))}"); sys.stdout.flush()
    elif line == "quit":
        break
"""


def write(directory, name, source):
    path = os.path.join(directory, name)
    with open(path, "w") as handle:
        handle.write(source)
    return path


class TestWaitFor(unittest.TestCase):
    def spawn(self, code):
        proc = subprocess.Popen(
            ["python3", "-c", code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        self.addCleanup(proc.kill)
        return proc, diagnose_knight.start_reader(proc)

    def test_a_token_that_arrives_is_returned(self):
        _, lines = self.spawn("print('uciok', flush=True); input()")
        self.assertIsNotNone(diagnose_knight.wait_for(lines, "uciok", timeout=5))

    def test_a_closed_pipe_gives_up_rather_than_spinning(self):
        proc, lines = self.spawn("pass")
        proc.wait(timeout=5)
        start = time.time()
        self.assertIsNone(diagnose_knight.wait_for(lines, "uciok", timeout=5))
        self.assertLess(time.time() - start, 5)

    def test_a_silent_engine_times_out(self):
        """The bug this replaced: a live but silent engine blocked forever"""
        _, lines = self.spawn("import time; time.sleep(30)")
        start = time.time()
        self.assertIsNone(diagnose_knight.wait_for(lines, "uciok", timeout=1))
        self.assertLess(time.time() - start, 5)


class TestTestPosition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_dead_engine_reports_no_moves_quickly(self):
        path = write(self.tmp.name, "dead.py", DEAD)
        start = time.time()
        self.assertEqual(diagnose_knight.test_position(path, STARTPOS), [])
        self.assertLess(time.time() - start, 10)

    def test_a_mute_engine_reports_no_moves(self):
        path = write(self.tmp.name, "mute.py", MUTE)
        self.assertEqual(diagnose_knight.test_position(path, STARTPOS), [])

    def test_a_working_engine_reports_its_moves(self):
        path = write(self.tmp.name, "tiny.py", WORKING)
        moves = diagnose_knight.test_position(path, STARTPOS)
        self.assertEqual(len(moves), 3)

    def test_the_reported_moves_are_legal(self):
        import chess

        path = write(self.tmp.name, "tiny.py", WORKING)
        board = chess.Board(STARTPOS)
        for uci in diagnose_knight.test_position(path, STARTPOS):
            with self.subTest(uci=uci):
                self.assertIn(chess.Move.from_uci(uci), board.legal_moves)


if __name__ == "__main__":
    unittest.main()
