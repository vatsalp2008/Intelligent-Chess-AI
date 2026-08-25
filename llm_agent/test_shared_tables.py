#!/usr/bin/env python3
"""
Guard the data that is duplicated across the two engines.

classic_agent/knightmare_bot.py and llm_agent/knightmare.py each carry
their own copy of the piece-square tables, because they are separate top
level scripts with no shared package between them. Copies drift silently,
so this test fails as soon as one is tuned without the other.

Run with:
    python3 -m unittest test_shared_tables
"""

import contextlib
import importlib.util
import io
import os
import sys
import unittest

import chess

import knightmare


def load_sibling(filename, module_name, directory=None):
    """Import a bot script by path, from this directory or a sibling"""
    here = os.path.dirname(os.path.abspath(__file__))
    parts = [here] + ([os.pardir, directory] if directory else []) + [filename]
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(*parts))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_classic():
    """Import the classic engine from the sibling directory"""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, os.pardir, "classic_agent", "knightmare_bot.py")
    spec = importlib.util.spec_from_file_location("classic_knightmare", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tactics(directory):
    """Import a tactics module from either agent directory"""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, os.pardir, directory, "tactics.py")
    spec = importlib.util.spec_from_file_location(f"{directory}_tactics", path)
    module = importlib.util.module_from_spec(spec)
    # tactics.py imports its own engine, so that directory has to be findable
    agent_dir = os.path.join(here, os.pardir, directory)
    sys.path.insert(0, agent_dir)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(agent_dir)
    return module


class TestTacticsSuitesMatch(unittest.TestCase):
    """The position lists are shared by copy, so they can drift

    They already did once: a wrong expectation was fixed in one copy and
    left in the other, where it sat waiting to fail the first time the
    engine chose that move.
    """

    @classmethod
    def setUpClass(cls):
        cls.classic = load_tactics("classic_agent")
        cls.baseline = load_tactics("llm_agent")

    def test_the_same_positions_are_tested(self):
        self.assertEqual(
            [(name, fen) for name, fen, _, _ in self.classic.POSITIONS],
            [(name, fen) for name, fen, _, _ in self.baseline.POSITIONS],
        )

    def test_the_same_moves_are_expected(self):
        self.assertEqual(
            [wanted for _, _, wanted, _ in self.classic.POSITIONS],
            [wanted for _, _, wanted, _ in self.baseline.POSITIONS],
        )

    def test_the_same_moves_are_forbidden(self):
        self.assertEqual(self.classic.FORBIDDEN, self.baseline.FORBIDDEN)

    def test_no_forbidden_move_is_also_an_expected_one(self):
        for name, fen, wanted, _ in self.classic.POSITIONS:
            forbidden = self.classic.FORBIDDEN.get(name, [])
            for move in forbidden:
                with self.subTest(position=name, move=move):
                    self.assertNotIn(move, wanted or [])


class TestTablesMatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classic = load_classic()

    def test_every_piece_table_matches(self):
        for piece_type, table in knightmare.PIECE_SQUARE_TABLES.items():
            with self.subTest(piece_type=piece_type):
                self.assertEqual(
                    table,
                    self.classic.PIECE_SQUARE_TABLES[piece_type],
                    "piece-square tables have drifted between the two engines",
                )

    def test_endgame_king_table_matches(self):
        self.assertEqual(
            knightmare.KING_ENDGAME_TABLE, self.classic.KING_ENDGAME_TABLE
        )

    def test_both_cover_the_whole_board(self):
        for table in list(knightmare.PIECE_SQUARE_TABLES.values()) + [
            knightmare.KING_ENDGAME_TABLE
        ]:
            self.assertEqual(len(table), 64)

    def test_lookup_agrees_between_engines(self):
        import chess

        for piece_type in knightmare.PIECE_SQUARE_TABLES:
            for square in (chess.A1, chess.D4, chess.G1, chess.H7):
                for color in (chess.WHITE, chess.BLACK):
                    with self.subTest(piece_type=piece_type, square=square, color=color):
                        self.assertEqual(
                            knightmare.piece_square_bonus(piece_type, square, color),
                            self.classic.piece_square_bonus(piece_type, square, color),
                        )


