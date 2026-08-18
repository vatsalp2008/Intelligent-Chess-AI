#!/usr/bin/env python3
"""
Shared helpers for the web interfaces to load and drive the engine.

Both Flask apps used to carry identical copies of this: find whatever
Knightmare class lives in knightmare_bot.py, then work out which method to
call on it. Keeping one copy means a change to the engine's interface only
has to be handled in one place.
"""

import contextlib
import io
import os
import random
import re
import sys

import chess

# The engine reports progress on UCI info lines. Pulling the last one out
# lets the web interfaces show what the engine thought, instead of that
# detail only reaching the server's own log.
INFO_LINE = re.compile(
    r"info depth (?P<depth>\d+) score (?P<score>cp -?\d+|mate -?\d+)"
    r".*?(?: pv (?P<pv>.*))?$"
)

# Fall back to this if the engine cannot be loaded at all
FALLBACK_NOTE = "engine unavailable, playing randomly"


def load_bot_class(module_name="knightmare_bot"):
    """Return the engine class from the given module, or None

    The class is found by name rather than imported directly so that
    renaming it in the engine does not break the web interfaces.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    try:
        module = __import__(module_name)
    except ImportError as exc:
        print(f"Warning: could not import {module_name}.py: {exc}")
        return None

    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and "Knightmare" in name:
            return obj

    print(f"Warning: no Knightmare class found in {module_name}.py")
    return None


def random_move(board):
    """Any legal move, used when the engine is missing or fails"""
    moves = list(board.legal_moves)
    return random.choice(moves) if moves else None


def parse_info(text):
    """The deepest info line in some engine output, as a dict

    Returns None when the output carries no usable info line, which is the
    case for the random bot and for a book move.
    """
    best = None
    for line in text.splitlines():
        match = INFO_LINE.match(line.strip())
        if match is None:
            continue
        found = match.groupdict()
        depth = int(found["depth"])
        if best is None or depth >= best["depth"]:
            best = {
                "depth": depth,
                "score": found["score"],
                "pv": (found["pv"] or "").strip(),
            }
    return best


def ask_engine(bot, board, seconds=1.0):
    """Ask the engine for a move, returning (move, info)

    info is whatever the engine reported about its search, or None. The
    engine writes those lines to stdout as any UCI engine would, so they
    are captured rather than intercepted.
    """
    if bot is None:
        return random_move(board), None

    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            if hasattr(bot, "get_move"):
                move = bot.get_move(board.copy(), seconds)
            elif hasattr(bot, "get_best_move"):
                move = bot.get_best_move(board.copy(), seconds)
            elif hasattr(bot, "minimax"):
                _, move = bot.minimax(
                    board.copy(), 3, -float("inf"), float("inf"),
                    board.turn == chess.WHITE,
                )
            else:
                return random_move(board), None
    except Exception as exc:
        print(f"Error getting engine move: {exc}")
        return random_move(board), None
    finally:
        # Still surface the engine's own output on the server log
        text = captured.getvalue()
        if text:
            sys.stdout.write(text)

    # Never hand back something the caller cannot play
    if move is None or move not in board.legal_moves:
        return random_move(board), None

    return move, parse_info(text)


def best_move(bot, board, seconds=1.0):
    """Ask the engine for a move, falling back to a random legal one"""
    move, _ = ask_engine(bot, board, seconds)
    return move
