#!/usr/bin/env python3
"""
Round robin tournament between the LLM bot and the classical baselines.

Every bot speaks UCI, so chester drives them as separate processes. The
LLM bot needs Ollama running; the others do not.

    python3 tournament.py
    python3 tournament.py --games 8
"""

import argparse

try:
    from chester.timecontrol import TimeControl
    from chester.tournament import play_tournament
except ImportError:
    # The scoring helpers are useful (and testable) without chester
    # installed; only run_tournament actually needs it to play games.
    TimeControl = None
    play_tournament = None

# Bots entered in the tournament, each a UCI speaking script
PLAYERS = [
    "./knightmare_llm.py",
    "./knightmare.py",
    "./random_chess_bot.py",
    "./mate_in_one.py",
]

# Points awarded to (white, black) for each PGN result header
RESULT_POINTS = {
    "1-0": (1.0, 0.0),
    "0-1": (0.0, 1.0),
    "1/2-1/2": (0.5, 0.5),
}


def score_game(pgn, scores, game_count):
    """Fold one finished game into the running totals

    Returns True if the game counted. An unfinished game ("*") is skipped
    rather than scored, since neither side earned anything.
    """
    white = pgn.headers["White"]
    black = pgn.headers["Black"]
    result = pgn.headers["Result"]

    scores.setdefault(white, 0)
    scores.setdefault(black, 0)
    game_count.setdefault(white, 0)
    game_count.setdefault(black, 0)

    if result not in RESULT_POINTS:
        print(f"Skipping unfinished game: {white} vs {black} ({result})")
        return False

    game_count[white] += 1
    game_count[black] += 1

    white_points, black_points = RESULT_POINTS[result]
    scores[white] += white_points
    scores[black] += black_points
    return True


def print_table(scores, game_count):
    """Print the final standings, best first"""
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n{'Bot':<40} {'Score':<10} {'Games':<10} {'Win %'}")
    print("-" * 60)

    for bot in sorted(scores, key=lambda name: scores[name], reverse=True):
        score = scores[bot]
        games = game_count[bot]
        win_pct = (score / games * 100) if games > 0 else 0
        print(f"{bot:<40} {score:<10.1f} {games:<10} {win_pct:.1f}%")

    print("=" * 60)


def run_tournament(games, initial_time, verbose=True):
    """Play the round robin and return the score and game count tables"""
    if play_tournament is None:
        raise RuntimeError(
            "chester is not installed; install it with "
            "'pip install -r requirements.txt' to run a tournament"
        )

    time_control = TimeControl(initial_time=initial_time, increment=0)

    scores = {}
    game_count = {}

    print("=" * 60)
    print("FINAL TOURNAMENT")
    print("=" * 60)
    print()

    for pgn in play_tournament(PLAYERS, time_control, n_games=games, repeat=True):
        if verbose:
            print(pgn, "\n")
        score_game(pgn, scores, game_count)

    return scores, game_count


def parse_args():
    parser = argparse.ArgumentParser(description="Run the LLM agent tournament")
    parser.add_argument("--games", type=int, default=4,
                        help="games per pairing (default: 4)")
    parser.add_argument("--time", type=float, default=10.0, metavar="S",
                        help="starting clock per side in seconds (default: 10)")
    parser.add_argument("--quiet", action="store_true",
                        help="skip printing each game's PGN")
    return parser.parse_args()


def main():
    args = parse_args()
    scores, game_count = run_tournament(args.games, args.time, verbose=not args.quiet)
    print_table(scores, game_count)


if __name__ == "__main__":
    main()
