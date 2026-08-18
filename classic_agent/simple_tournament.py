#!/usr/bin/env python3
"""
Simple tournament runner that actually works
No dependency on chester library
"""

import argparse
import queue
import subprocess
import threading
import chess
import chess.pgn
import time
from datetime import datetime

class EngineDied(RuntimeError):
    """Raised when an engine process exits or stops responding"""


class ChessEngine:
    def __init__(self, path, name):
        self.path = path
        self.name = name
        self.process = None
        self.output = queue.Queue()
        self.reader = None
        
    def start(self):
        """Start the engine process"""
        self.process = subprocess.Popen(
            ['python3', self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )

        # A daemon thread so a wedged engine cannot keep the process alive
        self.reader = threading.Thread(target=self._pump_output, daemon=True)
        self.reader.start()

        # Send UCI initialization
        self.send("uci")
        self.wait_for("uciok")
        
        self.send("isready")
        self.wait_for("readyok")
        
    def send(self, command):
        """Send command to engine"""
        try:
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise EngineDied(f"{self.name} is not accepting input: {exc}") from exc
        
    def _pump_output(self):
        """Move engine output into the queue until the pipe closes"""
        for line in self.process.stdout:
            self.output.put(line)
        self.output.put(None)  # sentinel: the engine closed its output

    def read_line(self, deadline):
        """One line of engine output, or None if nothing arrives in time

        readline() blocks until a newline appears, so an engine that is
        running but not answering would hang the tournament forever.
        Selecting on the pipe does not work either, because the text
        reader buffers ahead and leaves the pipe looking empty while a
        line is already in hand. A reader thread avoids both problems.
        """
        remaining = deadline - time.time()
        if remaining <= 0:
            return None

        try:
            line = self.output.get(timeout=remaining)
        except queue.Empty:
            return None

        if line is None:
            raise EngineDied(f"{self.name} closed its output")
        return line

    def wait_for(self, response, timeout=5):
        """Wait for specific response

        Gives up both on end of file, meaning the engine exited, and on the
        timeout, meaning it is alive but not answering.
        """
        deadline = time.time() + timeout
        while True:
            raw = self.read_line(deadline)
            if raw is None:
                raise TimeoutError(f"Timeout waiting for {response} from {self.name}")
            if response in raw.strip():
                return raw.strip()
    
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
        deadline = time.time() + (time_ms / 1000 + 2)
        while True:
            raw = self.read_line(deadline)
            if raw is None:
                # Alive but not answering, so give up on this move
                return None
            line = raw.strip()
            if line.startswith("bestmove"):
                move_uci = line.split()[1]
                if move_uci == "0000":
                    return None
                try:
                    return chess.Move.from_uci(move_uci)
                except ValueError:
                    print(f"Invalid move from {self.name}: {move_uci}")
                    return None

    def quit(self):
        """Shut the engine down, tolerating one that has already died

        Cleanup usually runs from a finally block, often because something
        already went wrong. Raising here would replace that error and skip
        whatever cleanup came after, so an unreachable engine is not a
        failure: it is the state we were trying to reach anyway.
        """
        if not self.process:
            return

        try:
            self.send("quit")
            time.sleep(0.2)
        except EngineDied:
            pass  # already gone, nothing to ask politely

        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Ignored the terminate, so stop it the hard way
            self.process.kill()

def play_game(white_engine, black_engine, max_moves=200, time_per_move=1000):
    """Play a single game between two engines

    Returns a (result, game) tuple where result is one of
    "white", "black", "draw" or "incomplete" and game is the PGN record.
    """
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
            return "black", game
        else:
            game.headers["Result"] = "1-0"
            return "white", game
    elif board.is_stalemate():
        game.headers["Result"] = "1/2-1/2"
        return "draw", game
    elif board.is_insufficient_material():
        game.headers["Result"] = "1/2-1/2"
        return "draw", game
    elif board.can_claim_fifty_moves():
        game.headers["Result"] = "1/2-1/2"
        return "draw", game
    elif move_count >= max_moves:
        game.headers["Result"] = "1/2-1/2"
        return "draw", game
    else:
        # Incomplete game
        game.headers["Result"] = "*"
        return "incomplete", game

def save_games(games, path):
    """Append the played games to a PGN file"""
    if not games:
        return

    with open(path, "w") as pgn_file:
        for game in games:
            print(game, file=pgn_file, end="\n\n")

    print(f"\nSaved {len(games)} game(s) to {path}")


def run_tournament(num_games=10, time_per_move=1000, pgn_path="tournament.pgn"):
    """Run a tournament between Knightmare and Random bots"""
    print("=" * 60)
    print("Simple Chess Tournament")
    print("=" * 60)
    print(f"Games to play: {num_games}")
    print(f"Time per move: {time_per_move}ms")
    print("=" * 60)
    
    results = {"knightmare": 0, "random": 0}
    draws = 0
    games = []

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
            result, game = play_game(white, black, time_per_move=time_per_move)
            game.headers["Event"] = "Simple Chess Tournament"
            game.headers["Round"] = str(game_num)
            games.append(game)
            
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
                draws += 1
                results["knightmare"] += 0.5
                results["random"] += 0.5
            else:
                print("Result: Incomplete game")
            
        except Exception as e:
            print(f"Error in game {game_num}: {e}")
        
        finally:
            # Each engine independently, so a failure on one still cleans
            # up the other
            for engine in (white, black):
                try:
                    engine.quit()
                except Exception as exc:
                    print(f"  Could not shut down {engine.name}: {exc}")
    
    save_games(games, pgn_path)

    # Print final results
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    knightmare_percentage = (results["knightmare"] / num_games) * 100
    random_percentage = (results["random"] / num_games) * 100
    
    print(f"Knightmare: {results['knightmare']:.1f} / {num_games} ({knightmare_percentage:.1f}%)")
    print(f"Random:     {results['random']:.1f} / {num_games} ({random_percentage:.1f}%)")
    if draws > 0:
        print(f"Draws:      {draws} games")
    
    print("=" * 60)
    
    if results["knightmare"] > results["random"]:
        print("🏆 KNIGHTMARE WINS THE TOURNAMENT! 🏆")
    elif results["random"] > results["knightmare"]:
        print("🏆 RANDOM WINS THE TOURNAMENT! 🏆")
    else:
        print("🤝 THE TOURNAMENT IS A DRAW! 🤝")

def parse_args():
    """Parse command line options"""
    parser = argparse.ArgumentParser(
        description="Run a tournament between Knightmare and the random bot"
    )
    parser.add_argument(
        "games", nargs="?", type=int, default=10,
        help="number of games to play (default: 10)"
    )
    parser.add_argument(
        "--time", type=int, default=1000, metavar="MS",
        help="thinking time per move in milliseconds (default: 1000)"
    )
    parser.add_argument(
        "--pgn", default="tournament.pgn", metavar="PATH",
        help="where to write the games (default: tournament.pgn)"
    )
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_args()
    run_tournament(args.games, time_per_move=args.time, pgn_path=args.pgn)

if __name__ == "__main__":
    main()