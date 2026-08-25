#!/usr/bin/env python3
"""
LLM Chess Bot using Mistral
Author: Vatsal Patel
"""

import chess
import sys
import os
import random
import re
import time

try:
    import ollama
except ImportError:
    # Parsing and logging are useful (and testable) without a model server
    ollama = None

from datetime import datetime
import json

# Shared with the llama bot rather than copied: both need the same answer
# to "which moves are worth putting in front of a model", and both live in
# this directory, so there is no package boundary to cross.
from knightmare_llm import moves_for_prompt, replay_moves

# Source square, destination square and an optional promotion piece
UCI_PATTERN = re.compile(r'[a-h][1-8][a-h][1-8][qrbn]?')

# Seconds allowed for model round trips when the host sends no movetime
DEFAULT_MOVE_TIME = 2.0

# Ollama model used unless KNIGHTMARE_MODEL says otherwise
DEFAULT_MODEL = "mistral"


def default_log_path():
    """Where to write the interaction log

    KNIGHTMARE_LOG_DIR keeps logs out of whichever directory the engine
    happens to be launched from, which matters when a tournament host
    starts it from somewhere else.
    """
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f"llm_log_recovery_{stamp}.jsonl"
    log_dir = os.environ.get("KNIGHTMARE_LOG_DIR")
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, name)
    return name

class KnightmareLLMRecovery:
    def __init__(self, model_name=None, log_file=None):
        self.model_name = model_name or os.environ.get("KNIGHTMARE_MODEL", DEFAULT_MODEL)
        self.log_file = log_file or default_log_path()
        self.game_number = 0
        self.move_number = 0

    def log_interaction(self, prompt, response, move_attempted, was_valid, attempt_num, strategy, error=None):
        """Log each LLM interaction to file"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "game": self.game_number,
            "move": self.move_number,
            "attempt": attempt_num,
            "strategy": strategy,
            "model": self.model_name,
            "prompt": prompt,
            "llm_response": response,
            "move_attempted": move_attempted,
            "was_valid": was_valid,
            "error": str(error) if error else None
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_llm_move_standard(self, board, legal_moves):
        """Strategy 1: Standard prompt with UCI examples"""
        legal_moves_str = ", ".join([str(move) for move in legal_moves])
        
        prompt = f"""You are a strong chess player. Consider these principles:
- Control the center (e4, d4, e5, d5)
- Develop knights and bishops early
- Castle to protect your king
- Don't move the same piece twice in opening

CRITICAL: Respond in UCI format (source square + destination square).
Examples: e2e4 (not e4), g1f3 (not Nf3), f1b5 (not Bb5)

Position:
{board}

Legal moves: {legal_moves_str}

Reply with ONLY the move in UCI format (example: e2e4)."""
        
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return prompt, response['response'].strip()
    
    def get_llm_move_with_feedback(self, board, legal_moves, previous_error):
        """Strategy 2: Re-prompt with error feedback"""
        legal_moves_str = ", ".join([str(move) for move in legal_moves])
        
        prompt = f"""You made an error: {previous_error}

Let me clarify: You MUST use UCI format (4-5 characters).
Examples: e2e4, g1f3, e7e8q

Current position:
{board}

Your legal moves: {legal_moves_str}

Try again. Reply with ONLY ONE legal move in UCI format."""
        
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return prompt, response['response'].strip()
    
    def get_llm_move_numbered_list(self, board, legal_moves):
        """Strategy 3: Numbered list - pick a number"""
        # Ordered so that a model skimming the top of a long list still
        # sees the captures and checks
        moves_list = "\n".join(
            f"{i+1}. {move}"
            for i, move in enumerate(moves_for_prompt(board, limit=len(legal_moves)))
        )
        
        prompt = f"""Choose the best chess move from this numbered list:

{moves_list}

Position:
{board}

Reply with ONLY the move in UCI format (example: e2e4). Pick from the list above."""
        
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return prompt, response['response'].strip()
    
    def get_llm_move_simplified(self, board, legal_moves):
        """Strategy 4: Simplified prompt focusing on just picking from list"""
        # Ten moves out of forty is a heavy cut, so it has to keep the ones
        # that matter: generation order used to hide most of the captures
        legal_moves_str = ", ".join(str(move) for move in moves_for_prompt(board, limit=10))
        
        prompt = f"""Pick ONE move from this list: {legal_moves_str}

Board:
{board}

