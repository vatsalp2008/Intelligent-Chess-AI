#!/usr/bin/env python3
"""
Tests for the Stockfish interface's settings endpoints.

An out of range skill level makes engine.configure() raise, which the move
handler catches by falling back to random moves. The user then thinks they
are playing Stockfish and are not, with nothing in the interface to say so.
That is why these endpoints validate, and why the validation is worth
pinning down.

Driven through the Flask test client, so no server or Stockfish is needed.

Run with:
    python3 -m unittest test_web_settings
"""

import unittest

import knightmare_vs_stockfish as web


class SettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()


class TestSkillLevel(SettingsTestCase):
    def post(self, payload):
        return self.client.post("/set_stockfish_level", json=payload)

    def test_a_level_in_range_is_accepted(self):
        response = self.post({"level": 10})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(web.stockfish_level, 10)

    def test_both_ends_of_the_range_are_accepted(self):
        for level in (web.MIN_SKILL_LEVEL, web.MAX_SKILL_LEVEL):
            with self.subTest(level=level):
                self.assertEqual(self.post({"level": level}).status_code, 200)

    def test_a_level_above_the_range_is_rejected(self):
        """Stockfish would raise on this, leaving us silently playing randomly"""
        before = web.stockfish_level
        response = self.post({"level": 99})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(web.stockfish_level, before)

    def test_a_negative_level_is_rejected(self):
        self.assertEqual(self.post({"level": -1}).status_code, 400)

    def test_a_non_numeric_level_is_rejected(self):
        response = self.post({"level": "abc"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("number", response.get_json()["error"])

    def test_the_error_names_the_valid_range(self):
        error = self.post({"level": 99}).get_json()["error"]
        self.assertIn(str(web.MIN_SKILL_LEVEL), error)
        self.assertIn(str(web.MAX_SKILL_LEVEL), error)

    def test_a_missing_body_does_not_error(self):
        """request.get_json() used to raise 415 without a JSON body"""
        self.assertEqual(self.client.post("/set_stockfish_level").status_code, 200)


class TestThinkTime(SettingsTestCase):
    def post(self, payload):
        return self.client.post("/set_stockfish_time", json=payload)

    def test_a_time_in_range_is_accepted(self):
        self.assertEqual(self.post({"time": 0.5}).status_code, 200)
        self.assertEqual(web.stockfish_time, 0.5)

    def test_too_long_is_rejected(self):
        before = web.stockfish_time
        self.assertEqual(self.post({"time": 999}).status_code, 400)
        self.assertEqual(web.stockfish_time, before)

    def test_too_short_is_rejected(self):
        self.assertEqual(self.post({"time": 0}).status_code, 400)

    def test_a_non_numeric_time_is_rejected(self):
        self.assertEqual(self.post({"time": "soon"}).status_code, 400)


class TestColours(SettingsTestCase):
    def test_colours_can_be_swapped(self):
        self.client.post("/set_colors", json={"white_is_knightmare": True})
        self.assertTrue(web.app.config["white_is_knightmare"])
        self.client.post("/set_colors", json={"white_is_knightmare": False})
        self.assertFalse(web.app.config["white_is_knightmare"])

    def test_a_missing_body_defaults_to_stockfish_as_white(self):
        self.assertEqual(self.client.post("/set_colors").status_code, 200)
        self.assertFalse(web.app.config["white_is_knightmare"])

    def test_the_value_is_coerced_to_a_boolean(self):
        self.client.post("/set_colors", json={"white_is_knightmare": "yes"})
        self.assertIsInstance(web.app.config["white_is_knightmare"], bool)


class TestBoardEndpoint(SettingsTestCase):
    def test_the_board_reports_whether_stockfish_is_available(self):
        data = self.client.get("/board").get_json()
        self.assertIn("stockfish_available", data)

    def test_the_board_reports_the_engine_info_field(self):
        self.assertIn("engine", self.client.get("/board").get_json())

    def test_a_new_game_clears_the_history(self):
        self.client.post("/new_game")
        self.assertEqual(self.client.get("/board").get_json()["moves"], [])


if __name__ == "__main__":
    unittest.main()
