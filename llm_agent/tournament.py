from chester.timecontrol import TimeControl
from chester.tournament import play_tournament

# Tournament setup
players = [
    "./knightmare_llm.py",
    "./knightmare.py",
    "./random_chess_bot.py",
    "./mate_in_one.py"
]

time_control = TimeControl(initial_time=10, increment=0)
n_games = 4

# Points awarded to (white, black) for each PGN result header
RESULT_POINTS = {
    "1-0": (1.0, 0.0),
    "0-1": (0.0, 1.0),
    "1/2-1/2": (0.5, 0.5),
}

scores = {}
game_count = {}

print("="*60)
print("FINAL TOURNAMENT")
print("="*60)
print()

for pgn in play_tournament(players, time_control, n_games=n_games, repeat=True):
    print(pgn, "\n")
    
    white = pgn.headers["White"]
    black = pgn.headers["Black"]
    result = pgn.headers["Result"]

    scores.setdefault(white, 0)
    scores.setdefault(black, 0)
    game_count.setdefault(white, 0)
    game_count.setdefault(black, 0)

    if result not in RESULT_POINTS:
        # Unfinished or aborted game ("*"): does not count toward scores
        print(f"Skipping unfinished game: {white} vs {black} ({result})")
        continue

    game_count[white] += 1
    game_count[black] += 1

    white_points, black_points = RESULT_POINTS[result]
    scores[white] += white_points
    scores[black] += black_points

print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"\n{'Bot':<40} {'Score':<10} {'Games':<10} {'Win %'}")
print("-"*60)

for bot in sorted(scores.keys(), key=lambda x: scores[x], reverse=True):
    score = scores[bot]
    games = game_count[bot]
    win_pct = (score / games * 100) if games > 0 else 0
    print(f"{bot:<40} {score:<10.1f} {games:<10} {win_pct:.1f}%")

print("="*60)