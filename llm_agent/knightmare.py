#!/usr/bin/env python3
"""
Knightmare Chess Bot - Robust Version
Fixed to prevent illegal moves and maintain correct board state
Author: Vatsal Patel
"""

import chess
import sys
import random
import time

# Enhanced piece values
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# Transposition table entry kinds
TT_EXACT = "exact"   # score is the true value
TT_LOWER = "lower"   # true value is at least score (search cut off high)
TT_UPPER = "upper"   # true value is at most score (search cut off low)

# Stop growing the table past this many entries
TT_MAX_ENTRIES = 200000

# Extra plies of captures resolved past the main search horizon
QUIESCENCE_DEPTH = 4

# Deepest iteration started when no depth is requested
DEFAULT_MAX_DEPTH = 4

# Roughly how much more work each extra ply costs, used to decide whether
# the next iteration will fit in the time that is left
BRANCHING_ESTIMATE = 4.0

# Hard ceiling for an explicitly requested search depth
MAX_SEARCH_DEPTH = 6

# Seconds to think when the go command carries no time information
DEFAULT_MOVE_TIME = 2.0

# Longest we will ever think about a single move
MAX_MOVE_TIME = 10.0

# Stop consulting the opening book after this many full moves
BOOK_MAX_FULLMOVES = 5

# Score for a mate delivered at ply 0; deeper mates score slightly lower
MATE_SCORE = 30000

# Scores within this margin of MATE_SCORE count as mate scores
MAX_PLY = 100

# Piece-square tables, written from White's point of view with rank 8 on the
# first row so they read like a board. Values are centipawn adjustments on
# top of the piece value. Black looks them up through a mirrored square.
#
# These tables are duplicated in classic_agent/knightmare_bot.py. The two engines
# are separate top level scripts with no shared package between them, so
# there is nowhere to import from; if you tune a table here, tune it there
# too or the two engines will quietly disagree.
PAWN_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]

KNIGHT_TABLE = [
   -50, -40, -30, -30, -30, -30, -40, -50,
   -40, -20,   0,   0,   0,   0, -20, -40,
   -30,   0,  10,  15,  15,  10,   0, -30,
   -30,   5,  15,  20,  20,  15,   5, -30,
   -30,   0,  15,  20,  20,  15,   0, -30,
   -30,   5,  10,  15,  15,  10,   5, -30,
   -40, -20,   0,   5,   5,   0, -20, -40,
   -50, -40, -30, -30, -30, -30, -40, -50,
]

BISHOP_TABLE = [
   -20, -10, -10, -10, -10, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,  10,  10,   5,   0, -10,
   -10,   5,   5,  10,  10,   5,   5, -10,
   -10,   0,  10,  10,  10,  10,   0, -10,
   -10,  10,  10,  10,  10,  10,  10, -10,
   -10,   5,   0,   0,   0,   0,   5, -10,
   -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0,
]

QUEEN_TABLE = [
   -20, -10, -10,  -5,  -5, -10, -10, -20,
   -10,   0,   0,   0,   0,   0,   0, -10,
   -10,   0,   5,   5,   5,   5,   0, -10,
    -5,   0,   5,   5,   5,   5,   0,  -5,
     0,   0,   5,   5,   5,   5,   0,  -5,
   -10,   5,   5,   5,   5,   5,   0, -10,
   -10,   0,   5,   0,   0,   0,   0, -10,
   -20, -10, -10,  -5,  -5, -10, -10, -20,
]

# The king wants shelter early on and activity once the queens come off
KING_MIDDLEGAME_TABLE = [
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -20, -30, -30, -40, -40, -30, -30, -20,
   -10, -20, -20, -20, -20, -20, -20, -10,
    20,  20,   0,   0,   0,   0,  20,  20,
    20,  30,  10,   0,   0,  10,  30,  20,
]

KING_ENDGAME_TABLE = [
   -50, -40, -30, -20, -20, -30, -40, -50,
   -30, -20, -10,   0,   0, -10, -20, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  30,  40,  40,  30, -10, -30,
   -30, -10,  20,  30,  30,  20, -10, -30,
   -30, -30,   0,   0,   0,   0, -30, -30,
   -50, -30, -30, -30, -30, -30, -30, -50,
]

PIECE_SQUARE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_MIDDLEGAME_TABLE,
}


def square_index(square, color):
    """Index into a piece-square table for the given side

    The tables are written with rank 8 first, so White reads them upside
    down and Black reads them through a vertical mirror.
    """
    if color == chess.WHITE:
        return chess.square_mirror(square)
    return square






