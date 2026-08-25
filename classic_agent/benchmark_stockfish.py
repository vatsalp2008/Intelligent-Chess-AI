#!/usr/bin/env python3
"""
Play Knightmare against Stockfish to get a strength figure that does not
depend on our own evaluation being right.

Self play only says whether a change beat the previous version; it cannot
say how strong the engine actually is, because both sides share the same
blind spots. Stockfish is an independent opponent, and its Skill Level
option gives a ladder to find roughly where we sit.

Stockfish is held to a small fixed depth, because even its weakest setting
at full depth is far beyond this engine. Prefer limiting depth at Skill
Level 20 over lowering the skill level: low skill levels work by playing
deliberately random moves, which adds noise and makes the ladder jump
around rather than getting steadily harder.

    python3 benchmark_stockfish.py --skill-depth 2 --games 6
    python3 benchmark_stockfish.py --ladder

Results are noisy: six games per rung produced 42/42/25 on one run and
58/25/50 on another, which is mostly sampling noise rather than a real
difference. Use the full opening set, and treat a single rung as a rough
band rather than a precise number.

Part of that noise was our own opening book, which picks between replies at
random: the same engine played against an identical copy of itself scored
54%, 54% and 50% with the book on, and exactly 50% with it off. Our book is
off by default here for the same reason, so the reference below is not
directly comparable to a run with --book.

Reference point, Knightmare at depth 3 over the full 12 game set. Measured
with the book on, so it carries several points of that noise:

    Stockfish depth 2   46%
"""

import argparse
import os
import shutil
import sys

import chess
import chess.engine

# Openings played from both sides so results are not one repeated game
OPENINGS = [
    ("start", []),
    ("e4 e5", ["e2e4", "e7e5"]),
    ("d4 d5", ["d2d4", "d7d5"]),
    ("Sicilian", ["e2e4", "c7c5"]),
    ("French", ["e2e4", "e7e6"]),
    ("QGD", ["d2d4", "d7d5", "c2c4", "e7e6"]),
]

# Our own search settings while benchmarking
OUR_DEPTH = 3
NO_TIME_LIMIT = 600.0

# Longest game before it is called a draw
MAX_PLIES = 160


def find_stockfish():
    """Locate the Stockfish binary, or return None"""
    configured = os.environ.get("STOCKFISH_PATH")
    if configured and os.path.isfile(configured):
        return configured

    found = shutil.which("stockfish")
    if found:
        return found

    for path in ("/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish",
                 "/usr/bin/stockfish", "/usr/games/stockfish"):
        if os.path.isfile(path):
            return path

    return None


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


def play_game(bot, engine, opening, our_colour, skill_depth):
    """One game; returns 1.0, 0.5 or 0.0 from our engine's point of view"""
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))

    while not game_finished(board) and len(board.move_stack) < MAX_PLIES:
        if board.turn == our_colour:
            move = bot.get_move(board, NO_TIME_LIMIT, OUR_DEPTH)
            if move is None or move not in board.legal_moves:
                return 0.0  # failing to move loses
        else:
            result = engine.play(board, chess.engine.Limit(depth=skill_depth))
            move = result.move
            if move is None:
                return 1.0

        board.push(move)

    if board.is_checkmate():
        # The side to move has been mated
        return 0.0 if board.turn == our_colour else 1.0
    return 0.5


def make_bot(bot_factory, use_book):
    """An engine for one game, with its book set as asked

    The book picks between replies at random, so leaving it on costs the
    result several points of noise that have nothing to do with the engine's
    strength, and spends the first five full moves of every game on book
    moves rather than searched ones.
    """
    bot = bot_factory()
    # Older engines have no such setting to turn off
    if not use_book and hasattr(bot, "use_book"):
        bot.use_book = False
    return bot


def run_match(bot_factory, engine, level, skill_depth, games, verbose=True,
              use_book=False):
    """Play a match at one skill level, returning (score, games_played)"""
    engine.configure({"Skill Level": level})

    score = 0.0
    played = 0

    for name, opening in OPENINGS:
        for our_colour in (chess.WHITE, chess.BLACK):
            if played >= games:
                break
            played += 1

            result = play_game(make_bot(bot_factory, use_book), engine,
                               opening, our_colour, skill_depth)
            score += result

            if verbose:
                outcome = {1.0: "win", 0.5: "draw", 0.0: "loss"}[result]
                colour = "W" if our_colour == chess.WHITE else "B"
                print(f"  {name:9} as {colour}: {outcome:4}  running {score}/{played}",
                      flush=True)
        if played >= games:
            break

    return score, played


def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure Knightmare against Stockfish"
    )
    parser.add_argument("--level", type=int, default=20,
                        help="Stockfish Skill Level 0-20 (default: 20, full strength)")
    parser.add_argument("--skill-depth", type=int, default=2,
                        help="depth limit for Stockfish (default: 2)")
    parser.add_argument("--games", type=int, default=2 * len(OPENINGS),
                        help=f"games to play (default: {2 * len(OPENINGS)}, the full set)")
    parser.add_argument("--ladder", action="store_true",
                        help="sweep several skill depths to find where we break even")
    parser.add_argument("--quiet", action="store_true", help="only print totals")
    parser.add_argument("--book", action="store_true",
                        help="leave our opening book on (adds noise to the result)")
    return parser.parse_args()


def main():
    args = parse_args()

    path = find_stockfish()
    if path is None:
        print("Stockfish not found. Install it or set STOCKFISH_PATH.")
        return 1

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from knightmare_bot import KnightmareBot

    print(f"Knightmare (depth {OUR_DEPTH}) vs Stockfish at {path}")
    print("=" * 62)

    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        if args.ladder:
            for skill_depth in (1, 2, 3, 4):
                score, played = run_match(
                    KnightmareBot, engine, args.level, skill_depth,
                    args.games, verbose=not args.quiet, use_book=args.book,
                )
                pct = 100 * score / played
                print(f"Stockfish level {args.level} depth {skill_depth}: "
                      f"scored {score}/{played} ({pct:.0f}%)")
                print("-" * 62)
        else:
            score, played = run_match(
                KnightmareBot, engine, args.level, args.skill_depth,
                args.games, verbose=not args.quiet, use_book=args.book,
            )
            print("=" * 62)
            pct = 100 * score / played
            print(f"Scored {score} / {played} ({pct:.0f}%) against "
                  f"Stockfish level {args.level} depth {args.skill_depth}")
    finally:
        engine.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())
