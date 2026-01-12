#!/usr/bin/env python
import chess
import random
import sys

board = chess.Board()

def make_random_move(b: chess.Board):
    '''Returns a random legal move'''
    return random.choice(list(b.legal_moves))

def uci(msg: str):
    '''Returns result of UCI protocol given passed message'''
    if msg == "uci":
        print("id name Random Chess Bot")
        print("id author Oscar Veliz")
        print("uciok")
    elif msg == "isready":
        print("readyok")
    elif msg.startswith("position startpos moves"):
        board.clear()
        board.set_fen(chess.STARTING_FEN)
        moves = msg.split()[3:]
        for move in moves:
            board.push(chess.Move.from_uci(move))
    elif msg.startswith("position fen"):
        fen = msg.removeprefix("position fen ")
        board.set_fen(fen)
    elif msg.startswith("go"):
        move = make_random_move(board) #change this
        print(f"bestmove {move}")
    elif msg == "quit":
        sys.exit(0)
    return
    
def main():
    '''Expects to forever be passed UCI messages'''
    try:
        while True:
            uci(input())
    except Exception:
        print("Fatal Error")

if __name__ == "__main__":
    # print(sys.argv)
    main()
