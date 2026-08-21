#!/usr/bin/env python3
"""
Tests for the UCI options a host can set.

The wire format is fiddly: an option name may contain spaces, and so may
its value, so the command cannot simply be split on whitespace. And an
option the engine does not advertise can never be set at all, so the
advertised list and the code that honours it have to agree.

Run with:
    python3 -m unittest test_uci_options
"""

import unittest

import chess

from knightmare_bot import (
    BYTES_PER_TT_ENTRY,
    KnightmareBot,
    TT_MAX_ENTRIES,
    UCI_OPTIONS,
    apply_option,
    entries_to_hash_mb,
    hash_mb_to_entries,
    option_lines,
    parse_setoption,
)


class TestParseSetoption(unittest.TestCase):
    """Splitting on the keywords rather than on whitespace"""

    def test_a_name_and_a_value(self):
        self.assertEqual(parse_setoption("setoption name Hash value 64"),
                         ("Hash", "64"))

    def test_a_name_with_no_value(self):
        """A button has no value, so None is the honest answer"""
        self.assertEqual(parse_setoption("setoption name Clear Hash"),
                         ("Clear Hash", None))

    def test_a_name_containing_spaces(self):
        self.assertEqual(parse_setoption("setoption name Some Long Name value 7"),
                         ("Some Long Name", "7"))

    def test_a_value_containing_spaces(self):
        self.assertEqual(parse_setoption("setoption name Path value /a b/c"),
                         ("Path", "/a b/c"))

    def test_an_option_actually_called_value(self):
        """Splitting on the first "value" would leave it with no name"""
        self.assertEqual(parse_setoption("setoption name value value 7"),
                         ("value", "7"))

    def test_a_missing_name_is_refused(self):
        self.assertIsNone(parse_setoption("setoption name"))
        self.assertIsNone(parse_setoption("setoption"))

    def test_a_missing_name_keyword_is_refused(self):
        self.assertIsNone(parse_setoption("setoption Hash value 64"))

    def test_another_command_is_refused(self):
        self.assertIsNone(parse_setoption("go depth 4"))
        self.assertIsNone(parse_setoption(""))


class TestAdvertisedOptions(unittest.TestCase):
    """A host only offers what the engine says it has"""

    def test_every_option_is_advertised(self):
        names = [line.split()[2] for line in option_lines()]
        self.assertEqual(names, [name for name, *_ in UCI_OPTIONS])

    def test_a_spin_carries_its_range(self):
        line = next(l for l in option_lines() if "Hash" in l)
        self.assertIn("type spin", line)
        self.assertIn("min 1", line)
        self.assertIn("max 1024", line)

    def test_a_check_says_true_or_false(self):
        """Not Python's True, which no host would understand"""
        line = next(l for l in option_lines() if "OwnBook" in l)
        self.assertIn("type check", line)
        self.assertIn("default true", line)

    def test_the_advertised_hash_default_is_the_real_one(self):
        """A host that sets nothing must get what it was promised"""
        line = next(l for l in option_lines() if "Hash" in l)
        advertised = int(line.split("default")[1].split()[0])
        self.assertEqual(advertised, entries_to_hash_mb(TT_MAX_ENTRIES))
        self.assertAlmostEqual(hash_mb_to_entries(advertised), TT_MAX_ENTRIES,
                               delta=TT_MAX_ENTRIES * 0.01)

    def test_everything_advertised_can_actually_be_set(self):
        bot = KnightmareBot()
        for name, kind, default, *_ in UCI_OPTIONS:
            with self.subTest(option=name):
                value = str(default).lower() if kind == "check" else str(default)
                self.assertNotIn("unknown", apply_option(bot, name, value))


