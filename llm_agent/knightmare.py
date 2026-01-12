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
from collections import defaultdict

# Enhanced piece values
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# Simplified piece-square tables
def get_piece_square_value(piece_type, square, color, endgame=False):
    """Get positional value for a piece on a square"""
    # Simple center bonus
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    
    center_distance = abs(3.5 - file) + abs(3.5 - rank)
    center_bonus = int((7 - center_distance) * 5)
    
    if piece_type == chess.PAWN:
        # Pawns get bonus for advancement
        if color == chess.WHITE:
            return rank * 10 + center_bonus
        else:
            return (7 - rank) * 10 + center_bonus
    elif piece_type == chess.KING:
        if endgame:
            # King should be active in endgame
            return center_bonus
        else:
            # King should be safe in middlegame
            if color == chess.WHITE:
                if square in [chess.G1, chess.C1, chess.B1]:
                    return 30
            else:
                if square in [chess.G8, chess.C8, chess.B8]:
                    return 30
            return -center_bonus
    else:
        # Other pieces benefit from central positions
        return center_bonus

class KnightmareFast:
    def __init__(self):
        self.reset()
        
    def reset(self):
        """Reset the bot state"""
        self.nodes = 0
        self.transposition_table = {}
        self.opening_book = self.create_simple_opening_book()
        
    def create_simple_opening_book(self):
        """Create a simple, reliable opening book"""
        return {
            # Starting position - only include moves we know are legal
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1": [
                "e2e4", "d2d4", "g1f3"
            ],
            # After 1.e4
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1": [
                "e7e5", "c7c5", "e7e6"
            ],
            # After 1.d4
            "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1": [
                "d7d5", "g8f6"
            ],
        }
        
    def is_endgame(self, board):
        """Determine if we're in endgame phase"""
        # Count major pieces
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
        minors = (len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(board.pieces(chess.BISHOP, chess.WHITE)) +
                 len(board.pieces(chess.KNIGHT, chess.BLACK)) + len(board.pieces(chess.BISHOP, chess.BLACK)))
        
        # Endgame if no queens or very few pieces
        return queens == 0 or (queens + rooks + minors) <= 6
    
    def evaluate_board(self, board):
        """Simplified but robust evaluation function"""
        if board.is_checkmate():
            return -30000 if board.turn else 30000
        
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        
        if board.can_claim_fifty_moves():
            return 0
            
        score = 0
        endgame = self.is_endgame(board)
        
        # Material evaluation
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                piece_value = PIECE_VALUES[piece.piece_type]
                position_value = get_piece_square_value(
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
        
        return score if board.turn == chess.WHITE else -score
    
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
    
    def minimax(self, board, depth, alpha, beta, maximizing):
        """Simple minimax with alpha-beta pruning"""
        self.nodes += 1
        
        # Terminal conditions
        if depth == 0 or board.is_game_over():
            return self.evaluate_board(board), None
        
        # Get legal moves
        moves = list(board.legal_moves)
        if not moves:
            return self.evaluate_board(board), None
        
        # Order moves for better pruning
        if depth > 1:
            moves = self.order_moves(board, moves)
        
        # Limit moves at low depths to save time
        if depth <= 2 and len(moves) > 10:
            moves = moves[:10]
        
        best_move = moves[0] if moves else None
        
        if maximizing:
            max_eval = -float('inf')
            for move in moves:
                board.push(move)
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            
            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in moves:
                board.push(move)
                eval_score, _ = self.minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move
                
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            
            return min_eval, best_move
    
    def get_best_move(self, board, max_time=2.0):
        """Get best move - CRITICAL: This must return a legal move from the given board"""
        start_time = time.time()
        
        # CRITICAL: Get legal moves from the actual board position
        legal_moves = list(board.legal_moves)
        
        if not legal_moves:
            print("No legal moves available!")
            return None
        
        if len(legal_moves) == 1:
            return legal_moves[0]
        
        # Try opening book ONLY if the position matches exactly
        fen = board.fen()
        if fen in self.opening_book and board.fullmove_number <= 5:
            book_moves = []
            for move_uci in self.opening_book[fen]:
                try:
                    move = chess.Move.from_uci(move_uci)
                    # CRITICAL: Verify the book move is legal in current position
                    if move in legal_moves:
                        book_moves.append(move)
                except:
                    pass
            
            if book_moves:
                chosen = random.choice(book_moves)
                print(f"Using opening book move: {chosen}")
                return chosen
        
        # Check for immediate checkmate
        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                print(f"Found checkmate: {move}")
                return move
            board.pop()
        
        # Use minimax to find best move
        # CRITICAL: Create a fresh copy for search
        search_board = board.copy()
        
        best_move = legal_moves[0]  # Default to first legal move
        best_eval = -float('inf') if board.turn == chess.WHITE else float('inf')
        
        # Iterative deepening
        max_depth = 4
        for depth in range(1, max_depth + 1):
            self.nodes = 0
            
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
                    if search_board.turn == chess.WHITE:
                        if eval_score > best_eval:
                            best_move = move
                            best_eval = eval_score
                    else:
                        if eval_score < best_eval:
                            best_move = move
                            best_eval = eval_score
                
                # Time check
                if time.time() - start_time > max_time * 0.5:
                    break
                    
            except Exception as e:
                print(f"Error in minimax at depth {depth}: {e}")
                break
        
        # FINAL SAFETY CHECK: Ensure we return a legal move
        if best_move not in legal_moves:
            print(f"WARNING: Best move {best_move} not legal, using fallback")
            best_move = legal_moves[0]
        
        return best_move

# Global variables for UCI
global_bot = None
global_board = chess.Board()

def uci(msg):
    """UCI protocol handler"""
    global global_board, global_bot
    
    if msg == "uci":
        print("id name Knightmare")
        print("id author CS5100 Student")
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
                        except:
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
                            except:
                                pass
            except:
                print("info string Invalid FEN, using startpos")
                global_board = chess.Board()
                
    elif msg.startswith("go"):
        if global_bot is None:
            global_bot = KnightmareFast()
        
        # Parse time control
        max_time = 2.0
        parts = msg.split()
        
        if "movetime" in parts:
            idx = parts.index("movetime")
            if idx + 1 < len(parts):
                try:
                    max_time = int(parts[idx + 1]) / 1000.0
                except:
                    pass
        
        # Get best move
        move = global_bot.get_best_move(global_board, max_time)
        
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