def piece_square_bonus(piece_type, square, color, endgame=False):
    """Positional bonus for a piece standing on a square"""
    if piece_type == chess.KING and endgame:
        table = KING_ENDGAME_TABLE
    else:
        table = PIECE_SQUARE_TABLES[piece_type]
    return table[square_index(square, color)]


def format_score(score):
    """Render a search score the way UCI expects

    Mate scores are reported as a distance in moves rather than as a very
    large centipawn number.
    """
    if abs(score) >= MATE_SCORE - MAX_PLY:
        plies_to_mate = MATE_SCORE - abs(score)
        moves_to_mate = max(1, (plies_to_mate + 1) // 2)
        return f"mate {moves_to_mate if score > 0 else -moves_to_mate}"
    return f"cp {int(score)}"


class KnightmareFast:
    def __init__(self):
        self.reset()
        
    def reset(self):
        """Reset the bot state"""
        self.nodes = 0
        self.transposition_table = {}
        self.opening_book = self.create_simple_opening_book()
        
    def create_simple_opening_book(self):
        """Build the opening book, keyed by position

        The lines are written as move sequences and replayed once to key
        them by position. Keying on a FEN string does not work: python-chess
        omits the en passant square when no en passant capture is actually
        possible, so a hand written FEN with "e3" in it never matches the
        position it describes. Keying on the position also makes
        transpositions work and covers boards built from a FEN, which have
        no move history at all.
        """
        lines = {
            # First move as White
            (): ["e2e4", "d2d4", "g1f3"],
            # After 1.e4
            ("e2e4",): ["e7e5", "c7c5", "e7e6"],
            # After 1.d4
            ("d2d4",): ["d7d5", "g8f6"],
        }

        book = {}
        for moves, replies in lines.items():
            board = chess.Board()
            for uci in moves:
                board.push(chess.Move.from_uci(uci))
            legal = [
                chess.Move.from_uci(uci)
                for uci in replies
                if chess.Move.from_uci(uci) in board.legal_moves
            ]
            if legal:
                book[board._transposition_key()] = legal
        return book
        
    def store_tt(self, key, score, move, flag):
        """Cache a search result, keeping the table to a sane size

        Mate scores are relative to the ply they were found at, so caching
        them would hand back the wrong distance elsewhere in the tree.
        """
        if abs(score) >= MATE_SCORE - MAX_PLY:
            return
        if len(self.transposition_table) >= TT_MAX_ENTRIES:
            return
        self.transposition_table[key] = (score, move, flag)

    def is_endgame(self, board):
        """Determine if we're in endgame phase"""
        # Count major pieces
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
        minors = (len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.WHITE)) +
                 len(board.pieces(chess.KNIGHT, chess.BLACK)) + len(board.pieces(chess.BISHOP, chess.BLACK)))
        
        # Endgame if no queens or very few pieces
        return queens == 0 or (queens + rooks + minors) <= 6
    
    def evaluate_board(self, board, ply=0):
        """Simplified but robust evaluation function

        Scores are absolute: positive favours White regardless of whose
        turn it is. minimax() maximizes for White and minimizes for Black,
        so a side-relative score here would flip sign every ply and make
        the search compare incompatible numbers.

        Mate scores shrink with ply so a quicker mate outranks a slower one
        and the losing side puts mate off as long as it can.
        """
        if board.is_checkmate():
            mate_score = MATE_SCORE - ply
            return -mate_score if board.turn else mate_score

        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        if board.can_claim_fifty_moves():
            return 0

        # A threefold repetition is a draw the opponent can claim, but
        # board.is_game_over() ignores it because it needs claiming. Without
        # this the engine reads a repetition in a won position as still won
        # and happily shuffles the win away.
        if board.is_repetition(3):
            return 0
            
        score = 0
        endgame = self.is_endgame(board)
        
        # Material evaluation
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                piece_value = PIECE_VALUES[piece.piece_type]
                position_value = piece_square_bonus(
                    piece.piece_type, square, piece.color, endgame
                )
                
                if piece.color == chess.WHITE:
                    score += piece_value + position_value
                else:
                    score -= piece_value + position_value
        
        # Simple mobility evaluation
        if not board.is_game_over():
            current_mobility = len(list(board.legal_moves))
            score += current_mobility * 5 if board.turn == chess.WHITE else -current_mobility * 5

        return score
    
    def order_moves(self, board, moves):
        """Simple move ordering for better alpha-beta pruning"""
        move_scores = []
        
        for move in moves:
            score = 0
            
            # Captures are good
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                if victim:
                    score += PIECE_VALUES[victim.piece_type]
            
            # Promotions are excellent
            if move.promotion:
                score += 900
            
            # Checks are good
            board.push(move)
            if board.is_check():
                score += 50
            board.pop()
            
            move_scores.append((move, score))
        
        move_scores.sort(key=lambda x: x[1], reverse=True)
        return [move for move, _ in move_scores]
    
    def quiesce(self, board, alpha, beta, ply=0, depth=QUIESCENCE_DEPTH):
        """Keep resolving captures before scoring the position

        Stopping in the middle of a trade reads the position as if the
        recapture will never happen, which makes the engine hang pieces.
        """
        self.nodes += 1

        if board.is_game_over():
            return self.evaluate_board(board, ply)

        stand_pat = self.evaluate_board(board, ply)
        if depth == 0:
            return stand_pat

        white_to_move = board.turn == chess.WHITE

        # The side to move can always decline and keep the standing score
        if white_to_move:
            if stand_pat >= beta:
                return stand_pat
            alpha = max(alpha, stand_pat)
        else:
            if stand_pat <= alpha:
                return stand_pat
            beta = min(beta, stand_pat)

        captures = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        if not captures:
            return stand_pat

        for move in self.order_moves(board, captures):
            board.push(move)
            score = self.quiesce(board, alpha, beta, ply + 1, depth - 1)
            board.pop()

            if white_to_move:
                if score >= beta:
                    return score
                alpha = max(alpha, score)
            else:
                if score <= alpha:
                    return score
                beta = min(beta, score)

        return alpha if white_to_move else beta

    def minimax(self, board, depth, alpha, beta, maximizing, ply=0):
        """Simple minimax with alpha-beta pruning"""
        self.nodes += 1

        # Terminal conditions
        if board.is_game_over():
            return self.evaluate_board(board, ply), None

        if depth == 0:
            return self.quiesce(board, alpha, beta, ply), None

        # Reuse an earlier search of this position when the stored score
        # still decides the current window. Values from a cut-off search
        # are only bounds, so they cannot be trusted unconditionally.
        tt_key = (board._transposition_key(), depth)
        cached = self.transposition_table.get(tt_key)
        if cached is not None:
            score, move, flag = cached
            if flag == TT_EXACT:
                return score, move
            if flag == TT_LOWER and score >= beta:
                return score, move
            if flag == TT_UPPER and score <= alpha:
                return score, move

        # Get legal moves
        moves = list(board.legal_moves)
        if not moves:
            return self.evaluate_board(board, ply), None

        # Order moves for better pruning. This has to happen before the
        # shallow-depth cut below, otherwise the cut keeps ten arbitrary
        # moves and can throw the best one away.
        moves = self.order_moves(board, moves)

        best_move = moves[0] if moves else None
        cut_off = False

        if maximizing:
            max_eval = -float('inf')
            for move in moves:
                board.push(move)
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, False, ply + 1)
                board.pop()

                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move

                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    cut_off = True
                    break

            self.store_tt(tt_key, max_eval, best_move, TT_LOWER if cut_off else TT_EXACT)
            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in moves:
                board.push(move)
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, True, ply + 1)
                board.pop()

                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move

                beta = min(beta, eval_score)
                if beta <= alpha:
                    cut_off = True
                    break

            self.store_tt(tt_key, min_eval, best_move, TT_UPPER if cut_off else TT_EXACT)
            return min_eval, best_move
    
    def get_best_move(self, board, max_time=2.0, max_depth=DEFAULT_MAX_DEPTH):
        """Get best move - CRITICAL: This must return a legal move from the given board"""
        start_time = time.time()
        
        # CRITICAL: Get legal moves from the actual board position
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            print("info string No legal moves available")
            return None
        
        if len(legal_moves) == 1:
            return legal_moves[0]
        
        # Check for immediate checkmate. This runs before the book so a
        # book reply can never talk the engine out of a forced win.
        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                print(f"info string Found checkmate {move}")
                return move
            board.pop()

        # Known theory for the opening, looked up by position
        if board.fullmove_number <= BOOK_MAX_FULLMOVES:
            replies = self.opening_book.get(board._transposition_key())
            if replies:
                book_moves = [move for move in replies if move in legal_moves]
                if book_moves:
                    chosen = random.choice(book_moves)
                    print(f"info string Using opening book move {chosen}")
                    return chosen
        
        # Use minimax to find best move
        # CRITICAL: Create a fresh copy for search
        search_board = board.copy()
        
        best_move = legal_moves[0]  # Default to first legal move

        # Iterative deepening. Scores from different depths are not
        # comparable, so always trust the deepest completed iteration
        # rather than keeping the best-looking score seen so far.
        last_iteration = None

        for depth in range(1, max_depth + 1):
            self.nodes = 0
            iteration_start = time.time()
            elapsed = iteration_start - start_time

            # Starting an iteration that cannot finish wastes the rest of
            # the budget and its result is discarded anyway, so predict the
            # cost from how long the previous depth actually took.
            if last_iteration is not None:
                if elapsed + last_iteration * BRANCHING_ESTIMATE > max_time:
                    break

            try:
                eval_score, move = self.minimax(
                    search_board,
                    depth,
                    -float('inf'),
                    float('inf'),
                    search_board.turn == chess.WHITE
                )

                # CRITICAL: Verify the returned move is legal
                if move and move in legal_moves:
                    best_move = move
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    nps = int(self.nodes / max(elapsed_ms / 1000.0, 0.001))
                    print(
                        f"info depth {depth} score {format_score(eval_score)} "
                        f"nodes {self.nodes} time {elapsed_ms} nps {nps} "
                        f"pv {move.uci()}",
                        flush=True,
                    )

                last_iteration = time.time() - iteration_start

            except Exception as e:
                print(f"info string Error in minimax at depth {depth}: {e}")
                break
        
        # FINAL SAFETY CHECK: Ensure we return a legal move
        if best_move not in legal_moves:
            print(f"info string Best move {best_move} not legal, using fallback")
            best_move = legal_moves[0]
        
        return best_move

