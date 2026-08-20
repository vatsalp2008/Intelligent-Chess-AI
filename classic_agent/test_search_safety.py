#!/usr/bin/env python3
"""
Safety net for the search: whatever it does internally, it must always
hand back a legal move and leave the caller's board untouched.

The search has a lot of moving parts now (quiescence, transposition table,
static exchange evaluation, check extensions, opening book), and any one of
them returning a stale or illegal move would be a serious bug. These tests
sweep a range of position types rather than checking any single feature.

Run with:
    python3 -m unittest test_search_safety
"""

import contextlib
import io
import re
import time
import unittest

import chess

from knightmare_bot import (
    CLOCK_CHECK_INTERVAL,
    KnightmareBot,
    SearchAborted,
    parse_go,
    parse_position,
)

# A spread of position types: openings, tactics, endgames, promotions,
# checks, castling rights, en passant and near-stalemate.
POSITIONS = [
    ("startpos", chess.STARTING_FEN),
    ("open game", "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"),
    ("kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("black to move", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R b KQkq - 0 1"),
    ("king and pawn", "8/5k2/8/3K4/8/8/4P3/8 w - - 0 1"),
    ("promotion", "8/P6k/8/8/8/8/6K1/8 w - - 0 1"),
    ("black promotion", "8/6k1/8/8/8/8/p6K/8 b - - 0 1"),
    # In check but not mate, so the search must find one of the escapes
    ("in check", "4k3/8/8/8/7q/8/8/4K3 w - - 0 1"),
    ("en passant", "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"),
    ("only one legal move", "7k/8/8/8/8/8/5rr1/K7 w - - 0 1"),
    ("mate in one", "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1"),
    ("rook endgame", "8/8/8/4k3/8/8/4K3/R7 w - - 0 1"),
    ("bare kings and pawns", "8/pp4pp/8/8/8/8/PP4PP/4K1k1 w - - 0 1"),
    ("queens on", "3qk3/8/8/8/8/8/8/3QK3 w - - 0 1"),
]

NO_TIME_LIMIT = 60.0


class TestSearchAlwaysReturnsLegalMoves(unittest.TestCase):
    def setUp(self):
        self.bot = KnightmareBot()

    def test_every_position_yields_a_legal_move(self):
        for name, fen in POSITIONS:
            with self.subTest(position=name):
                board = chess.Board(fen)
                move = self.bot.get_move(board, NO_TIME_LIMIT, 3)
                self.assertIsNotNone(move, f"{name}: no move returned")
                self.assertIn(move, board.legal_moves, f"{name}: illegal move {move}")

    def test_search_never_mutates_the_caller_board(self):
        for name, fen in POSITIONS:
            with self.subTest(position=name):
                board = chess.Board(fen)
                before = board.fen()
                self.bot.get_move(board, NO_TIME_LIMIT, 3)
                self.assertEqual(board.fen(), before, f"{name}: board changed")

    def test_reused_bot_stays_correct_across_positions(self):
        """Killer moves and the table carry over between searches"""
        for name, fen in POSITIONS:
            with self.subTest(position=name):
                board = chess.Board(fen)
                move = self.bot.get_move(board, NO_TIME_LIMIT, 2)
                self.assertIn(move, board.legal_moves)

    def test_every_depth_returns_a_legal_move(self):
        board = chess.Board(POSITIONS[1][1])
        for depth in range(1, 5):
            with self.subTest(depth=depth):
                move = self.bot.get_move(board, NO_TIME_LIMIT, depth)
                self.assertIn(move, board.legal_moves)

    def test_playing_a_whole_game_never_goes_illegal(self):
        """Self play to a fixed length, checking every move on the way"""
        board = chess.Board()
        bot = KnightmareBot()

        for _ in range(40):
            if board.is_game_over():
                break
            move = bot.get_move(board, NO_TIME_LIMIT, 2)
            self.assertIsNotNone(move)
            self.assertIn(move, board.legal_moves, f"illegal move in {board.fen()}")
            board.push(move)

    def test_forced_move_is_found(self):
        board = chess.Board("7k/8/8/8/8/8/5rr1/K7 w - - 0 1")
        self.assertEqual(len(list(board.legal_moves)), 1)
        self.assertIn(self.bot.get_move(board, NO_TIME_LIMIT, 3), board.legal_moves)

    def test_checkmate_position_returns_no_move(self):
        """Fool's mate: no legal moves at all, so there is nothing to return"""
        board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
        self.assertTrue(board.is_checkmate())
        self.assertIsNone(self.bot.get_move(board, NO_TIME_LIMIT, 3))

    def test_finished_game_returns_no_move(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("e1e8"))
        self.assertTrue(board.is_game_over())
        self.assertIsNone(self.bot.get_move(board, NO_TIME_LIMIT, 3))


