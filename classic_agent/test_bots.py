#!/usr/bin/env python3
"""
Test script to verify both bots work correctly
Run this before tournaments to check for issues
"""

import subprocess
import time
import chess

def test_bot(bot_path, test_name):
    """Test a bot with various UCI commands"""
    print(f"\nTesting {test_name}...")
    print("-" * 40)
    
    try:
        # Start the bot process
        proc = subprocess.Popen(
            ['python3', bot_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        def send_command(cmd):
            """Send command and get response"""
            proc.stdin.write(cmd + '\n')
            proc.stdin.flush()
            time.sleep(0.1)
            
            responses = []
            while True:
                try:
                    line = proc.stdout.readline()
                    if line:
                        responses.append(line.strip())
                    else:
                        break
                except:
                    break
            return responses
        
        # Test 1: UCI handshake
        print("Test 1: UCI handshake")
        proc.stdin.write("uci\n")
        proc.stdin.flush()
        time.sleep(0.5)
        
        response = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            response.append(line.strip())
            if "uciok" in line:
                break
        
        if any("uciok" in r for r in response):
            print("✓ UCI handshake successful")
        else:
            print("✗ UCI handshake failed")
            return False
        
        # Test 2: Ready check
        print("Test 2: Ready check")
        proc.stdin.write("isready\n")
        proc.stdin.flush()
        time.sleep(0.5)
        
        line = proc.stdout.readline().strip()
        if "readyok" in line:
            print("✓ Ready check successful")
        else:
            print("✗ Ready check failed")
            return False
        
        # Test 3: New game
        print("Test 3: New game")
        proc.stdin.write("ucinewgame\n")
        proc.stdin.flush()
        time.sleep(0.1)
        print("✓ New game command sent")
        
        # Test 4: Starting position
        print("Test 4: Starting position")
        proc.stdin.write("position startpos\n")
        proc.stdin.flush()
        time.sleep(0.1)
        
        proc.stdin.write("go movetime 100\n")
        proc.stdin.flush()
        time.sleep(0.3)
        
        response = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            response.append(line.strip())
            if "bestmove" in line:
                break
        
        bestmove_line = next((r for r in response if r.startswith("bestmove")), None)
        if bestmove_line:
            move_uci = bestmove_line.split()[1]
            try:
                board = chess.Board()
                move = chess.Move.from_uci(move_uci)
                if move in board.legal_moves:
                    print(f"✓ Valid move from starting position: {move_uci}")
                else:
                    print(f"✗ Invalid move: {move_uci}")
                    return False
            except:
                print(f"✗ Invalid UCI format: {move_uci}")
                return False
        else:
            print("✗ No bestmove received")
            return False
        
        # Test 5: Position with moves
        print("Test 5: Position with moves")
        proc.stdin.write("position startpos moves e2e4 e7e5\n")
        proc.stdin.flush()
        time.sleep(0.1)
        
        proc.stdin.write("go movetime 100\n")
        proc.stdin.flush()
        time.sleep(0.3)
        
        response = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            response.append(line.strip())
            if "bestmove" in line:
                break
        
        bestmove_line = next((r for r in response if r.startswith("bestmove")), None)
        if bestmove_line:
            move_uci = bestmove_line.split()[1]
            try:
                board = chess.Board()
                board.push(chess.Move.from_uci("e2e4"))
                board.push(chess.Move.from_uci("e7e5"))
                move = chess.Move.from_uci(move_uci)
                if move in board.legal_moves:
                    print(f"✓ Valid move after e4 e5: {move_uci}")
                else:
                    print(f"✗ Invalid move after e4 e5: {move_uci}")
                    return False
            except:
                print(f"✗ Invalid UCI format: {move_uci}")
                return False
        else:
            print("✗ No bestmove received")
            return False
        
        # Test 6: FEN position
        print("Test 6: FEN position")
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        proc.stdin.write(f"position fen {fen}\n")
        proc.stdin.flush()
        time.sleep(0.1)
        
        proc.stdin.write("go movetime 100\n")
        proc.stdin.flush()
        time.sleep(0.3)
        
        response = []
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            response.append(line.strip())
            if "bestmove" in line:
                break
        
        bestmove_line = next((r for r in response if r.startswith("bestmove")), None)
        if bestmove_line:
            move_uci = bestmove_line.split()[1]
            try:
                board = chess.Board(fen)
                move = chess.Move.from_uci(move_uci)
                if move in board.legal_moves:
                    print(f"✓ Valid move from FEN: {move_uci}")
                else:
                    print(f"✗ Invalid move from FEN: {move_uci}")
                    return False
            except:
                print(f"✗ Invalid UCI format: {move_uci}")
                return False
        else:
            print("✗ No bestmove received")
            return False
        
        # Clean shutdown
        print("Test 7: Clean shutdown")
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        time.sleep(0.5)
        
        proc.terminate()
        proc.wait(timeout=2)
        print("✓ Clean shutdown")
        
        print(f"\n✅ All tests passed for {test_name}!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing {test_name}: {e}")
        try:
            proc.terminate()
        except:
            pass
        return False

def main():
    print("=" * 50)
    print("Chess Bot UCI Protocol Tester")
    print("=" * 50)
    
    # Test both bots
    knightmare_ok = test_bot("knightmare_bot.py", "Knightmare Bot")
    random_ok = test_bot("random_chess_bot.py", "Random Bot")
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    if knightmare_ok:
        print("✅ Knightmare Bot: PASSED")
    else:
        print("❌ Knightmare Bot: FAILED")
    
    if random_ok:
        print("✅ Random Bot: PASSED")
    else:
        print("❌ Random Bot: FAILED")
    
    if knightmare_ok and random_ok:
        print("\n🎉 Both bots are ready for tournament play!")
    else:
        print("\n⚠️ Fix the failing bot(s) before running tournaments")

if __name__ == "__main__":
    main()