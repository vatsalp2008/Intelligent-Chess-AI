#!/usr/bin/env python3
"""
Knightmare Chess Bot - Ultra Reliable Version
Focus on 100% move generation reliability and beating random bot
Author: Vatsal Patel
"""

import chess
import sys
import random
import time
import traceback

# Piece values
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# Extra credit for keeping both bishops
BISHOP_PAIR_BONUS = 30

# Score for a mate delivered at ply 0; deeper mates score slightly lower
MATE_SCORE = 10000

# Any score within this margin of MATE_SCORE is treated as a mate score
MAX_PLY = 100

# Deepest iteration the search will start when no depth is requested
DEFAULT_MAX_DEPTH = 4

# Hard ceiling for an explicitly requested search depth
MAX_SEARCH_DEPTH = 6

# Seconds to think when the go command carries no time information
DEFAULT_MOVE_TIME = 1.0

# Longest we will ever think about a single move
MAX_MOVE_TIME = 5.0

# Assumed moves left in the game when movestogo is not supplied
CLOCK_DIVISOR = 30

# How many extra plies of captures to resolve past the main search horizon
QUIESCENCE_DEPTH = 4

# Transposition table entry kinds
TT_EXACT = "exact"   # score is the true value
TT_LOWER = "lower"   # true value is at least score (search cut off high)
TT_UPPER = "upper"   # true value is at most score (search cut off low)

# Stop growing the table past this many entries
TT_MAX_ENTRIES = 200000

