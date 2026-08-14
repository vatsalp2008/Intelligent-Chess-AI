#!/usr/bin/env python3
"""
LLM Chess Bot using Mistral
Author: Vatsal Patel
"""

import chess
import sys
import random
import re
import ollama
from datetime import datetime
import json

# Source square, destination square and an optional promotion piece
UCI_PATTERN = re.compile(r'[a-h][1-8][a-h][1-8][qrbn]?')

class KnightmareLLMRecovery:
    def __init__(self, model_name="mistral"):
        self.model_name = model_name
        self.max_retries = 3
        self.log_file = f"llm_log_recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
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
        moves_list = "\n".join([f"{i+1}. {move}" for i, move in enumerate(legal_moves)])
        
        prompt = f"""Choose the best chess move from this numbered list:

{moves_list}

Position:
{board}

Reply with ONLY the move in UCI format (example: e2e4). Pick from the list above."""
        
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return prompt, response['response'].strip()
    
    def get_llm_move_simplified(self, board, legal_moves):
        """Strategy 4: Simplified prompt focusing on just picking from list"""
        legal_moves_str = ", ".join([str(move) for move in legal_moves[:10]])  # Limit to 10
        
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
            except:
                pass
        
        # Strategy 2: Look for 4-5 character sequences
        for match in UCI_PATTERN.findall(llm_output.lower()):
            try:
                move = chess.Move.from_uci(match)
                if move in legal_moves:
                    return move, None
            except:
                pass
        
        # Strategy 3: Check if any legal move is mentioned
        for move in legal_moves:
            move_str = str(move)
            if move_str in llm_output.lower():
                return move, None
        
        return None, f"Could not parse: {llm_output[:50]}"
    
    def get_best_move(self, board, max_time=2.0):
        """Get best move with progressive recovery strategies"""
        self.move_number += 1
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            return None
        
        if len(legal_moves) == 1:
            return legal_moves[0]
        
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
        
        strategies = [
            ("standard", self.get_llm_move_standard),
            ("feedback", None),  # Will be called with error feedback
            ("numbered", self.get_llm_move_numbered_list),
            ("simplified", self.get_llm_move_simplified)
        ]
        
        last_error = None
        
        for attempt, (strategy_name, strategy_func) in enumerate(strategies, 1):
            try:
                # Special handling for feedback strategy
                if strategy_name == "feedback" and last_error:
                    prompt, llm_output = self.get_llm_move_with_feedback(
                        board, legal_moves, last_error
                    )
                elif strategy_name == "feedback":
                    continue  # Skip feedback on first attempt
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
        parts = msg.split()
        
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
                        except:
                            pass
        
        elif "fen" in msg:
            fen_start = msg.find("fen") + 4
            moves_start = msg.find("moves")
            
            if moves_start == -1:
                fen = msg[fen_start:].strip()
            else:
                fen = msg[fen_start:moves_start].strip()
            
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
                            except:
                                pass
            except:
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = KnightmareLLMRecovery()
        
        move = global_bot.get_best_move(global_board, 2.0)
        
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