#!/usr/bin/env python3
"""
Play the current engine against another copy of itself to measure whether
a change actually helps.

Point it at a saved copy of the engine (for example one written out with
`git show HEAD~1:classic_agent/knightmare_bot.py > old_bot.py`) and it
plays a match, alternating colours from a spread of standard openings.

Searches run to a fixed depth by default, so results are reproducible
instead of depending on how busy the machine is.

Use --seconds when the change was about speed rather than about what the
search returns. Better move ordering, for instance, cannot change the
result of a fixed-depth search at all; it only shows up when the clock is
what stops the search. Timed matches are slow and less reproducible, so
prefer fixed depth unless speed is the thing being measured.

    python3 selfplay.py old_bot.py
    python3 selfplay.py old_bot.py --depth 4
    python3 selfplay.py old_bot.py --seconds 0.5
    python3 selfplay.py old_bot.py --quiet
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
    ("Caro-Kann", ["e2e4", "c7c6"]),
    ("QGD", ["d2d4", "d7d5", "c2c4", "e7e6"]),
    ("Indian", ["d2d4", "g8f6", "c2c4", "e7e6"]),
    ("English", ["c2c4", "e7e5"]),
    ("Ruy Lopez", ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]),
    ("Italian", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]),
    ("Scandinavian", ["e2e4", "d7d5"]),
]

# Generous ceiling so the depth limit is what actually stops the search
NO_TIME_LIMIT = 600.0

# Depth ceiling when the clock is what should stop the search
MAX_DEPTH_WHEN_TIMED = 6


def load_engine(path, name):
    """Import an engine module from an arbitrary file path"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def disable_book(bot):
    """Turn off a bot's opening book if it has one

    The book picks between replies at random, so leaving it on makes a
    measurement irreproducible: an engine played against an identical copy
    of itself scored 54%, 54% and 50% over the same twelve games. It also
    means the first few moves of every game test the book rather than the
    search, which is the thing being measured.
    """
    if hasattr(bot, "use_book"):
        bot.use_book = False


def game_finished(board):
    """True when the game is over, counting the draws a player may claim

    is_game_over() alone says False for the fifty move rule and threefold
    repetition, so a game that reached one carried on being played. Three
    of five sampled self play games hit a claimable draw and then went on
    to end in checkmate, which the harness recorded as a decisive result
    for a game that was in fact drawn.

    Checked directly rather than through is_game_over(claim_draw=True),
    which is true one ply early: that asks can_claim_fifty_moves(), which
    reports that the side to move *could* reach the rule with their move.
    """
    if board.is_game_over():
        return True
    return board.halfmove_clock >= 100 or board.is_repetition(3)


def play_game(white_bot, black_bot, opening, depth, seconds=None, max_plies=160):
    """Play one game and return a PGN style result string

    With seconds set, both sides get that long per move and depth becomes
    only a ceiling. That is the regime where faster search turns into
    better play; at a fixed depth a speedup changes nothing.
    """
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))

    while not game_finished(board) and len(board.move_stack) < max_plies:
        bot = white_bot if board.turn == chess.WHITE else black_bot
        if seconds is None:
            move = bot.get_move(board, NO_TIME_LIMIT, depth)
        else:
            move = bot.get_move(board, seconds, MAX_DEPTH_WHEN_TIMED)

        # Failing to produce a legal move loses the game
        if move is None or move not in board.legal_moves:
            return "0-1" if board.turn == chess.WHITE else "1-0"

        board.push(move)

    if board.is_checkmate():
        return "0-1" if board.turn == chess.WHITE else "1-0"
    return "1/2-1/2"


def run_match(new_module, old_module, depth, seconds=None, verbose=True,
              max_games=None, use_book=False):
    """Play openings from both sides, returning (new_score, games)

    max_games stops early, which is useful when a full match is too slow to
    sit through. Colours still alternate, so an odd limit leaves one opening
    played from one side only.

    The books are off by default, so that a fixed depth match is
    reproducible and measures the search rather than the book.
    """
    new_score = 0.0
    games = 0

    for name, opening in OPENINGS:
        for new_is_white in (True, False):
            if max_games is not None and games >= max_games:
                return new_score, games
            games += 1
            new_bot = new_module.KnightmareBot()
            old_bot = old_module.KnightmareBot()
            if not use_book:
                disable_book(new_bot)
                disable_book(old_bot)

            if new_is_white:
                result = play_game(new_bot, old_bot, opening, depth, seconds)
            else:
                result = play_game(old_bot, new_bot, opening, depth, seconds)

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
                print(f"  {name:13} new={colour}  {outcome:9} "
                      f"running {new_score}/{games}", flush=True)

    return new_score, games


def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure the current engine against a saved copy of itself"
    )
    parser.add_argument("baseline", help="path to the engine to play against")
    parser.add_argument("--depth", type=int, default=3,
                        help="fixed search depth for both sides (default: 3)")
    parser.add_argument("--seconds", type=float, default=None, metavar="S",
                        help="give each side S seconds per move instead of a fixed depth")
    parser.add_argument("--games", type=int, default=None, metavar="N",
                        help="stop after N games instead of playing them all")
    parser.add_argument("--quiet", action="store_true", help="only print the final score")
    parser.add_argument("--book", action="store_true",
                        help="leave the opening books on (results stop being reproducible)")
    return parser.parse_args()


def main():
    args = parse_args()

    new_module = load_engine("knightmare_bot.py", "engine_new")
    old_module = load_engine(args.baseline, "engine_old")

    if args.seconds is None:
        setting = f"depth {args.depth}"
    else:
        setting = f"{args.seconds}s per move"
    book = "book on" if args.book else "book off"
    print(f"Current engine vs {args.baseline} at {setting}, {book}")
    print("=" * 60)

    score, games = run_match(new_module, old_module, args.depth,
                             seconds=args.seconds, verbose=not args.quiet,
                             max_games=args.games, use_book=args.book)

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
