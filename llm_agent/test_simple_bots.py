#!/usr/bin/env python3
"""
Tests for the two baseline opponents.

Neither had any tests, and both turned out to mishandle the position
command in ways that only show up across games: "position startpos" with no
move list matched nothing, so a new game continued from wherever the last
one ended, and the mate bot pushed every move in the list without checking
it, so one bad move left the board half replayed and the host with no
reply.

They are UCI scripts rather than importable modules, so they are loaded by
path. That also keeps each test's board independent, since both keep their
position in a module level global.

Run with:
    python3 -m unittest test_simple_bots
"""

import contextlib
import importlib.util
import io
import unittest

import chess


def load(path, name):
    """Load a bot script as a fresh module, so its globals are its own"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedBotBehaviour:
    """Shared behaviour both bots have to get right

    A mixin rather than a TestCase subclass, so unittest does not collect
    and then skip a copy of every test for the base class itself.
    """

    PATH = None
    NAME = None

    def setUp(self):
        self.bot = load(self.PATH, self.NAME)

    def send(self, msg):
        """Run one UCI command, returning whatever it printed"""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.bot.uci(msg)
        return buffer.getvalue()

    # --- position handling ---

    def test_startpos_with_no_moves_resets_the_board(self):
        """A new game must not continue from the last one's final position"""
        self.send("position startpos moves e2e4 e7e5 g1f3")
        self.send("position startpos")
        self.assertEqual(self.bot.board.fen(), chess.STARTING_FEN)

    def test_ucinewgame_resets_the_board(self):
        self.send("position startpos moves e2e4 e7e5")
        self.send("ucinewgame")
        self.assertEqual(self.bot.board.fen(), chess.STARTING_FEN)

    def test_a_move_list_is_replayed(self):
        self.send("position startpos moves e2e4 e7e5 g1f3")
        self.assertEqual([m.uci() for m in self.bot.board.move_stack],
                         ["e2e4", "e7e5", "g1f3"])

    def test_a_fen_is_used(self):
        fen = "8/8/4k3/8/8/8/4P3/4K3 w - - 0 1"
        self.send(f"position fen {fen}")
        self.assertEqual(self.bot.board.fen(), fen)

    def test_a_fen_followed_by_moves_uses_both(self):
        """The move list used to be handed to set_fen along with the FEN"""
        self.send("position fen 8/8/4k3/8/8/8/4P3/4K3 w - - 0 1 moves e2e4")
        self.assertEqual(self.bot.board.fen(), "8/8/4k3/8/4P3/8/8/4K3 b - - 0 1")

    def test_an_unreadable_fen_falls_back_to_the_start(self):
        self.send("position fen not-a-fen")
        self.assertEqual(self.bot.board.fen(), chess.STARTING_FEN)

    def test_an_illegal_move_stops_the_replay(self):
        self.send("position startpos moves e2e4 d7d6 d7d5 g1f3")
        self.assertEqual([m.uci() for m in self.bot.board.move_stack],
                         ["e2e4", "d7d6"])

    def test_an_unreadable_move_stops_the_replay(self):
        self.send("position startpos moves e2e4 zzz e7e5")
        self.assertEqual([m.uci() for m in self.bot.board.move_stack], ["e2e4"])

    def test_a_bad_move_is_reported(self):
        self.assertIn("not legal",
                      self.send("position startpos moves e2e4 d7d6 d7d5"))

    # --- the handshake ---

    def test_uci_is_answered(self):
        self.assertIn("uciok", self.send("uci"))

    def test_isready_is_answered(self):
        self.assertIn("readyok", self.send("isready"))

    def test_the_bot_names_itself(self):
        self.assertIn("id name", self.send("uci"))

    # --- moving ---

    def test_go_returns_a_legal_move(self):
        self.send("position startpos")
        reply = self.send("go movetime 100")
        uci = reply.split("bestmove ")[1].split()[0]
        self.assertIn(chess.Move.from_uci(uci), self.bot.board.legal_moves)

    def test_a_finished_game_still_gets_a_reply(self):
        """Sending nothing leaves the host waiting for a move forever"""
        self.send("position fen 4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertIn("bestmove 0000", self.send("go movetime 100"))

    def test_an_unknown_command_is_ignored(self):
        """The protocol says to ignore what you do not understand"""
        self.send("position startpos")
        before = self.bot.board.fen()
        self.send("nonsense command here")
        self.assertEqual(self.bot.board.fen(), before)


class TestRandomBot(SharedBotBehaviour, unittest.TestCase):
    PATH = "random_chess_bot.py"
    NAME = "random_bot_under_test"

    def test_it_plays_a_legal_move_from_any_position(self):
        for fen in ("8/8/4k3/8/8/8/4P3/4K3 w - - 0 1",
                    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"):
            with self.subTest(fen=fen):
                board = chess.Board(fen)
                self.assertIn(self.bot.make_random_move(board), board.legal_moves)

    def test_no_move_in_a_finished_position(self):
        board = chess.Board("4R1k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1")
        self.assertIsNone(self.bot.make_random_move(board))


class TestMateInOneBot(SharedBotBehaviour, unittest.TestCase):
    PATH = "mate_in_one.py"
    NAME = "mate_bot_under_test"

    def test_it_takes_an_available_mate(self):
        """The one thing this bot exists to do"""
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        move = self.bot.make_move(board)
        board.push(move)
        self.assertTrue(board.is_checkmate())

    def test_it_finds_a_mate_with_the_queen_too(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1")
        move = self.bot.make_move(board)
        board.push(move)
        self.assertTrue(board.is_checkmate())

    def test_no_mate_means_a_legal_move_anyway(self):
        board = chess.Board()
        self.assertIn(self.bot.make_move(board), board.legal_moves)

    def test_finding_a_mate_does_not_disturb_the_board(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1")
        before = board.fen()
        self.bot.find_mate_in_one(board)
        self.assertEqual(board.fen(), before)

    def test_no_mate_available_reports_none(self):
        self.assertIsNone(self.bot.find_mate_in_one(chess.Board()))


if __name__ == "__main__":
    unittest.main()
