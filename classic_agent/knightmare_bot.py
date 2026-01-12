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

class KnightmareBot:
    def __init__(self):
        self.nodes = 0
        self.killer_moves = {}
        self.history_table = {}
        
    def evaluate(self, board):
        """Simple but reliable evaluation"""
        if board.is_checkmate():
            return -10000 if board.turn else 10000
        if board.is_stalemate():
            return 0
        if board.is_insufficient_material():
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
    
    def minimax(self, board, depth, alpha, beta, maximizing, ply=0):
        """Simplified but robust minimax"""
        self.nodes += 1
        
        if depth == 0 or board.is_game_over():
            return self.evaluate(board), None
        
        moves = list(board.legal_moves)
        if not moves:
            return self.evaluate(board), None
        
        # Order moves
        moves = self.order_moves(board, moves, ply)
        
        # Limit moves at low depth to prevent timeout
        if depth == 1:
            moves = moves[:15]
        elif depth == 2:
            moves = moves[:20]
        
        best_move = moves[0]
        
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
                    # Update killer moves
                    if not board.is_capture(move):
                        if ply not in self.killer_moves:
                            self.killer_moves[ply] = []
                        if move not in self.killer_moves[ply]:
                            self.killer_moves[ply].insert(0, move)
                            if len(self.killer_moves[ply]) > 2:
                                self.killer_moves[ply].pop()
                        
                        # Update history
                        key = (move.from_square, move.to_square)
                        if key not in self.history_table:
                            self.history_table[key] = 0
                        self.history_table[key] += depth
                    break
            
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
                    # Update killer moves
                    if not board.is_capture(move):
                        if ply not in self.killer_moves:
                            self.killer_moves[ply] = []
                        if move not in self.killer_moves[ply]:
                            self.killer_moves[ply].insert(0, move)
                            if len(self.killer_moves[ply]) > 2:
                                self.killer_moves[ply].pop()
                        
                        # Update history
                        key = (move.from_square, move.to_square)
                        if key not in self.history_table:
                            self.history_table[key] = 0
                        self.history_table[key] += depth
                    break
            
            return min_eval, best_move
    
    def get_move(self, board, time_limit=1.0):
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
        self.killer_moves.clear()  # Clear each search
        
        # Iterative deepening with time control
        try:
            for depth in range(1, 5):
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
                    print(f"info depth {depth} score cp {int(score)} nodes {self.nodes}", flush=True)
                
                # Another time check
                elapsed = time.time() - start_time
                if elapsed > time_limit * 0.8:
                    break
                    
        except Exception as e:
            print(f"info string Search error: {e}", flush=True)
        
        return best_move

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
                # Parse time limit
                time_limit = 1.0
                parts = line.split()
                
                if "movetime" in parts:
                    try:
                        idx = parts.index("movetime")
                        time_limit = int(parts[idx + 1]) / 1000.0
                        time_limit = max(0.1, min(time_limit, 5.0))
                    except:
                        time_limit = 1.0
                
                # Get move with error handling
                try:
                    move = bot.get_move(board, time_limit * 0.9)  # Keep some buffer
                    
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