class TestHashConversion(unittest.TestCase):
    def test_megabytes_become_entries(self):
        self.assertEqual(hash_mb_to_entries(1), 1024 * 1024 // BYTES_PER_TT_ENTRY)

    def test_more_memory_means_more_entries(self):
        self.assertGreater(hash_mb_to_entries(64), hash_mb_to_entries(8))

    def test_a_tiny_setting_still_leaves_room_for_one(self):
        """A table that can hold nothing would make every store a no-op"""
        self.assertGreaterEqual(hash_mb_to_entries(0), 1)

    def test_it_round_trips(self):
        for megabytes in (1, 8, 38, 256, 1024):
            with self.subTest(mb=megabytes):
                self.assertEqual(entries_to_hash_mb(hash_mb_to_entries(megabytes)),
                                 megabytes)


class TestApplyOption(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_hash_resizes_the_table(self):
        apply_option(self.bot, "Hash", "64")
        self.assertEqual(self.bot.tt_limit, hash_mb_to_entries(64))

    def test_hash_is_clamped_to_the_advertised_range(self):
        apply_option(self.bot, "Hash", "999999")
        self.assertEqual(self.bot.tt_limit, hash_mb_to_entries(1024))
        apply_option(self.bot, "Hash", "-5")
        self.assertEqual(self.bot.tt_limit, hash_mb_to_entries(1))

    def test_a_non_numeric_hash_is_refused(self):
        before = self.bot.tt_limit
        self.assertIn("needs a number", apply_option(self.bot, "Hash", "abc"))
        self.assertEqual(self.bot.tt_limit, before)

    def test_shrinking_the_table_drops_what_no_longer_fits(self):
        """Otherwise the entries sit there until something clears them"""
        self.bot.transposition_table = {i: (0, None, "exact") for i in range(5000)}
        apply_option(self.bot, "Hash", "1")
        self.assertLessEqual(len(self.bot.transposition_table), self.bot.tt_limit)

    def test_growing_the_table_keeps_what_is_there(self):
        self.bot.transposition_table = {1: (0, None, "exact")}
        apply_option(self.bot, "Hash", "1024")
        self.assertEqual(len(self.bot.transposition_table), 1)

    def test_ownbook_can_be_turned_off(self):
        apply_option(self.bot, "OwnBook", "false")
        self.assertFalse(self.bot.use_book)

    def test_ownbook_can_be_turned_back_on(self):
        apply_option(self.bot, "OwnBook", "false")
        apply_option(self.bot, "OwnBook", "true")
        self.assertTrue(self.bot.use_book)

    def test_ownbook_accepts_the_usual_spellings(self):
        for text in ("true", "TRUE", "1", "yes", "on"):
            with self.subTest(value=text):
                self.bot.use_book = False
                apply_option(self.bot, "OwnBook", text)
                self.assertTrue(self.bot.use_book)

    def test_anything_else_turns_ownbook_off(self):
        for text in ("false", "0", "no", "", "nonsense"):
            with self.subTest(value=text):
                self.bot.use_book = True
                apply_option(self.bot, "OwnBook", text)
                self.assertFalse(self.bot.use_book)

    def test_option_names_are_matched_without_case(self):
        apply_option(self.bot, "ownbook", "false")
        self.assertFalse(self.bot.use_book)

    def test_an_unknown_option_says_so(self):
        """A host that has misspelled one would otherwise see nothing"""
        self.assertIn("unknown", apply_option(self.bot, "Nonsense", "3"))

    def test_an_unknown_option_changes_nothing(self):
        before = (self.bot.tt_limit, self.bot.use_book)
        apply_option(self.bot, "Nonsense", "3")
        self.assertEqual((self.bot.tt_limit, self.bot.use_book), before)


class TestOptionsAffectTheSearch(unittest.TestCase):
    """The settings have to reach the search, not just the attributes"""

    def test_turning_the_book_off_makes_it_search(self):
        import contextlib
        import io

        def output_for(use_book):
            bot = KnightmareBot()
            bot.use_book = use_book
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                bot.get_move(chess.Board(), 1.0, 2)
            return buffer.getvalue()

        self.assertIn("book move", output_for(True))
        self.assertNotIn("book move", output_for(False))

    def test_a_small_table_stays_within_its_limit(self):
        bot = KnightmareBot()
        apply_option(bot, "Hash", "1")
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        bot.get_move(board, 1.0, 4)
        self.assertLessEqual(len(bot.transposition_table), bot.tt_limit)

    def test_a_capped_table_still_finds_a_legal_move(self):
        bot = KnightmareBot()
        bot.tt_limit = 1
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        self.assertIn(bot.get_move(board, 0.5, 3), board.legal_moves)


if __name__ == "__main__":
    unittest.main()
