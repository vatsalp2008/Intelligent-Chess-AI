#!/usr/bin/env python3
"""
Play the baseline minimax engine against a saved copy of itself.

This is the same idea as classic_agent/selfplay.py, but for the
KnightmareFast engine used as the strong opponent in the LLM tournament.
Without it there is no way to tell whether a change to that engine helped
or hurt, and its results are what the LLM bots are measured against.

Write out a copy of the engine to compare with, then run a match:

    git show HEAD~1:llm_agent/knightmare.py > /tmp/old.py
    python3 selfplay.py /tmp/old.py --depth 3

Both sides search to the same fixed depth so the result does not depend on
how busy the machine is.
"""

import argparse
import importlib.util
import sys

import chess

# Openings played from both sides so the sample is not one repeated game
OPENINGS = [
    ("start", []),
    ("e4 e5", ["e2e4", "e7e5"]),
    ("d4 d5", ["d2d4", "d7d5"]),
    ("Sicilian", ["e2e4", "c7c5"]),
    ("French", ["e2e4", "e7e6"]),
    ("QGD", ["d2d4", "d7d5", "c2c4", "e7e6"]),
    ("English", ["c2c4", "e7e5"]),
    ("Indian", ["d2d4", "g8f6"]),
]

# Longest game before it is called a draw
MAX_PLIES = 120


def load_engine(path, name):
    """Import an engine module from an arbitrary file path"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Generous budget so the depth limit is what actually stops the search
NO_TIME_LIMIT = 600.0


def ask_move(bot, board, depth):
    """One move from the engine at the fixed depth"""
    return bot.get_best_move(board, NO_TIME_LIMIT, depth)


def play_game(white_bot, black_bot, opening, depth):
    """Play one game and return a PGN style result string"""
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))

    while not board.is_game_over() and len(board.move_stack) < MAX_PLIES:
        bot = white_bot if board.turn == chess.WHITE else black_bot
        move = ask_move(bot, board, depth)

        # Failing to produce a legal move loses the game
        if move is None or move not in board.legal_moves:
            return "0-1" if board.turn == chess.WHITE else "1-0"

        board.push(move)

    if board.is_checkmate():
        return "0-1" if board.turn == chess.WHITE else "1-0"
    return "1/2-1/2"


def run_match(new_module, old_module, depth, verbose=True):
    """Play every opening from both sides, returning (new_score, games)"""
    new_score = 0.0
    games = 0

    for name, opening in OPENINGS:
        for new_is_white in (True, False):
            games += 1
            new_bot = new_module.KnightmareFast()
            old_bot = old_module.KnightmareFast()

            if new_is_white:
                result = play_game(new_bot, old_bot, opening, depth)
            else:
                result = play_game(old_bot, new_bot, opening, depth)

            if result == "1/2-1/2":
                new_score += 0.5
                outcome = "draw"
            elif (result == "1-0") == new_is_white:
                new_score += 1.0
                outcome = "new wins"
            else:
                outcome = "old wins"

            if verbose:
                colour = "W" if new_is_white else "B"
                print(f"  {name:9} new={colour}  {outcome:9} "
                      f"running {new_score}/{games}", flush=True)

    return new_score, games


def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure the baseline engine against a saved copy of itself"
    )
    parser.add_argument("baseline", help="path to the engine to play against")
    parser.add_argument("--depth", type=int, default=3,
                        help="fixed search depth for both sides (default: 3)")
    parser.add_argument("--quiet", action="store_true", help="only print the final score")
    return parser.parse_args()


def main():
    args = parse_args()

    new_module = load_engine("knightmare.py", "engine_new")
    old_module = load_engine(args.baseline, "engine_old")

    print(f"Current engine vs {args.baseline} at depth {args.depth}")
    print("=" * 60)

    score, games = run_match(new_module, old_module, args.depth,
                             verbose=not args.quiet)

    print("=" * 60)
    percent = 100 * score / games
    print(f"Current engine scored {score} / {games} ({percent:.0f}%)")

    if percent > 55:
        print("The change looks like an improvement.")
    elif percent < 45:
        print("The change looks like a regression.")
    else:
        print("No clear difference from this many games.")


if __name__ == "__main__":
    main()
