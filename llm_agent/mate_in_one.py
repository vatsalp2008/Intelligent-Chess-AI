#!/usr/bin/env python
import chess
import sys
import random_chess_bot

board = chess.Board()

def find_mate_in_one(b: chess.Board):
    """Finds a mate-in-one move if available."""
    for move in b.legal_moves:
        b.push(move)
        is_mate = b.is_checkmate()
        b.pop()
        if is_mate:
            return move
    return None

def make_move(b: chess.Board):
    """Bot finds mate-in-one if available, otherwise random."""
    mate_in_one_move = find_mate_in_one(b)
    if mate_in_one_move:
        return mate_in_one_move
    return random_chess_bot.make_random_move(b)

def uci(msg: str):
    '''Returns result of UCI protocol given passed message'''
    if msg == "uci":
        print("id name Mate-in-One Bot")
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
        move = make_move(board) 
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
