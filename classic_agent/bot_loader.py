#!/usr/bin/env python3
"""
Shared helpers for the web interfaces to load and drive the engine.

Both Flask apps used to carry identical copies of this: find whatever
Knightmare class lives in knightmare_bot.py, then work out which method to
call on it. Keeping one copy means a change to the engine's interface only
has to be handled in one place.

Writing the game out as PGN lives here for the same reason: both
interfaces play a game worth saving, and the format has enough small rules
to be worth getting right once.
"""

import contextlib
import datetime
import io
import os
import random
import re
import sys

import chess

# The engine reports progress on UCI info lines. Pulling the last one out
# lets the web interfaces show what the engine thought, instead of that
# detail only reaching the server's own log.
INFO_LINE = re.compile(
    r"info depth (?P<depth>\d+) score (?P<score>cp -?\d+|mate -?\d+)"
    r".*?(?: pv (?P<pv>.*))?$"
)

def load_bot_class(module_name="knightmare_bot"):
    """Return the engine class from the given module, or None

    The class is found by name rather than imported directly so that
    renaming it in the engine does not break the web interfaces.
    """
    # Only add the directory once: this used to insert on every call, so a
    # process that asked repeatedly grew sys.path without bound
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    try:
        module = __import__(module_name)
    except ImportError as exc:
        print(f"Warning: could not import {module_name}.py: {exc}")
        return None

    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and "Knightmare" in name:
            return obj

    print(f"Warning: no Knightmare class found in {module_name}.py")
    return None


def random_move(board):
    """Any legal move, used when the engine is missing or fails"""
    moves = list(board.legal_moves)
    return random.choice(moves) if moves else None


def parse_info(text):
    """The deepest info line in some engine output, as a dict

    Returns None when the output carries no usable info line, which is the
    case for the random bot and for a book move.
    """
    best = None
    for line in text.splitlines():
        match = INFO_LINE.match(line.strip())
        if match is None:
            continue
        found = match.groupdict()
        depth = int(found["depth"])
        if best is None or depth >= best["depth"]:
            best = {
                "depth": depth,
                "score": found["score"],
                "pv": (found["pv"] or "").strip(),
            }
    return best


def describe_info(info, board):
    """Turn raw UCI info into something readable for a person

    A score of "cp -104" and a line of "b8c6 d2d4" mean little at a glance;
    "-1.04" and "Nc6 d4" mean rather more. The board is needed because SAN
    depends on the position each move is played from.
    """
    if info is None:
        return None

    described = dict(info)

    score = info.get("score", "")
    if score.startswith("cp "):
        try:
            described["score_text"] = f"{int(score[3:]) / 100:+.2f}"
        except ValueError:
            described["score_text"] = score
    elif score.startswith("mate "):
        moves = score[5:]
        described["score_text"] = f"mate in {moves.lstrip('-')}" + (
            " for the opponent" if moves.startswith("-") else ""
        )
    else:
        described["score_text"] = score

    # Replay the line to name each move the way a player would
    scratch = board.copy(stack=False)
    san_moves = []
    for uci in info.get("pv", "").split():
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in scratch.legal_moves:
            break
        san_moves.append(scratch.san(move))
        scratch.push(move)
    described["pv_text"] = " ".join(san_moves)

    return described


def ask_engine(bot, board, seconds=1.0):
    """Ask the engine for a move, returning (move, info)

    info is whatever the engine reported about its search, or None. The
    engine writes those lines to stdout as any UCI engine would, so they
    are captured rather than intercepted.
    """
    if bot is None:
        return random_move(board), None

    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            if hasattr(bot, "get_move"):
                move = bot.get_move(board.copy(), seconds)
            elif hasattr(bot, "get_best_move"):
                move = bot.get_best_move(board.copy(), seconds)
            elif hasattr(bot, "minimax"):
                _, move = bot.minimax(
                    board.copy(), 3, -float("inf"), float("inf"),
                    board.turn == chess.WHITE,
                )
            else:
                return random_move(board), None
    except Exception as exc:
        print(f"Error getting engine move: {exc}")
        return random_move(board), None
    finally:
        # Still surface the engine's own output on the server log
        text = captured.getvalue()
        if text:
            sys.stdout.write(text)

    # Never hand back something the caller cannot play
    if move is None or move not in board.legal_moves:
        return random_move(board), None

    return move, describe_info(parse_info(text), board)


def best_move(bot, board, seconds=1.0):
    """Ask the engine for a move, falling back to a random legal one"""
    move, _ = ask_engine(bot, board, seconds)
    return move


def game_pgn(board, white, black):
    """The game so far as PGN

    Written out by hand rather than through chess.pgn, so that the only
    dependency stays python-chess itself and the headers can name whoever
    actually played. A game loaded from a FEN records that FEN, since the
    moves alone would not reproduce the position.
    """
    start = board.root()
    headers = [
        ('Event', 'Knightmare web interface'),
        ('Site', 'local'),
        ('Date', datetime.date.today().strftime('%Y.%m.%d')),
        ('White', white),
        ('Black', black),
        ('Result', board.result(claim_draw=True)),
    ]
    if start.fen() != chess.STARTING_FEN:
        headers.extend([('SetUp', '1'), ('FEN', start.fen())])

    lines = [f'[{key} "{value}"]' for key, value in headers]
    lines.append('')

    # Replay from the root so each move can be named the way a player
    # would write it, which depends on the position it is played from
    scratch = start.copy(stack=False)
    text = []
    for move in board.move_stack:
        if scratch.turn == chess.WHITE:
            text.append(f'{scratch.fullmove_number}.')
        elif not text:
            # A game set up from a FEN can begin on Black's move, which is
            # written "20..." so the number is not read as White's
            text.append(f'{scratch.fullmove_number}...')
        text.append(scratch.san(move))
        scratch.push(move)
    text.append(board.result(claim_draw=True))

    # Wrapped at 80 columns, as the PGN standard asks for
    wrapped = []
    row = ''
    for token in text:
        if row and len(row) + 1 + len(token) > 80:
            wrapped.append(row)
            row = token
        else:
            row = f'{row} {token}'.strip()
    if row:
        wrapped.append(row)

    return '\n'.join(lines + wrapped) + '\n'