Reply with just the move (like e2e4)."""
        
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return prompt, response['response'].strip()
    
    def parse_move_with_recovery(self, llm_output, legal_moves):
        """Try multiple parsing strategies"""
        if not llm_output:
            return None, "Empty response"
        
        # Strategy 1: Take first token
        tokens = llm_output.split()
        if tokens:
            move_str = tokens[0].lower().replace('-', '').strip('.,;:')
            try:
                move = chess.Move.from_uci(move_str)
                if move in legal_moves:
                    return move, None
            except ValueError:
                pass
        
        # Strategy 2: scan the whole reply for a UCI move, in the order the
        # moves appear in the text. Dashes are stripped first because models
        # often write e2-e4, and the pattern needs the squares adjacent.
        #
        # There used to be a third strategy here that looked for each legal
        # move as a substring. It could never fire: every legal move's UCI
        # form matches this pattern, so anything it would have found was
        # already found above.
        for match in UCI_PATTERN.findall(llm_output.lower().replace('-', '')):
            try:
                move = chess.Move.from_uci(match)
                if move in legal_moves:
                    return move, None
            except ValueError:
                pass

        return None, f"Could not parse: {llm_output[:50]}"
    
    def get_best_move(self, board, max_time=2.0):
        """Get best move with progressive recovery strategies

        Each strategy costs a full model round trip, so the remaining time
        budget is checked before starting another one.
        """
        start_time = time.time()
        self.move_number += 1
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            return None

        if len(legal_moves) == 1:
            return legal_moves[0]

        if ollama is None:
            print("info string Ollama is not installed, playing randomly")
            return random.choice(legal_moves)

        # Check for immediate checkmate
        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                self.log_interaction(
                    "Checkmate detection",
                    f"Found checkmate: {move}",
                    str(move),
                    True,
                    0,
                    "checkmate_detection"
                )
                return move
            board.pop()
        
        # Tried in order until one yields a legal move. The third element
        # marks a strategy that needs the previous failure to prompt with,
        # so it is skipped while there is nothing to report.
        strategies = [
            ("standard", self.get_llm_move_standard, False),
            ("feedback", self.get_llm_move_with_feedback, True),
            ("numbered", self.get_llm_move_numbered_list, False),
            ("simplified", self.get_llm_move_simplified, False),
        ]

        last_error = None

        for attempt, (strategy_name, strategy_func, needs_error) in enumerate(strategies, 1):
            if needs_error and not last_error:
                continue

            # Another round trip would likely blow the budget
            if attempt > 1 and time.time() - start_time > max_time:
                print(
                    f"info string Out of time after {attempt - 1} attempt(s), "
                    "falling back to random"
                )
                break

            try:
                if needs_error:
                    prompt, llm_output = strategy_func(board, legal_moves, last_error)
                else:
                    prompt, llm_output = strategy_func(board, legal_moves)

                # Try to parse the move
                move, error = self.parse_move_with_recovery(llm_output, legal_moves)
                
                if move:
                    # Success!
                    self.log_interaction(
                        prompt,
                        llm_output,
                        str(move),
                        True,
                        attempt,
                        strategy_name
                    )
                    print(f"info string Attempt {attempt} ({strategy_name}): Success with {move}")
                    return move
                else:
                    # Failed - log and try next strategy
                    last_error = error
                    self.log_interaction(
                        prompt,
                        llm_output,
                        llm_output[:20] if llm_output else "",
                        False,
                        attempt,
                        strategy_name,
                        error
                    )
                    print(f"info string Attempt {attempt} ({strategy_name}): {error}")
                    
            except Exception as e:
                last_error = str(e)
                self.log_interaction(
                    f"Strategy: {strategy_name}",
                    "",
                    "",
                    False,
                    attempt,
                    strategy_name,
                    str(e)
                )
                print(f"info string Attempt {attempt} ({strategy_name}) exception: {e}")
        
        # All strategies failed - use random fallback
        fallback_move = random.choice(legal_moves)
        self.log_interaction(
            "All strategies failed",
            f"Using random: {fallback_move}",
            str(fallback_move),
            True,
            len(strategies) + 1,
            "random_fallback",
            "All recovery strategies exhausted"
        )
        print(f"info string All strategies failed, using random: {fallback_move}")
        return fallback_move

# Global variables for UCI
global_bot = None
global_board = chess.Board()

def uci(msg):
    """UCI protocol handler"""
    global global_board, global_bot
    
    if msg == "uci":
        print("id name LLM Chess Bot Mistral")
        print("id author Vatsal Patel")
        print("uciok")
        sys.stdout.flush()
        
    elif msg == "isready":
        if global_bot is None:
            global_bot = KnightmareLLMRecovery()
        print("readyok")
        sys.stdout.flush()
        
    elif msg == "ucinewgame":
        global_board = chess.Board()
        if global_bot:
            global_bot.game_number += 1
            global_bot.move_number = 0
        
    elif msg.startswith("position"):
        moves_start = msg.find("moves")
        moves_text = msg[moves_start + 6:].strip() if moves_start != -1 else ""

        if "startpos" in msg:
            global_board = replay_moves(chess.Board(), moves_text)
        elif "fen" in msg:
            fen_start = msg.find("fen") + 4
            fen = (msg[fen_start:moves_start] if moves_start != -1
                   else msg[fen_start:]).strip()
            try:
                global_board = replay_moves(chess.Board(fen), moves_text)
            except ValueError:
                print(f"info string could not read fen {fen!r}")
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = KnightmareLLMRecovery()
        
        # Respect movetime when the host supplies one
        max_time = DEFAULT_MOVE_TIME
        parts = msg.split()
        if "movetime" in parts:
            idx = parts.index("movetime")
            if idx + 1 < len(parts):
                try:
                    max_time = int(parts[idx + 1]) / 1000.0
                except ValueError:
                    pass

        move = global_bot.get_best_move(global_board, max_time)
        
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
    """Main entry point"""
    global global_bot
    global_bot = KnightmareLLMRecovery()
    
    print(f"# Logging to: {global_bot.log_file}", file=sys.stderr)
    
    try:
        while True:
            line = input().strip()
            if line:
                uci(line)
    except (EOFError, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    main()