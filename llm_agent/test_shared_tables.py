#!/usr/bin/env python3
"""
Guard the evaluation tables that are duplicated across the two engines.

classic_agent/knightmare_bot.py and llm_agent/knightmare.py each carry
their own copy of the piece-square tables, because they are separate top
level scripts with no shared package between them. Copies drift silently,
so this test fails as soon as one is tuned without the other.

Run with:
    python3 -m unittest test_shared_tables
"""

import importlib.util
import os
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
