#!/usr/bin/env python3
import chess
import random
import sys

board = chess.Board()

for line in sys.stdin:
    line = line.strip()
    
    if line == "uci":
        print("id name Random")
        print("uciok")
    elif line == "isready":
        print("readyok")
    elif line == "ucinewgame":
        board = chess.Board()
    elif line.startswith("position"):
        if "startpos" in line:
            board = chess.Board()
        elif "fen" in line:
            fen_start = line.find("fen") + 4
            fen_end = line.find("moves") if "moves" in line else len(line)
            try:
                board = chess.Board(line[fen_start:fen_end].strip())
            except ValueError:
                board = chess.Board()

        if "moves" in line:
            moves_start = line.find("moves") + 6
            for uci in line[moves_start:].split():
                try:
                    move = chess.Move.from_uci(uci)
                except ValueError:
                    break
                if move not in board.legal_moves:
                    break
                board.push(move)
    elif line.startswith("go"):
        moves = list(board.legal_moves)
        print(f"bestmove {random.choice(moves) if moves else '0000'}")
    elif line == "quit":
        break
    
    sys.stdout.flush()