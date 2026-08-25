#!/usr/bin/env python3
"""
LLM Chess Bot using llama3.2
Author: Vatsal Patel
"""

import chess
import os
import re
import sys
import random
import time

try:
    import ollama
except ImportError:
    # The move parsing helpers are useful (and testable) without a model
    # server installed; only get_best_move actually needs Ollama.
    ollama = None

# Source square, destination square and an optional promotion piece
UCI_PATTERN = re.compile(r'[a-h][1-8][a-h][1-8][qrbn]?')

# Ollama model used unless KNIGHTMARE_MODEL says otherwise
DEFAULT_MODEL = "llama3.2"

# Seconds allowed for model round trips when the host sends no movetime
DEFAULT_MOVE_TIME = 2.0

# How many legal moves to offer the model at once. A long list crowds the
# prompt and the model starts ignoring it, so the list is cut - which makes
# the order it is cut in matter, see moves_for_prompt.
MAX_MOVES_SHOWN = 15

# How many times to ask before falling back to a random legal move
MAX_ATTEMPTS = 3


# Rough piece worth, used only to rank captures for the prompt. Kept local
# rather than imported from the search engine: this bot is a standalone
# script and does not otherwise depend on it.
CAPTURE_WORTH = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def moves_for_prompt(board, limit=MAX_MOVES_SHOWN):
    """The moves to offer the model, most interesting first

    The list has to be cut somewhere, and it used to be cut in whatever
    order python-chess generated the moves, which is by piece and square.
    That silently hid material: in the standard "kiwipete" test position
    three of the eight captures fell outside the first fifteen moves,
    including the one the search engine picks. Captures, checks and
    promotions go first now, so a cut list still contains the moves worth
    considering.
    """
    def interest(move):
        score = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            # An empty target square means an en passant capture, which
            # takes a pawn even though nothing stands on the square
            worth = CAPTURE_WORTH.get(victim.piece_type, 0) if victim else 1
            score += 100 + worth
        if move.promotion:
            score += 90
        if board.gives_check(move):
            score += 50
        return score

    # Sorted rather than partially selected, so the order is stable for a
    # given position and the prompt does not change between attempts
    ordered = sorted(board.legal_moves, key=lambda m: (-interest(m), m.uci()))
    return ordered[:limit]


def parse_move(text, legal_moves):
    """Pull the first legal move out of a model's reply

    Scans in the order the moves appear in the text rather than in move
    generation order, so a reply like "not e2e4, I will play d2d4" gives
    back d2d4 instead of whichever happens to be generated first.
    """
    if not text:
        return None

    lowered = text.lower()
    legal = set(legal_moves)

    # Dashes are a common LLM habit: e2-e4
    for candidate in UCI_PATTERN.findall(lowered.replace("-", "")):
        try:
            move = chess.Move.from_uci(candidate)
        except ValueError:
            continue
        if move in legal:
            return move

    return None


class LLMChessBot:
    def __init__(self, model_name=None):
        self.model_name = model_name or os.environ.get("KNIGHTMARE_MODEL", DEFAULT_MODEL)

    def get_best_move(self, board, max_time=DEFAULT_MOVE_TIME):
        """Ask the model for a move, falling back to a random legal one

        Every retry costs a full model round trip, so stop asking once the
        time budget is spent rather than overrunning the clock.
        """
        start_time = time.time()
        legal_moves = list(board.legal_moves)

        if not legal_moves:
            return None

        if ollama is None:
            print("info string Ollama is not installed, playing randomly")
            return random.choice(legal_moves)

        if len(legal_moves) == 1:
            return legal_moves[0]

        # Check for checkmate in one move
        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            board.pop()

        # Cut the list, but cut it so the interesting moves survive
        moves_to_show = moves_for_prompt(board)
        legal_moves_str = ", ".join([str(move) for move in moves_to_show])
        
        prompt = f"""Pick ONE move from this list: {legal_moves_str}

Board:
{board}

Reply with just the move (like e2e4)."""
        
        # Try a few times if it fails
        for attempt in range(MAX_ATTEMPTS):
            # Another round trip would likely blow the budget
            if attempt > 0 and time.time() - start_time > max_time:
                print(
                    f"info string Out of time after {attempt} attempt(s), "
                    "falling back to random"
                )
                break

            try:
                response = ollama.generate(model=self.model_name, prompt=prompt)
                move = parse_move(response['response'], legal_moves)
                if move is not None:
                    return move
                print(f"info string Attempt {attempt+1}: no legal move in reply")

            except Exception as e:
                print(f"info string Attempt {attempt+1} failed: {e}")
        
        # If all attempts fail, just pick random
        return random.choice(legal_moves)

def parse_movetime(msg, default=DEFAULT_MOVE_TIME):
    """Seconds to spend on a move, taken from a go command"""
    parts = msg.split()
    if "movetime" not in parts:
        return default

    idx = parts.index("movetime")
    if idx + 1 >= len(parts):
        return default

    try:
        return max(0.1, int(parts[idx + 1]) / 1000.0)
    except ValueError:
        return default


# Globals for UCI
global_bot = None
global_board = chess.Board()

def uci(msg):
    global global_board, global_bot
    
    if msg == "uci":
        print("id name LLM Chess Bot")
        print("id author Vatsal Patel")
        print("uciok")
        sys.stdout.flush()
        
    elif msg == "isready":
        if global_bot is None:
            global_bot = LLMChessBot()
        print("readyok")
        sys.stdout.flush()
        
    elif msg == "ucinewgame":
        global_board = chess.Board()
        
    elif msg.startswith("position"):
        if "startpos" in msg:
            global_board = chess.Board()
            moves_start = msg.find("moves")
            if moves_start != -1:
                moves_str = msg[moves_start + 6:].strip()
                if moves_str:
                    for move_uci in moves_str.split():
                        try:
                            move = chess.Move.from_uci(move_uci)
                            if move in global_board.legal_moves:
                                global_board.push(move)
                        except ValueError:
                            pass
        elif "fen" in msg:
            fen_start = msg.find("fen") + 4
            moves_start = msg.find("moves")
            fen = msg[fen_start:moves_start].strip() if moves_start != -1 else msg[fen_start:].strip()
            try:
                global_board = chess.Board(fen)
                if moves_start != -1:
                    moves_str = msg[moves_start + 6:].strip()
                    if moves_str:
                        for move_uci in moves_str.split():
                            try:
                                move = chess.Move.from_uci(move_uci)
                                if move in global_board.legal_moves:
                                    global_board.push(move)
                            except ValueError:
                                pass
            except ValueError:
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = LLMChessBot()

        move = global_bot.get_best_move(global_board, parse_movetime(msg))
        
        if move and move in global_board.legal_moves:
            print(f"bestmove {move}")
        else:
            legal_moves = list(global_board.legal_moves)
            if legal_moves:
                print(f"bestmove {legal_moves[0]}")
            else:
                print("bestmove 0000")
        
        sys.stdout.flush()
        
    elif msg == "quit":
        sys.exit(0)

def main():
    global global_bot
    global_bot = LLMChessBot()
    
    try:
        while True:
            line = input().strip()
            if line:
                uci(line)
    except (EOFError, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    main()