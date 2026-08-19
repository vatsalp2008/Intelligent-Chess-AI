#!/usr/bin/env python3
"""
Diagnostic script to find why Knightmare keeps repeating moves
"""

import chess
import queue
import subprocess
import threading
import time


def start_reader(proc):
    """Pump the engine's output into a queue on a background thread

    readline() blocks until a newline arrives, so an engine that is running
    but silent would hang this script indefinitely. Reading on a separate
    thread lets the caller apply a real timeout.
    """
    lines = queue.Queue()

    def pump():
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)  # sentinel: the engine closed its output

    threading.Thread(target=pump, daemon=True).start()
    return lines


def read_line(lines, deadline):
    """One line of output, or None on timeout or end of file"""
    remaining = deadline - time.time()
    if remaining <= 0:
        return None
    try:
        return lines.get(timeout=remaining)
    except queue.Empty:
        return None


def wait_for(lines, token, timeout=5):
    """Read until token appears, giving up on EOF or timeout"""
    deadline = time.time() + timeout

    while True:
        line = read_line(lines, deadline)
        if line is None:
            return None
        if token in line:
            return line


def test_position(bot_path, fen):
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
    
    lines = start_reader(proc)

    # Initialize
    proc.stdin.write("uci\n")
    proc.stdin.flush()

    # Wait for uciok
    if wait_for(lines, "uciok") is None:
        print("  ✗ Engine never answered 'uci' - is it crashing on startup?")
        proc.kill()
        return []

    proc.stdin.write("isready\n")
    proc.stdin.flush()
    if wait_for(lines, "readyok") is None:
        print("  ✗ Engine never answered 'isready'")
        proc.kill()
        return []
    
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
        deadline = time.time() + 2
        while True:
            raw = read_line(lines, deadline)
            if raw is None:
                # Timed out or the engine closed its output
                print(f"  ✗ No answer from the engine on attempt {i+1}")
                break
            line = raw.strip()
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
    if not moves:
        print("  ✗ No moves returned at all")
    elif len(set(moves)) == 1:
        print(f"  ⚠️ Bot keeps playing the same move: {moves[0]}")
        
        # Verify it's legal
        board = chess.Board(fen)
        try:
            move_obj = chess.Move.from_uci(moves[0])
            if move_obj in board.legal_moves:
                print(f"  ✓ Move is legal")
            else:
                print(f"  ✗ Move is ILLEGAL!")
        except ValueError:
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
        # Black is a rook down and must find a defence
        ("Down a rook", "6k1/5ppp/8/8/8/8/5PPP/6KR b - - 0 1"),
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