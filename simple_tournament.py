#!/usr/bin/env python3
"""
Simple tournament runner that actually works
No dependency on chester library
"""

import subprocess
import chess
import chess.pgn
import time
import io
from datetime import datetime

class ChessEngine:
    def __init__(self, path, name):
        self.path = path
        self.name = name
        self.process = None
        
    def start(self):
        """Start the engine process"""
        self.process = subprocess.Popen(
            ['python3', self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=0
        )
        
        # Send UCI initialization
        self.send("uci")
        self.wait_for("uciok")
        
        self.send("isready")
        self.wait_for("readyok")
        
    def send(self, command):
        """Send command to engine"""
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()
        
    def wait_for(self, response, timeout=5):
        """Wait for specific response"""
        start = time.time()
        while time.time() - start < timeout:
            line = self.process.stdout.readline().strip()
            if response in line:
                return line
        raise TimeoutError(f"Timeout waiting for {response} from {self.name}")
    
    def get_move(self, board, time_ms=1000):
        """Get a move for the current position"""
        # Send position - FIX: Convert Move objects to UCI strings
        if board.move_stack:
            moves_uci = [move.uci() for move in board.move_stack]
            self.send(f"position startpos moves {' '.join(moves_uci)}")
        else:
            self.send("position startpos")
        
        # Request move
        self.send(f"go movetime {time_ms}")
        
        # Wait for bestmove
        start = time.time()
        while time.time() - start < (time_ms/1000 + 2):
            line = self.process.stdout.readline().strip()
            if line.startswith("bestmove"):
                move_uci = line.split()[1]
                if move_uci == "0000":
                    return None
                try:
                    return chess.Move.from_uci(move_uci)
                except:
                    print(f"Invalid move from {self.name}: {move_uci}")
                    return None
        
        return None
    
    def quit(self):
        """Quit the engine"""
        if self.process:
            self.send("quit")
            time.sleep(0.2)
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except:
                self.process.kill()

def play_game(white_engine, black_engine, max_moves=200, time_per_move=1000):
    """Play a single game between two engines"""
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["White"] = white_engine.name
    game.headers["Black"] = black_engine.name
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    
    node = game
    move_count = 0
    
    while not board.is_game_over() and move_count < max_moves:
        # Determine current engine
        current_engine = white_engine if board.turn == chess.WHITE else black_engine
        
        # Get move
        try:
            move = current_engine.get_move(board, time_per_move)
            
            if move and move in board.legal_moves:
                # Make the move
                san = board.san(move)
                board.push(move)
                node = node.add_variation(move)
                move_count += 1
                
                # Print progress
                if move_count % 20 == 0:
                    print(f"  Move {move_count}: {current_engine.name} played {san}")
                    
            else:
                print(f"  Invalid or no move from {current_engine.name}")
                break
                
        except Exception as e:
            print(f"  Error getting move from {current_engine.name}: {e}")
            break
    
    # Determine result
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            game.headers["Result"] = "0-1"
            return "black"
        else:
            game.headers["Result"] = "1-0"
            return "white"
    elif board.is_stalemate():
        game.headers["Result"] = "1/2-1/2"
        return "draw"
    elif board.is_insufficient_material():
        game.headers["Result"] = "1/2-1/2"
        return "draw"
    elif board.can_claim_fifty_moves():
        game.headers["Result"] = "1/2-1/2"
        return "draw"
    elif move_count >= max_moves:
        game.headers["Result"] = "1/2-1/2"
        return "draw"
    else:
        # Incomplete game
        game.headers["Result"] = "*"
        return "incomplete"

def run_tournament(num_games=10):
    """Run a tournament between Knightmare and Random bots"""
    print("=" * 60)
    print("Simple Chess Tournament")
    print("=" * 60)
    print(f"Games to play: {num_games}")
    print("Time per move: 1000ms")
    print("=" * 60)
    
    results = {"knightmare": 0, "random": 0, "draw": 0}
    
    for game_num in range(1, num_games + 1):
        print(f"\nGame {game_num}/{num_games}")
        
        # Alternate colors
        if game_num % 2 == 1:
            white = ChessEngine("./knightmare_bot.py", "Knightmare")
            black = ChessEngine("./random_chess_bot.py", "Random")
            white_name = "Knightmare"
            black_name = "Random"
        else:
            white = ChessEngine("./random_chess_bot.py", "Random")
            black = ChessEngine("./knightmare_bot.py", "Knightmare")
            white_name = "Random"
            black_name = "Knightmare"
        
        print(f"White: {white_name} vs Black: {black_name}")
        
        try:
            # Start engines
            white.start()
            black.start()
            
            # Send new game command
            white.send("ucinewgame")
            black.send("ucinewgame")
            time.sleep(0.1)
            
            # Play game
            result = play_game(white, black)
            
            # Update results
            if result == "white":
                print(f"Result: {white_name} wins!")
                if white_name == "Knightmare":
                    results["knightmare"] += 1
                else:
                    results["random"] += 1
            elif result == "black":
                print(f"Result: {black_name} wins!")
                if black_name == "Knightmare":
                    results["knightmare"] += 1
                else:
                    results["random"] += 1
            elif result == "draw":
                print("Result: Draw")
                results["draw"] += 0.5
                results["knightmare"] += 0.5
                results["random"] += 0.5
            else:
                print("Result: Incomplete game")
            
        except Exception as e:
            print(f"Error in game {game_num}: {e}")
        
        finally:
            # Cleanup
            white.quit()
            black.quit()
    
    # Print final results
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    knightmare_percentage = (results["knightmare"] / num_games) * 100
    random_percentage = (results["random"] / num_games) * 100
    
    print(f"Knightmare: {results['knightmare']:.1f} / {num_games} ({knightmare_percentage:.1f}%)")
    print(f"Random:     {results['random']:.1f} / {num_games} ({random_percentage:.1f}%)")
    if results["draw"] > 0:
        print(f"Draws:      {int(results['draw'] / 0.5)} games")
    
    print("=" * 60)
    
    if results["knightmare"] > results["random"]:
        print("🏆 KNIGHTMARE WINS THE TOURNAMENT! 🏆")
    elif results["random"] > results["knightmare"]:
        print("🏆 RANDOM WINS THE TOURNAMENT! 🏆")
    else:
        print("🤝 THE TOURNAMENT IS A DRAW! 🤝")

def main():
    """Main function"""
    import sys
    
    # Get number of games from command line
    if len(sys.argv) > 1:
        try:
            num_games = int(sys.argv[1])
        except:
            num_games = 10
    else:
        num_games = 10
    
    run_tournament(num_games)

if __name__ == "__main__":
    main()