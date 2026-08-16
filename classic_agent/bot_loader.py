#!/usr/bin/env python3
"""
Shared helpers for the web interfaces to load and drive the engine.

Both Flask apps used to carry identical copies of this: find whatever
Knightmare class lives in knightmare_bot.py, then work out which method to
call on it. Keeping one copy means a change to the engine's interface only
has to be handled in one place.
"""

import os
import random
import sys

import chess

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


def best_move(bot, board, seconds=1.0):
    """Ask the engine for a move, falling back to a random legal one

    Different versions of the engine have exposed different entry points,
    so the usable one is discovered rather than assumed. The board is
    copied because callers hold the real game state.
    """
    if bot is None:
        return random_move(board)

    try:
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
            return random_move(board)
    except Exception as exc:
        print(f"Error getting engine move: {exc}")
        return random_move(board)

    # Never hand back something the caller cannot play
    if move is None or move not in board.legal_moves:
        return random_move(board)

    return move