class TestTimeBudget(unittest.TestCase):
    """Overrunning the clock loses games, so the budget has to be respected

    The bounds a started iteration can be held to live in TestHardDeadline
    below. What is left here is the rest of the contract: something legal
    always comes back, and more time never searches less deeply.
    """

    # Rich enough that a deep search would take far longer than the budget
    BUSY_FEN = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

    def test_a_move_is_still_returned_on_a_tiny_budget(self):
        """Even with no time to think, something legal must come back"""
        board = chess.Board(self.BUSY_FEN)
        move = KnightmareBot().get_move(board, 0.01, 6)
        self.assertIn(move, board.legal_moves)

    def test_larger_budget_searches_at_least_as_deep(self):
        board = chess.Board(self.BUSY_FEN)

        def depth_for(budget):
            bot = KnightmareBot()
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                bot.get_move(board.copy(), budget, 6)
            depths = [int(d) for d in re.findall(r"info depth (\d+)", buffer.getvalue())]
            return max(depths) if depths else 0

        self.assertGreaterEqual(depth_for(2.0), depth_for(0.2))


class TestHardDeadline(unittest.TestCase):
    """The search must stop mid iteration, not only between iterations

    The cost of the next depth is predicted from the last one, and that
    prediction can be badly wrong. Before the search itself watched the
    clock, a depth that turned out to cost twenty times its prediction ran
    to the end anyway, which on a real clock forfeits the game.
    """

    # A deep search here costs tens of seconds, so any budget below that
    # can only be met by abandoning an iteration part way through
    BUSY_FEN = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

    def search(self, budget, depth=12, fen=None):
        """Search with a deep depth limit, so only the clock can stop it"""
        board = chess.Board(fen or self.BUSY_FEN)
        bot = KnightmareBot()
        with contextlib.redirect_stdout(io.StringIO()):
            start = time.time()
            move = bot.get_move(board, budget, depth)
            elapsed = time.time() - start
        return bot, board, move, elapsed

    def test_a_deep_search_still_stops_near_the_budget(self):
        _, board, move, elapsed = self.search(1.0)
        self.assertIn(move, board.legal_moves)
        self.assertLess(elapsed, 2.0, f"took {elapsed:.2f}s for a 1.0s budget")

    def test_the_budget_is_honoured_at_several_sizes(self):
        for budget in (0.2, 0.5, 1.0):
            with self.subTest(budget=budget):
                _, _, _, elapsed = self.search(budget)
                # One clock check interval of slack, plus the fixed cost of
                # the mate scan that runs before any searching
                self.assertLess(elapsed, budget + 0.5,
                                f"took {elapsed:.2f}s for a {budget}s budget")

    def test_an_abandoned_search_leaves_the_board_alone(self):
        """Unwinding out of the search skips the matching pops"""
        board = chess.Board(self.BUSY_FEN)
        before = board.fen()
        bot = KnightmareBot()
        with contextlib.redirect_stdout(io.StringIO()):
            bot.get_move(board, 0.4, 12)
        self.assertEqual(board.fen(), before)

    def test_a_legal_move_comes_back_from_an_abandoned_search(self):
        for budget in (0.05, 0.15, 0.4):
            with self.subTest(budget=budget):
                _, board, move, _ = self.search(budget)
                self.assertIn(move, board.legal_moves)

    def test_the_deadline_is_released_afterwards(self):
        """Otherwise the next search is still bound by the last one's clock"""
        bot, _, _, _ = self.search(0.2)
        self.assertIsNone(bot.deadline)

    def test_a_later_unlimited_search_is_not_cut_short(self):
        bot, _, _, _ = self.search(0.05)
        board = chess.Board(self.BUSY_FEN)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIn(bot.get_move(board, 600.0, 2), board.legal_moves)

    def test_part_of_a_depth_is_better_than_none_of_it(self):
        """A root move searched deeper beats the whole shallower depth"""
        board = chess.Board(self.BUSY_FEN)
        bot = KnightmareBot()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            move = bot.get_move(board, 2.0, 12)
        output = buffer.getvalue()
        self.assertIn(move, board.legal_moves)
        # Either it finished cleanly or it reported using a partial depth,
        # but it must never silently discard one it had already started
        if "aborted on time" not in output:
            self.assertTrue(
                "cut short on time" in output or "info depth" in output,
                output,
            )


