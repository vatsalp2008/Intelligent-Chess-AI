#!/usr/bin/env python3
"""
Play the baseline minimax engine against Stockfish for a strength figure
that does not depend on our own evaluation being right.

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

This is the engine the LLM bots are measured against in the tournament,
so knowing roughly how strong it is puts those results in context.

Reference point, this engine at depth 3 over 6 games:

    Stockfish depth 2   17%

The classic_agent engine scores about 46% on the same rung, so this one is
clearly the weaker of the two despite sharing much of its evaluation.
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


def play_game(bot, engine, opening, our_colour, skill_depth):
    """One game; returns 1.0, 0.5 or 0.0 from our engine's point of view"""
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))

    while not board.is_game_over() and len(board.move_stack) < MAX_PLIES:
        if board.turn == our_colour:
            move = bot.get_best_move(board, NO_TIME_LIMIT, OUR_DEPTH)
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


def run_match(bot_factory, engine, level, skill_depth, games, verbose=True):
    """Play a match at one skill level, returning (score, games_played)"""
    engine.configure({"Skill Level": level})

    score = 0.0
    played = 0

    for name, opening in OPENINGS:
        for our_colour in (chess.WHITE, chess.BLACK):
            if played >= games:
                break
            played += 1

            result = play_game(bot_factory(), engine, opening, our_colour, skill_depth)
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
        description="Measure the baseline engine against Stockfish"
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
    return parser.parse_args()


def main():
    args = parse_args()

    path = find_stockfish()
    if path is None:
        print("Stockfish not found. Install it or set STOCKFISH_PATH.")
        return 1

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from knightmare import KnightmareFast

    print(f"Baseline engine (depth {OUR_DEPTH}) vs Stockfish at {path}")
    print("=" * 62)

    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        if args.ladder:
            for skill_depth in (1, 2, 3, 4):
                score, played = run_match(
                    KnightmareFast, engine, args.level, skill_depth,
                    args.games, verbose=not args.quiet,
                )
                pct = 100 * score / played
                print(f"Stockfish level {args.level} depth {skill_depth}: "
                      f"scored {score}/{played} ({pct:.0f}%)")
                print("-" * 62)
        else:
            score, played = run_match(
                KnightmareFast, engine, args.level, args.skill_depth,
                args.games, verbose=not args.quiet,
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
