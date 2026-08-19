#!/usr/bin/env python3
"""
Unit tests for the game tree generator.

These trees are teaching material for minimax and alpha-beta, so the
structural promises matter: leaves carry utilities, internal nodes do not,
zero-sum games really sum to zero, and a given seed reproduces.

Needs networkx.

Run with:
    python3 -m unittest test_generator
"""

import unittest

import networkx as nx

import generator


class TestRandomGame(unittest.TestCase):
    def build(self, rounds=2, actions=2, **kwargs):
        return generator.createRandomGame(rounds, actions, **kwargs)

    def leaves(self, graph):
        return [n for n in graph.nodes() if graph.out_degree(n) == 0]

    def internal(self, graph):
        return [n for n in graph.nodes() if graph.out_degree(n) > 0]

    def test_the_tree_has_the_expected_shape(self):
        """rounds*2 levels of branching, so a full tree of that depth"""
        graph = self.build(rounds=2, actions=2)
        expected = sum(2 ** level for level in range(2 * 2 + 1))
        self.assertEqual(graph.number_of_nodes(), expected)

    def test_it_is_a_directed_acyclic_tree(self):
        graph = self.build()
        self.assertTrue(nx.is_directed_acyclic_graph(graph))

    def test_leaves_carry_a_utility(self):
        graph = self.build()
        for node in self.leaves(graph):
            with self.subTest(node=node):
                self.assertIsNotNone(graph.nodes[node]["utility"])

    def test_internal_nodes_carry_no_utility(self):
        """They get filled in by whatever search the reader is studying"""
        graph = self.build()
        for node in self.internal(graph):
            with self.subTest(node=node):
                self.assertIsNone(graph.nodes[node]["utility"])

    def test_zero_sum_payoffs_sum_to_zero(self):
        graph = self.build(isZeroSum=True)
        for node in self.leaves(graph):
            with self.subTest(node=node):
                self.assertEqual(sum(graph.nodes[node]["utility"]), 0)

    def test_general_sum_payoffs_are_both_non_negative(self):
        graph = self.build(isZeroSum=False)
        for node in self.leaves(graph):
            with self.subTest(node=node):
                first, second = graph.nodes[node]["utility"]
                self.assertGreaterEqual(first, 0)
                self.assertGreaterEqual(second, 0)

    def test_the_same_seed_reproduces_the_same_payoffs(self):
        first = self.build(seed=7)
        second = self.build(seed=7)
        self.assertEqual(
            [first.nodes[n]["utility"] for n in self.leaves(first)],
            [second.nodes[n]["utility"] for n in self.leaves(second)],
        )

    def test_different_seeds_give_different_payoffs(self):
        first = self.build(seed=1)
        second = self.build(seed=2)
        self.assertNotEqual(
            [first.nodes[n]["utility"] for n in self.leaves(first)],
            [second.nodes[n]["utility"] for n in self.leaves(second)],
        )

    def test_more_actions_makes_a_wider_tree(self):
        self.assertGreater(
            self.build(actions=3).number_of_nodes(),
            self.build(actions=2).number_of_nodes(),
        )


class TestExampleTrees(unittest.TestCase):
    def test_the_textbook_tree_is_labelled(self):
        graph = generator.exampleGameTree()
        self.assertIn("A", graph.nodes())
        self.assertEqual(graph.nodes["b1"]["utility"], (3, -3))

    def test_the_textbook_tree_leaves_are_zero_sum(self):
        graph = generator.exampleGameTree()
        for node in graph.nodes():
            utility = graph.nodes[node]["utility"]
            if utility is not None:
                with self.subTest(node=node):
                    self.assertEqual(sum(utility), 0)

    def test_the_generic_tree_uses_the_payoffs_given(self):
        payoffs = list(range(1, 13))
        graph = generator.genericGameTree(payoffs)
        assigned = [
            graph.nodes[n]["utility"][0]
            for n in graph.nodes()
            if graph.nodes[n]["utility"] is not None
        ]
        self.assertEqual(sorted(assigned), sorted(payoffs))

    def test_the_generic_tree_is_acyclic(self):
        self.assertTrue(nx.is_directed_acyclic_graph(generator.genericGameTree()))


if __name__ == "__main__":
    unittest.main()
