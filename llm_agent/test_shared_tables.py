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

import importlib.util
import os
import sys
import unittest

import knightmare


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


if __name__ == "__main__":
    unittest.main()
