#!/usr/bin/env python3
"""
Board presentation shared by the two web interfaces.

Both Flask apps draw the same board, report the same legal moves and work
out the same takeback, but they grew separately and each had its own copy.
The functions here are the parts that depend only on a position, with no
Flask request or module level game state involved, which is what makes them
worth sharing and easy to test.

Anything that touches an app's own globals — whose turn it is, which engine
plays which side — stays in that app, because the two differ there.
"""

import chess
import chess.svg

# Pixels across for the rendered board. Both interfaces used 500.
BOARD_SIZE = 500


def legal_by_origin(board):
    """Legal moves as {from_square_name: [uci, ...]}

    Sent to the browser so it can show a piece's options and reject an
    impossible drag without having to know how chess works. Promotions
    appear as the full UCI including the piece, so the client can offer a
    choice when several share the same destination.
    """
    grouped = {}
    for move in board.legal_moves:
        grouped.setdefault(chess.square_name(move.from_square), []).append(move.uci())
    return grouped


def render_board(board, flipped=False, size=BOARD_SIZE):
    """The position as an SVG, with the useful markings turned on

    The last move is marked because otherwise the engine's reply has to be
    found by comparing the board against what it looked like a moment ago,
    and a king in check is marked because that is easy to miss when the
    king is not the piece that just moved.
    """
    return chess.svg.board(
        board,
        size=size,
        flipped=flipped,
        lastmove=board.move_stack[-1] if board.move_stack else None,
        check=board.king(board.turn) if board.is_check() else None,
    )


def moves_by(board, colour):
    """How many moves on the stack were played by the given colour

    Needed because a board set up from a FEN can start on either side, so
    the mover of a given move is not simply decided by its index.
    """
    root_turn = board.root().turn
    return sum(
        1 for index in range(len(board.move_stack))
        if (root_turn if index % 2 == 0 else not root_turn) == colour
    )


def plies_to_take_back(board, colour):
    """How many moves to pop to hand the turn back to colour

    Unwinding a single move would hand it straight back to the opponent,
    which would just play again, so this counts whole move pairs. It
    returns 0 when the given side has nothing of its own to take back:
    popping the opponent's opening move would leave them to move with
    nothing prompting them to play.
    """
    if not moves_by(board, colour):
        return 0

    scratch = board.copy()
    popped = 0
    while scratch.move_stack:
        scratch.pop()
        popped += 1
        if scratch.turn == colour:
            break
    return popped