class KnightmareBot:
    def __init__(self):
        self.nodes = 0
        self.killer_moves = {}
        self.history_table = {}
        self.transposition_table = {}

    def store_tt(self, key, score, move, flag):
        """Cache a search result, skipping values that do not travel well

        Mate scores are relative to the ply they were found at, so caching
        them would hand back the wrong distance somewhere else in the tree.
        """
        if abs(score) >= MATE_SCORE - MAX_PLY:
            return
        if len(self.transposition_table) >= TT_MAX_ENTRIES:
            return
        self.transposition_table[key] = (score, move, flag)

    def evaluate(self, board, ply=0):
        """Simple but reliable evaluation

        Mate scores shrink with ply so a quicker mate always outranks a
        slower one, and the losing side prefers to delay mate as long as
        possible.
        """
        if board.is_checkmate():
            mate_score = MATE_SCORE - ply
            return -mate_score if board.turn else mate_score
        if board.is_stalemate():
            return 0
        if board.is_insufficient_material():
            return 0
        # Claimable draws: board.is_game_over() ignores these because they
        # need a claim, but the search must still score them as drawn.
        if board.halfmove_clock >= 100:
            return 0
        if board.is_repetition(3):
            return 0
        
        score = 0
        
        # Material count
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = PIECE_VALUES[piece.piece_type]
                
                # Simple positional bonus
                if piece.piece_type == chess.PAWN:
                    rank = chess.square_rank(square)
                    if piece.color == chess.WHITE:
                        value += rank * 5
                    else:
                        value += (7 - rank) * 5
                
                # Center bonus for knights and bishops
                if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                    file = chess.square_file(square)
                    rank = chess.square_rank(square)
                    center_dist = abs(3.5 - file) + abs(3.5 - rank)
                    value += int((7 - center_dist) * 2)
                
                if piece.color == chess.WHITE:
                    score += value
                else:
                    score -= value
        
        # Bishop pair is worth a small bonus in most positions
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += BISHOP_PAIR_BONUS
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= BISHOP_PAIR_BONUS

        # Mobility bonus
        mobility = len(list(board.legal_moves)) * 3
        score += mobility if board.turn == chess.WHITE else -mobility

        return score
    
    def order_moves(self, board, moves, ply=0):
        """Simple but effective move ordering"""
        scored = []
        
        for move in moves:
            score = 0
            
            # Captures - MVV-LVA
            if board.is_capture(move):
                victim = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                if victim and attacker:
                    score += 1000 + PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]//10
            
            # Promotions
            if move.promotion:
                score += 900
            
            # Checks
            board.push(move)
            if board.is_check():
                score += 500
            board.pop()
            
            # Killer moves
            if ply in self.killer_moves and move in self.killer_moves[ply]:
                score += 400
            
            # History heuristic
            key = (move.from_square, move.to_square)
            if key in self.history_table:
                score += min(self.history_table[key], 300)
            
            # Center moves
            if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
                score += 30
            
            scored.append((score, move))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]
    
    def record_cutoff(self, board, move, depth, ply):
        """Store a quiet move that caused a beta cutoff for later ordering"""
        if board.is_capture(move):
            return

        killers = self.killer_moves.setdefault(ply, [])
        if move not in killers:
            killers.insert(0, move)
            if len(killers) > 2:
                killers.pop()

        key = (move.from_square, move.to_square)
        self.history_table[key] = self.history_table.get(key, 0) + depth

    def quiesce(self, board, alpha, beta, ply, depth=QUIESCENCE_DEPTH):
        """Search only captures until the position is quiet

        Stopping a search in the middle of a capture sequence badly
        misjudges the position, so keep resolving captures before handing
        the score back to the main search.
        """
        self.nodes += 1

        if board.is_game_over():
            return self.evaluate(board, ply)

        stand_pat = self.evaluate(board, ply)
        if depth == 0:
            return stand_pat

        white_to_move = board.turn == chess.WHITE

        # The side to move can decline all captures and keep stand_pat
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

        for move in self.order_moves(board, captures, ply):
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
        """Simplified but robust minimax"""
        self.nodes += 1

        if board.is_game_over():
            return self.evaluate(board, ply), None

        if depth == 0:
            return self.quiesce(board, alpha, beta, ply), None

        # A position reached by different move orders only needs searching once.
        # Stored scores may be bounds rather than exact values, so a cached
        # entry is only reusable when it still settles the current window.
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

        moves = list(board.legal_moves)
        if not moves:
            return self.evaluate(board, ply), None

        # Order moves
        moves = self.order_moves(board, moves, ply)

        # Limit moves at low depth to prevent timeout
        if depth == 1:
            moves = moves[:15]
        elif depth == 2:
            moves = moves[:20]

        best_move = moves[0]

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
                    self.record_cutoff(board, move, depth, ply)
                    cut_off = True
                    break

            # An early exit means max_eval is only a lower bound on the truth
            flag = TT_LOWER if cut_off else TT_EXACT
            self.store_tt(tt_key, max_eval, best_move, flag)
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
                    self.record_cutoff(board, move, depth, ply)
                    cut_off = True
                    break

            # An early exit means min_eval is only an upper bound on the truth
            flag = TT_UPPER if cut_off else TT_EXACT
            self.store_tt(tt_key, min_eval, best_move, flag)
            return min_eval, best_move
    
    def get_move(self, board, time_limit=1.0, max_depth=DEFAULT_MAX_DEPTH):
        """Get best move with guaranteed return"""
        start_time = time.time()
        
        # Get all legal moves
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
                return move
            board.pop()
        
        # Default to first legal move (will be replaced by search)
        best_move = legal_moves[0]
        
        # Clear tables if too large
        if len(self.history_table) > 5000:
            self.history_table.clear()
        if len(self.transposition_table) >= TT_MAX_ENTRIES:
            self.transposition_table.clear()
        self.killer_moves.clear()  # Clear each search
        
        # Iterative deepening with time control
        try:
            for depth in range(1, max_depth + 1):
                self.nodes = 0
                
                # Time check
                elapsed = time.time() - start_time
                if elapsed > time_limit * 0.7:
                    break
                
                # Search with timeout protection
                maximizing = board.turn == chess.WHITE
                score, move = self.minimax(board, depth, -float('inf'), float('inf'), maximizing)
                
                if move and move in legal_moves:
                    best_move = move
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    nps = int(self.nodes / max(elapsed_ms / 1000.0, 0.001))
                    print(
                        f"info depth {depth} score {format_score(score)} "
                        f"nodes {self.nodes} time {elapsed_ms} nps {nps}",
                        flush=True,
                    )
                
                # Another time check
                elapsed = time.time() - start_time
                if elapsed > time_limit * 0.8:
                    break
                    
        except Exception as e:
            print(f"info string Search error: {e}", flush=True)
        
        return best_move