def token_value(parts, name):
    """The integer argument following a go token, if it is present"""
    if name not in parts:
        return None
    idx = parts.index(name)
    if idx + 1 >= len(parts):
        return None
    try:
        return int(parts[idx + 1])
    except ValueError:
        return None


def parse_go(msg):
    """Work out a (seconds, max_depth) budget for a go command"""
    parts = msg.split()

    max_time = DEFAULT_MOVE_TIME
    max_depth = DEFAULT_MAX_DEPTH

    movetime = token_value(parts, "movetime")
    if movetime is not None:
        max_time = max(0.1, movetime / 1000.0)

    depth = token_value(parts, "depth")
    if depth is not None and depth > 0:
        max_depth = min(depth, MAX_SEARCH_DEPTH)
        # An explicit depth should not be cut short by the default clock
        if movetime is None:
            max_time = MAX_MOVE_TIME

    if "infinite" in parts:
        max_time = MAX_MOVE_TIME

    return max_time, max_depth


# Global variables for UCI
global_bot = None
global_board = chess.Board()

def uci(msg):
    """UCI protocol handler"""
    global global_board, global_bot
    
    if msg == "uci":
        print("id name Knightmare")
        print("id author Vatsal Patel")
        print("uciok")
        sys.stdout.flush()
        
    elif msg == "isready":
        if global_bot is None:
            global_bot = KnightmareFast()
        print("readyok")
        sys.stdout.flush()
        
    elif msg == "ucinewgame":
        global_board = chess.Board()
        if global_bot:
            global_bot.reset()
        
    elif msg.startswith("position"):
        # Parse position command
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
                            else:
                                print(f"info string Illegal move in position: {move_uci}")
                        except ValueError:
                            print(f"info string Invalid move format: {move_uci}")
        
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
                            except ValueError:
                                pass
            except ValueError:
                print("info string Invalid FEN, using startpos")
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = KnightmareFast()
        
        max_time, max_depth = parse_go(msg)

        # Get best move
        move = global_bot.get_best_move(global_board, max_time, max_depth)
        
        if move and move in global_board.legal_moves:
            print(f"bestmove {move}")
        else:
            # Emergency: just pick first legal move
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
    # Check for draw argument
    if len(sys.argv) > 1 and sys.argv[1] == 'draw':
        try:
            from standalone_tree_viz import main as viz_main
            viz_main()
        except ImportError:
            print("Tree visualization module not found")
        sys.exit(0)
    
    # Run UCI loop
    global global_bot
    global_bot = KnightmareFast()
    
    try:
        while True:
            line = input().strip()
            if line:
                uci(line)
    except (EOFError, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    main()