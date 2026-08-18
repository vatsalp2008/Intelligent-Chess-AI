#!/usr/bin/env python3
"""
Unit tests for the evaluation weight tuner.

The tuner mutates module level constants while it works, so the important
property is that it always puts them back: a leaked weight would silently
change the engine for everything that runs afterwards in the same process.

Nothing here needs Stockfish; the reference scores are stubbed.

Run with:
    python3 -m unittest test_tune_eval
"""

import unittest

import chess

import knightmare_bot
import tune_eval


class FakeEngine:
    """Stands in for Stockfish, scoring by material only"""

    def analyse(self, board, limit):
        score = 0
        values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                  chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                signed = values[piece.piece_type]
                score += signed if piece.color == chess.WHITE else -signed
        pv = list(board.legal_moves)[:1]
        return {"score": chess.engine.PovScore(chess.engine.Cp(score), chess.WHITE),
                "pv": pv}


class TestPositions(unittest.TestCase):
    def test_every_position_is_a_legal_fen(self):
        """Hand written FENs were repeatedly malformed, so check them"""
        for fen in tune_eval.POSITIONS:
            with self.subTest(fen=fen):
                chess.Board(fen)  # raises if malformed

    def test_positions_are_not_already_finished(self):
        for fen in tune_eval.POSITIONS:
            with self.subTest(fen=fen):
                self.assertFalse(chess.Board(fen).is_game_over())

    def test_there_are_enough_positions_to_mean_something(self):
        self.assertGreaterEqual(len(tune_eval.POSITIONS), 8)


class TestTunableTable(unittest.TestCase):
    def test_every_named_weight_exists_in_the_engine(self):
        for name in tune_eval.TUNABLE:
            with self.subTest(name=name):
                self.assertTrue(hasattr(knightmare_bot, name))

    def test_every_weight_has_candidate_values(self):
        for name, values in tune_eval.TUNABLE.items():
            with self.subTest(name=name):
                self.assertGreaterEqual(len(values), 2)

    def test_candidates_are_integers(self):
        for name, values in tune_eval.TUNABLE.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    self.assertIsInstance(value, int)


class TestSweepRestoresWeights(unittest.TestCase):
    """The tuner must never leave a weight changed behind it"""

    def test_weight_is_restored_after_a_sweep(self):
        name = "BISHOP_PAIR_BONUS"
        original = getattr(knightmare_bot, name)

        tune_eval.sweep_weight(
            FakeEngine(), name, [0, 999], tune_eval.POSITIONS[:1],
            {tune_eval.POSITIONS[0]: 0}, {}, verbose=False,
        )

        self.assertEqual(getattr(knightmare_bot, name), original)

    def test_weight_is_restored_even_if_scoring_raises(self):
        name = "BISHOP_PAIR_BONUS"
        original = getattr(knightmare_bot, name)

        class Exploding:
            def analyse(self, board, limit):
                raise RuntimeError("engine died")

        with self.assertRaises(RuntimeError):
            tune_eval.sweep_weight(
                Exploding(), name, [0, 999], tune_eval.POSITIONS[:1],
                {tune_eval.POSITIONS[0]: 0}, {}, verbose=False,
            )

        self.assertEqual(getattr(knightmare_bot, name), original)

    def test_sweep_reports_a_score_for_every_value(self):
        values = [0, 15, 30]
        losses = tune_eval.sweep_weight(
            FakeEngine(), "BISHOP_PAIR_BONUS", values,
            tune_eval.POSITIONS[:2],
            {fen: 0 for fen in tune_eval.POSITIONS[:2]}, {}, verbose=False,
        )
        self.assertEqual(sorted(losses), sorted(values))


class TestReport(unittest.TestCase):
    def test_a_clearly_lower_loss_is_reported_as_a_candidate(self):
        self.assertTrue(tune_eval.report("W", {10: 500, 20: 400}, 10))

    def test_a_higher_loss_is_not(self):
        self.assertFalse(tune_eval.report("W", {10: 400, 20: 500}, 10))

    def test_ties_keep_the_current_value(self):
        self.assertFalse(tune_eval.report("W", {10: 400, 20: 400}, 10))

    def test_the_observed_false_positive_is_rejected(self):
        """ISOLATED_PAWN_PENALTY 150 looked 2% better and scored 27% in a match

        Pinning the real numbers means the threshold cannot quietly drift
        back down to where it would wave that through again.
        """
        self.assertFalse(tune_eval.report("ISOLATED_PAWN_PENALTY", {12: 615, 150: 601}, 12))

    def test_the_observed_true_positive_is_reported(self):
        """BISHOP_PAIR_BONUS looked 9% better and held up in a match"""
        self.assertTrue(tune_eval.report("BISHOP_PAIR_BONUS", {30: 615, 200: 560}, 30))

    def test_the_threshold_sits_between_those_two_cases(self):
        self.assertGreater(tune_eval.MIN_RELATIVE_GAIN, 14 / 615)
        self.assertLess(tune_eval.MIN_RELATIVE_GAIN, 55 / 615)

    def test_zero_loss_is_not_divided_by(self):
        """A perfect score must not raise instead of reporting"""
        self.assertFalse(tune_eval.report("W", {10: 0, 20: 0}, 10))


if __name__ == "__main__":
    unittest.main()
