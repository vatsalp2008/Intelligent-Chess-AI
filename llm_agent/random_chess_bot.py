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
            try:
                parsed = chess.Move.from_uci(move)
            except ValueError:
                break
            if parsed not in board.legal_moves:
                break
            board.push(parsed)
    elif msg.startswith("position fen"):
        fen = msg.removeprefix("position fen ")
        try:
            board.set_fen(fen)
        except ValueError:
            board.set_fen(chess.STARTING_FEN)
    elif msg.startswith("go"):
        move = make_random_move(board) #change this
        print(f"bestmove {move}")
    elif msg == "quit":
        sys.exit(0)
    return
    
def main():
    '''Expects to forever be passed UCI messages'''
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            # The host closed the pipe, which is a normal way to finish
            break

        try:
            uci(line)
        except Exception as exc:
            # Report what actually went wrong instead of "Fatal Error",
            # and keep going so one bad command does not end the game
            print(f"info string Error handling {line!r}: {exc}")
            sys.stdout.flush()

if __name__ == "__main__":
    # print(sys.argv)
    main()
