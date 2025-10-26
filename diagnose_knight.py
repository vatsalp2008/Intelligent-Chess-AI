#!/usr/bin/env python3
"""
Diagnostic script to find why Knightmare keeps repeating moves
"""

import chess
import subprocess
import time

def test_position(bot_path, fen, expected_different=True):
    """Test if bot gives different moves for a position"""
    print(f"\nTesting position: {fen}")
    
    proc = subprocess.Popen(
        ['python3', bot_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0
    )
    
    # Initialize
    proc.stdin.write("uci\n")
    proc.stdin.flush()
    time.sleep(0.5)
    
    # Wait for uciok
    while True:
        line = proc.stdout.readline()
        if "uciok" in line:
            break
    
    proc.stdin.write("isready\n")
    proc.stdin.flush()
    time.sleep(0.5)
    proc.stdout.readline()  # readyok
    
    # Test the position multiple times
    moves = []
    for i in range(3):
        proc.stdin.write("ucinewgame\n")
        proc.stdin.flush()
        time.sleep(0.1)
        
        proc.stdin.write(f"position fen {fen}\n")
        proc.stdin.flush()
        time.sleep(0.1)
        
        proc.stdin.write("go movetime 500\n")
        proc.stdin.flush()
        
        # Get response
        start = time.time()
        while time.time() - start < 2:
            line = proc.stdout.readline().strip()
            if line.startswith("info"):
                print(f"  {line}")
            elif line.startswith("bestmove"):
                move = line.split()[1]
                moves.append(move)
                print(f"  Attempt {i+1}: {move}")
                break
    
    proc.stdin.write("quit\n")
    proc.stdin.flush()
    proc.terminate()
    
    # Check if moves are all the same
    if len(set(moves)) == 1:
        print(f"  ⚠️ Bot keeps playing the same move: {moves[0]}")
        
        # Verify it's legal
        board = chess.Board(fen)
        try:
            move_obj = chess.Move.from_uci(moves[0])
            if move_obj in board.legal_moves:
                print(f"  ✓ Move is legal")
            else:
                print(f"  ✗ Move is ILLEGAL!")
        except:
            print(f"  ✗ Invalid move format!")
    else:
        print(f"  ✓ Bot gives different moves: {moves}")
    
    return moves

def main():
    print("=" * 60)
    print("Knightmare Diagnostic")
    print("=" * 60)
    
    # Test different positions
    positions = [
        ("Starting position", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
        ("After 1.e4", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"),
        ("Middle game", "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"),
        ("Endgame", "8/5k2/8/3K4/8/8/4P3/8 w - - 0 1"),
        ("Complex position", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
        ("Position with Rook", "6k1/5ppp/8/8/8/8/5PPP/6KR b - - 0 1"),  # Black has Rook on g8
    ]
    
    for name, fen in positions:
        print(f"\n{name}:")
        test_position("knightmare_bot.py", fen)
    
    # Also test random bot for comparison
    print("\n\nTesting Random Bot for comparison:")
    print("-" * 40)
    for name, fen in positions[:2]:
        print(f"\n{name}:")
        test_position("random_chess_bot.py", fen)

if __name__ == "__main__":
    main()