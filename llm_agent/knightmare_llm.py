#!/usr/bin/env python3
"""
LLM Chess Bot using llama3.2
Author: Vatsal Patel
"""

import chess
import sys
import random
import ollama

class LLMChessBot:
    def __init__(self, model_name="llama3.2"):
        self.model_name = model_name
        
    def get_best_move(self, board):
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            return None
        
        if len(legal_moves) == 1:
            return legal_moves[0]
        
        # Check for checkmate in one move
        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            board.pop()
        
        # Limit moves shown to avoid overwhelming the LLM
        moves_to_show = legal_moves[:15]
        legal_moves_str = ", ".join([str(move) for move in moves_to_show])
        
        prompt = f"""Pick ONE move from this list: {legal_moves_str}

Board:
{board}

Reply with just the move (like e2e4)."""
        
        # Try a few times if it fails
        for attempt in range(3):
            try:
                response = ollama.generate(model=self.model_name, prompt=prompt)
                llm_output = response['response'].strip().lower()
                
                # Look for the move in the response
                for move in legal_moves:
                    if str(move) in llm_output:
                        return move
                
                # Try parsing first word
                tokens = llm_output.split()
                if tokens:
                    move_str = tokens[0].replace('-', '').strip('.,;:')
                    try:
                        move = chess.Move.from_uci(move_str)
                        if move in legal_moves:
                            return move
                    except:
                        pass
                        
            except Exception as e:
                print(f"info string Attempt {attempt+1} failed: {e}")
        
        # If all attempts fail, just pick random
        return random.choice(legal_moves)

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
                        except:
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
                            except:
                                pass
            except:
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = LLMChessBot()
        
        move = global_bot.get_best_move(global_board)
        
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