class TestMoveReplayAgrees(unittest.TestCase):
    """Three copies of "replay a position command's move list" exist

    classic_agent/knightmare_bot.py, llm_agent/knightmare_llm.py and
    llm_agent/random_chess_bot.py each have their own, because they are
    standalone UCI scripts. All three have to stop at the first move that
    will not apply rather than skipping it, so they must agree on exactly
    where a bad list stops. Copies drift silently, so this fails as soon as
    one is changed without the others.
    """

    CASES = [
        "e2e4 e7e5 g1f3 b8c6",
        "e2e4 d7d6 d7d5 g1f3",
        "e2e4 zzz e7e5",
        "",
        "not a move at all",
        "e2e4 e7e5 e7e5",
        "e2e4 e7e5 g1f3 g1f3",
    ]

    @classmethod
    def setUpClass(cls):
        cls.classic = load_classic()
        cls.llama = load_sibling("knightmare_llm.py", "llm_for_replay")
        cls.simple = load_sibling("random_chess_bot.py", "random_for_replay")

    def replays(self, text):
        """The three boards, quietly - all three report why they stopped"""
        with contextlib.redirect_stdout(io.StringIO()):
            return (
                self.classic.replay_moves(chess.Board(), text.split()),
                self.llama.replay_moves(chess.Board(), text),
                self.simple.apply_position(chess.Board(),
                                           f"position startpos moves {text}"),
            )

    def test_all_three_reach_the_same_position(self):
        for text in self.CASES:
            with self.subTest(moves=text):
                fens = {board.fen() for board in self.replays(text)}
                self.assertEqual(len(fens), 1, fens)

    def test_all_three_stop_at_the_same_move(self):
        for text in self.CASES:
            with self.subTest(moves=text):
                counts = {len(board.move_stack) for board in self.replays(text)}
                self.assertEqual(len(counts), 1, counts)

    def test_all_three_stop_rather_than_skip(self):
        """The bug being guarded against: a game nobody sent"""
        for board in self.replays("e2e4 d7d6 d7d5 g1f3"):
            self.assertEqual([m.uci() for m in board.move_stack],
                             ["e2e4", "d7d6"])

    def test_all_three_say_why_they_stopped(self):
        for text in ("e2e4 d7d6 d7d5", "e2e4 zzz"):
            with self.subTest(moves=text):
                for replay in (
                    lambda: self.classic.replay_moves(chess.Board(), text.split()),
                    lambda: self.llama.replay_moves(chess.Board(), text),
                    lambda: self.simple.apply_position(
                        chess.Board(), f"position startpos moves {text}"),
                ):
                    buffer = io.StringIO()
                    with contextlib.redirect_stdout(buffer):
                        replay()
                    self.assertIn("stopping replay", buffer.getvalue())


class TestDrawShortcutAgrees(unittest.TestCase):
    """Both engines decide "is there anything left to search" separately

    One asks halfmove_clock >= 100 and the other asks
    can_claim_fifty_moves(), which are meant to be the same question. If
    they ever stop agreeing, one engine will search on from a position the
    other has already written off.
    """

    @classmethod
    def setUpClass(cls):
        cls.classic = load_classic()

    POSITIONS = [
        ("fresh board", chess.STARTING_FEN),
        ("clock at 99", "4k3/8/8/8/8/8/1Q6/4K3 w - - 99 60"),
        ("clock at 100", "4k3/8/8/8/8/8/1Q6/4K3 w - - 100 60"),
        ("clock past 100", "4k3/8/8/8/8/8/1Q6/4K3 w - - 140 80"),
        ("checkmate", "4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1"),
        ("stalemate", "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"),
        ("bare kings", "4k3/8/8/8/8/8/8/4K3 w - - 0 1"),
    ]

    def test_both_engines_agree(self):
        for name, fen in self.POSITIONS:
            with self.subTest(position=name):
                board = chess.Board(fen)
                self.assertEqual(
                    self.classic.KnightmareBot.game_over(board),
                    knightmare.KnightmareFast.game_over(board),
                    name,
                )

    def test_they_agree_on_a_repetition(self):
        board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
        for uci in ("a1a2", "e8e7", "a2a1", "e7e8") * 2:
            board.push(chess.Move.from_uci(uci))
        self.assertTrue(board.is_repetition(3))
        self.assertEqual(self.classic.KnightmareBot.game_over(board),
                         knightmare.KnightmareFast.game_over(board))


if __name__ == "__main__":
    unittest.main()