def format_score(score):
    """Render a search score the way UCI expects

    Mate scores are reported as a distance in moves rather than as a very
    large centipawn value.
    """
    if abs(score) >= MATE_SCORE - MAX_PLY:
        plies_to_mate = MATE_SCORE - abs(score)
        moves_to_mate = max(1, (plies_to_mate + 1) // 2)
        return f"mate {moves_to_mate if score > 0 else -moves_to_mate}"
    return f"cp {int(score)}"


def token_value(parts, name):
    """Return the integer argument following a go token, if it is present"""
    if name not in parts:
        return None
    idx = parts.index(name)
    if idx + 1 >= len(parts):
        return None
    try:
        return int(parts[idx + 1])
    except ValueError:
        return None


def clock_budget(parts, white_to_move):
    """Seconds to spend from a remaining-clock style go command

    Spends a modest fraction of the remaining time plus most of the
    increment, which keeps the engine from flagging in long games.
    """
    remaining = token_value(parts, "wtime" if white_to_move else "btime")
    if remaining is None:
        return None

    increment = token_value(parts, "winc" if white_to_move else "binc") or 0
    moves_to_go = token_value(parts, "movestogo") or CLOCK_DIVISOR

    budget_ms = remaining / max(1, moves_to_go) + increment * 0.8
    # Never commit more than a fraction of what is actually left
    budget_ms = min(budget_ms, remaining * 0.4)
    return max(0.05, min(budget_ms / 1000.0, MAX_MOVE_TIME))


def parse_go(line, white_to_move=True):
    """Work out a (time_limit_seconds, max_depth) budget for a go command"""
    parts = line.split()

    time_limit = DEFAULT_MOVE_TIME
    max_depth = DEFAULT_MAX_DEPTH

    clock = clock_budget(parts, white_to_move)
    if clock is not None:
        time_limit = clock

    movetime = token_value(parts, "movetime")
    if movetime is not None:
        time_limit = max(0.1, min(movetime / 1000.0, 5.0))

    depth = token_value(parts, "depth")
    if depth is not None and depth > 0:
        max_depth = min(depth, MAX_SEARCH_DEPTH)
        # An explicit depth should not be cut short by the default clock
        if movetime is None:
            time_limit = MAX_MOVE_TIME

    if "infinite" in parts:
        time_limit = MAX_MOVE_TIME

    return time_limit, max_depth


def parse_position(line):
    """Parse position command and return board"""
    board = chess.Board()
    parts = line.split()
    
    try:
        if "startpos" in parts:
            board = chess.Board()
            
            if "moves" in parts:
                moves_idx = parts.index("moves") + 1
                for uci_str in parts[moves_idx:]:
                    try:
                        move = chess.Move.from_uci(uci_str)
                        if move in board.legal_moves:
                            board.push(move)
                    except:
                        break
        
        elif "fen" in parts:
            fen_idx = parts.index("fen") + 1
            fen_parts = []
            
            # Collect FEN string parts
            for i in range(fen_idx, len(parts)):
                if parts[i] == "moves":
                    break
                fen_parts.append(parts[i])
            
            fen = " ".join(fen_parts)
            board = chess.Board(fen)
            
            if "moves" in parts:
                moves_idx = parts.index("moves") + 1
                for uci_str in parts[moves_idx:]:
                    try:
                        move = chess.Move.from_uci(uci_str)
                        if move in board.legal_moves:
                            board.push(move)
                    except:
                        break
    except:
        board = chess.Board()
    
    return board

def main():
    """Main UCI loop"""
    bot = KnightmareBot()
    board = chess.Board()
    
    while True:
        try:
            line = sys.stdin.readline().strip()
            
            if not line:
                continue
            
            if line == "uci":
                print("id name Knightmare Reliable")
                print("id author Vatsal Patel")
                print("uciok")
                sys.stdout.flush()
            
            elif line == "isready":
                print("readyok")
                sys.stdout.flush()
            
            elif line == "ucinewgame":
                board = chess.Board()
                bot = KnightmareBot()
            
            elif line.startswith("position"):
                board = parse_position(line)
            
            elif line.startswith("go"):
                time_limit, max_depth = parse_go(line, board.turn == chess.WHITE)

                # Get move with error handling
                try:
                    # Keep some buffer
                    move = bot.get_move(board, time_limit * 0.9, max_depth)
                    
                    # Validate move
                    if move and move in board.legal_moves:
                        print(f"bestmove {move.uci()}")
                    else:
                        # Fallback to any legal move
                        legal_moves = list(board.legal_moves)
                        if legal_moves:
                            print(f"bestmove {legal_moves[0].uci()}")
                        else:
                            print("bestmove 0000")
                    
                except Exception as e:
                    # Emergency fallback
                    print(f"info string Emergency: {e}", flush=True)
                    legal_moves = list(board.legal_moves)
                    if legal_moves:
                        print(f"bestmove {random.choice(legal_moves).uci()}")
                    else:
                        print("bestmove 0000")
                
                sys.stdout.flush()
            
            elif line == "quit":
                break
                
        except EOFError:
            break
        except Exception as e:
            print(f"info string Error: {e}", flush=True)
            sys.stdout.flush()

if __name__ == "__main__":
    try:
        main()
    except:
        sys.exit(0)