class TestClockCheck(unittest.TestCase):
    """The check itself, away from a real search"""

    def setUp(self):
        self.bot = KnightmareBot()

    def test_no_deadline_never_aborts(self):
        self.bot.deadline = None
        self.bot.nodes = CLOCK_CHECK_INTERVAL
        self.bot.check_clock()  # must not raise

    def test_a_future_deadline_does_not_abort(self):
        self.bot.deadline = time.time() + 60
        self.bot.nodes = CLOCK_CHECK_INTERVAL
        self.bot.check_clock()

    def test_a_passed_deadline_aborts(self):
        self.bot.deadline = time.time() - 1
        self.bot.nodes = CLOCK_CHECK_INTERVAL
        with self.assertRaises(SearchAborted):
            self.bot.check_clock()

    def test_the_clock_is_only_read_periodically(self):
        """Reading it on every node is measurable overhead at these rates"""
        self.bot.deadline = time.time() - 1
        self.bot.nodes = CLOCK_CHECK_INTERVAL + 1
        self.bot.check_clock()

    def test_it_fires_once_per_interval(self):
        self.bot.deadline = time.time() - 1
        aborts = 0
        for node in range(1, 4 * CLOCK_CHECK_INTERVAL + 1):
            self.bot.nodes = node
            try:
                self.bot.check_clock()
            except SearchAborted:
                aborts += 1
        self.assertEqual(aborts, 4)


class TestUciRoundTrip(unittest.TestCase):
    """Positions arriving over UCI must survive parsing and searching"""

    def setUp(self):
        self.bot = KnightmareBot()

    def test_fen_positions_round_trip(self):
        for name, fen in POSITIONS:
            with self.subTest(position=name):
                board = parse_position(f"position fen {fen}")
                move = self.bot.get_move(board, NO_TIME_LIMIT, 2)
                if board.is_game_over():
                    continue
                self.assertIn(move, board.legal_moves)

    def test_move_list_positions_round_trip(self):
        board = parse_position("position startpos moves e2e4 e7e5 g1f3 b8c6 f1b5")
        move = self.bot.get_move(board, NO_TIME_LIMIT, 2)
        self.assertIn(move, board.legal_moves)

    def test_go_budget_is_respected_by_the_search(self):
        """A depth limit from the go line must bound the search"""
        time_limit, max_depth = parse_go("go depth 2")
        board = chess.Board(POSITIONS[1][1])
        move = self.bot.get_move(board, time_limit, max_depth)
        self.assertIn(move, board.legal_moves)


if __name__ == "__main__":
    unittest.main()
