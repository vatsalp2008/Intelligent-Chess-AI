#!/usr/bin/env python3
"""
Tournament runner for Mac/Linux
Uses Python scripts directly instead of .exe files
With better control over number of games
"""

from chester.timecontrol import TimeControl
from chester.tournament import play_tournament
import os
import sys

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# For Mac/Linux, use the executable scripts directly
# Since we made them executable with chmod +x, we can run them directly
players = [
    "./knightmare_bot.py",
    "./random_chess_bot.py"
]

# Verify the files exist and are executable
for player in players:
    if not os.path.exists(player.replace("./", "")):
        print(f"Error: {player} not found!")
        sys.exit(1)
    
print(f"Using players: {players}")

# Specify time and increment, both in seconds.
time_control = TimeControl(initial_time=10, increment=0)

# EXACT number of games you want to play
max_games = 10  # Change this to control exact number of games

# Tabulate scores at the end
scores = {}

print("=" * 60)
print("CS5100 Chess Tournament")
print("=" * 60)
print(f"Players: Knightmare Bot vs Random Bot")
print(f"Time Control: {time_control.initial_time}+{time_control.increment}")
print(f"Maximum games: {max_games}")
print("=" * 60)
print("\nStarting tournament...\n")

try:
    game_count = 0
    
    # Create tournament generator
    tournament = play_tournament(
        players,
        time_control,
        n_games=max_games * 2,  # Set higher to ensure we have enough
        repeat=False,  # Don't repeat with reversed colors
    )
    
    for pgn in tournament:
        game_count += 1
        
        # STOP after reaching our limit
        if game_count > max_games:
            print(f"\nReached game limit of {max_games} games.")
            break
        
        # Printing out the game result
        pgn.headers["Event"] = "CS5100 Tournament"
        pgn.headers["Site"] = "Mac Computer"
        
        # Show game progress
        white = pgn.headers["White"]
        black = pgn.headers["Black"]
        result = pgn.headers["Result"]
        
        # Simplify player names for display
        white_name = "Knightmare" if "knightmare" in white.lower() else "Random"
        black_name = "Knightmare" if "knightmare" in black.lower() else "Random"
        
        print(f"Game {game_count}/{max_games}: {white_name} vs {black_name} - Result: {result}")
        
        # Update scores
        scores.setdefault(white_name, 0)
        scores.setdefault(black_name, 0)
        
        results = result.split('-')
        if results[0] == '1':
            scores[white_name] += 1
        elif results[0] == '1/2':
            scores[white_name] += 0.5
            scores[black_name] += 0.5
        elif results[1] == '1':
            scores[black_name] += 1
            
except KeyboardInterrupt:
    print("\n\nTournament interrupted by user.")
    print(f"Completed {game_count} games before interruption.")
    
except Exception as e:
    print(f"\nError during tournament: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure both bot files exist: knightmare_bot.py and random_chess_bot.py")
    print("2. Make sure both bots are executable: chmod +x knightmare_bot.py random_chess_bot.py")
    print("3. Check that both bots implement the UCI protocol correctly")
    
print("\n" + "=" * 60)
print("FINAL SCORES")
print("=" * 60)

total_games_played = min(game_count, max_games)

for (bot, score) in sorted(scores.items(), key=lambda x: x[1], reverse=True):
    win_percentage = (score / total_games_played) * 100 if total_games_played > 0 else 0
    print(f"{bot:15} : {score:5.1f} points ({win_percentage:.1f}%)")

print("=" * 60)

# Determine winner
if len(scores) == 2:
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if sorted_scores[0][1] > sorted_scores[1][1]:
        print(f"\n🏆 {sorted_scores[0][0]} WINS THE TOURNAMENT! 🏆")
    elif sorted_scores[0][1] == sorted_scores[1][1]:
        print("\n🤝 The tournament ended in a DRAW! 🤝")

print(f"\nTotal games played: {total_games_played}")
print()