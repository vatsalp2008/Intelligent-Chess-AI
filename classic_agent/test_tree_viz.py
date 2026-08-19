#!/usr/bin/env python3
"""
Unit tests for the minimax tree visualiser.

The figures are teaching material, so a wrong evaluation would print wrong
numbers on a diagram someone reads to understand minimax. The sign
convention is the part worth pinning: build_node alternates maximizing and
minimizing levels and therefore needs absolute, White-positive scores. This
file once returned side-relative scores, which made the values on the
diagram incomparable.

Needs matplotlib, which the visualiser imports.

Run with:
    python3 -m unittest test_tree_viz
"""

import unittest

import chess

import standalone_tree_viz as viz


class TestSimpleEvaluate(unittest.TestCase):
    def test_the_starting_position_is_near_level(self):
        self.assertLess(abs(viz.simple_evaluate(chess.Board())), 200)

    def test_extra_material_favours_its_owner(self):
        white_up = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        black_up = chess.Board("3qk3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertGreater(viz.simple_evaluate(white_up), 0)
        self.assertLess(viz.simple_evaluate(black_up), 0)

    def test_the_score_does_not_flip_with_the_side_to_move(self):
        """The bug this file used to have: scores were side-relative

        build_node treats even depths as maximizing levels, so a score that
        changed sign with the turn made the diagram's numbers meaningless.
        """
        white_turn = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        black_turn = chess.Board("4k3/8/8/8/8/8/8/3QK3 b - - 0 1")
        self.assertGreater(viz.simple_evaluate(white_turn), 0)
        self.assertGreater(viz.simple_evaluate(black_turn), 0)

    def test_mirrored_positions_score_opposite(self):
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        self.assertEqual(
            viz.simple_evaluate(board), -viz.simple_evaluate(board.mirror())
        )

    def test_checkmate_is_decisive(self):
        black_mated = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertTrue(black_mated.is_checkmate())
        self.assertGreater(viz.simple_evaluate(black_mated), 1000)

    def test_stalemate_is_level(self):
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(board.is_stalemate())
        self.assertEqual(viz.simple_evaluate(board), 0)

    def test_the_board_is_not_disturbed(self):
        board = chess.Board()
        before = board.fen()
        viz.simple_evaluate(board)
        self.assertEqual(board.fen(), before)


class TestTreePositions(unittest.TestCase):
    def test_nodes_are_laid_out_by_level(self):
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edges_from([(0, 1), (0, 2), (1, 3), (1, 4)])
        info = {n: {"depth": 0} for n in graph.nodes()}

        pos = viz.calculate_tree_positions(graph, info, 0)

        self.assertEqual(len(pos), graph.number_of_nodes())
        # Deeper levels sit lower on the page
        self.assertGreater(pos[0][1], pos[1][1])
        self.assertGreater(pos[1][1], pos[3][1])

    def test_the_root_is_centred(self):
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node(0)
        pos = viz.calculate_tree_positions(graph, {0: {"depth": 0}}, 0)
        self.assertEqual(pos[0], (0, 0))

    def test_siblings_are_spread_apart(self):
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_edges_from([(0, 1), (0, 2), (0, 3)])
        info = {n: {"depth": 0} for n in graph.nodes()}
        pos = viz.calculate_tree_positions(graph, info, 0)
        xs = sorted(pos[n][0] for n in (1, 2, 3))
        self.assertEqual(len(set(xs)), 3)


if __name__ == "__main__":
    unittest.main()
