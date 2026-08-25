#!/usr/bin/env python
import chess
import random
import sys

board = chess.Board()

def make_random_move(b: chess.Board):
    '''Returns a random legal move, or None if there are none'''
    moves = list(b.legal_moves)
    return random.choice(moves) if moves else None

def uci(msg: str):
    '''Returns result of UCI protocol given passed message'''
    if msg == "uci":
        print("id name Random Chess Bot")
        print("id author Oscar Veliz")
        print("uciok")
    elif msg == "isready":
        print("readyok")
    elif msg == "ucinewgame":
        # Without this the next game carried on from the last one's
        # final position, because nothing else resets the board
        board.set_fen(chess.STARTING_FEN)
    elif msg.startswith("position"):
        # One branch for both forms. "position startpos" with no move list
        # used to match nothing at all, so a new game began from wherever
        # the previous one ended.
        parts = msg.split()
        moves_at = parts.index("moves") if "moves" in parts else len(parts)

        if "startpos" in parts:
            board.set_fen(chess.STARTING_FEN)
        elif "fen" in parts:
            # Only the FEN fields, not the move list that may follow it:
            # passing both to set_fen raised and reset to the opening
            fen = " ".join(parts[parts.index("fen") + 1:moves_at])
            try:
                board.set_fen(fen)
            except ValueError:
                print(f"info string could not read fen {fen!r}")
                board.set_fen(chess.STARTING_FEN)

        for move in parts[moves_at + 1:]:
            try:
                parsed = chess.Move.from_uci(move)
            except ValueError:
                print(f"info string could not read move {move!r}, stopping replay")
                break
            if parsed not in board.legal_moves:
                print(f"info string {move} is not legal here, stopping replay")
                break
            board.push(parsed)
    elif msg.startswith("go"):
        move = make_random_move(board)
        # A finished position used to raise here and send nothing at all,
        # leaving the host waiting for a reply that never came
        print(f"bestmove {move}" if move else "bestmove 0000")
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
