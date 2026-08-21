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

# Piece values
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# Extra credit for keeping both bishops. Raised from 30 after tune_eval.py
# pointed at a higher value and selfplay.py confirmed 50 (60% over 24 games).
# The tuner's own suggestion of 200 only scored 56% and is far above what a
# bishop pair is actually worth, so the proxy overshot the magnitude.
BISHOP_PAIR_BONUS = 50

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

# Roughly how much more work each extra ply costs, used to decide whether
# the next iteration will fit in the time that is left
BRANCHING_ESTIMATE = 4.0

# How many nodes to search between clock checks. Calling time.time() on
# every node is measurable overhead at these node rates, and a few thousand
# nodes is well under a millisecond of extra work.
CLOCK_CHECK_INTERVAL = 2048

# How many extra plies of captures to resolve past the main search horizon.
# Measured: 2 scored 42% and 6 scored 44% against this value over 24 games,
# so 4 is already near the sweet spot. Shallower misses recaptures, deeper
# costs more than the extra accuracy is worth at this search depth.
QUIESCENCE_DEPTH = 4

# Transposition table entry kinds
TT_EXACT = "exact"   # score is the true value
TT_LOWER = "lower"   # true value is at least score (search cut off high)
TT_UPPER = "upper"   # true value is at most score (search cut off low)

# Stop growing the table past this many entries
TT_MAX_ENTRIES = 200000

# History entries kept before the scores are aged down
HISTORY_MAX_ENTRIES = 5000

# Rooks, queens and minors left before a position counts as an endgame
ENDGAME_PIECE_COUNT = 6

# Bonus for a passed pawn, indexed by how many ranks it has advanced.
# A pawn one step from promoting is worth far more than one still at home.
PASSED_PAWN_BONUS = [0, 10, 20, 35, 60, 100, 150, 0]

# Pawns stacked on the same file get in each other's way
DOUBLED_PAWN_PENALTY = 15

# A pawn with no friendly pawn on either neighbouring file is hard to defend
ISOLATED_PAWN_PENALTY = 12

# Rook on a file with no pawns at all
ROOK_OPEN_FILE_BONUS = 20

# Rook on a file holding only enemy pawns
ROOK_HALF_OPEN_FILE_BONUS = 10

# Charged per file around the king with no friendly pawn on it
KING_SHIELD_PENALTY = 12

# Stop consulting the opening book after this many full moves
BOOK_MAX_FULLMOVES = 5

# Shallowest depth at which a null move search is worth trying
NULL_MOVE_MIN_DEPTH = 4

# Plies shaved off the null move search, since it only needs to be a probe.
# Measured over three middlegame positions at depth 5: 2 was fastest every
# time, with the same move chosen throughout. A reduction of 1 searches the
# probe too deeply; 3 makes it too shallow to prove the cutoff, so the real
# search happens anyway.
NULL_MOVE_REDUCTION = 2

# The best move from a previous search of this position, tried before all else
TT_MOVE_SCORE = 10000

# Captures that lose material are ordered below every quiet move
LOSING_CAPTURE_SCORE = -1000

# Values used when playing out an exchange. The king is given a huge value
# so it is only ever used as a last resort recapture.
SEE_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10000,
}

# Piece-square tables, written from White's point of view with rank 8 on the
# first row so they read like a board. Values are centipawn adjustments on
# top of the piece value. Black looks them up through a mirrored square.
#
# These tables are duplicated in llm_agent/knightmare.py. The two engines
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


def static_exchange_eval(board, move):
    """Material won or lost by playing a capture and letting it play out

    Plays the whole exchange on the target square, each side always
    recapturing with its cheapest attacker, and returns the net centipawn
    gain for the side making the move. A negative result means the capture
    loses material, which the search can then avoid without searching it.
    """
    target = move.to_square
    captured = board.piece_at(target)

    # En passant takes a pawn that is not standing on the target square
    if captured is None:
        if not board.is_en_passant(move):
            return 0
        gain = SEE_PIECE_VALUES[chess.PAWN]
    else:
        gain = SEE_PIECE_VALUES[captured.piece_type]

    attacker = board.piece_at(move.from_square)
    if attacker is None:
        return 0

    # Work on a copy: the exchange is simulated, not played for real
    scratch = board.copy(stack=False)
    scratch.push(move)

    # gains[i] is the running material balance after i captures
    gains = [gain]
    on_square = attacker.piece_type
    side = not board.turn

    while True:
        capture = cheapest_attacker_move(scratch, target, side)
        if capture is None:
            break

        gains.append(SEE_PIECE_VALUES[on_square] - gains[-1])
        on_square = scratch.piece_at(capture.from_square).piece_type
        scratch.push(capture)
        side = not side

    # Walk back up: each side stops capturing when the exchange turns bad
    for i in range(len(gains) - 2, -1, -1):
        gains[i] = -max(-gains[i], gains[i + 1])

    return gains[0]


def cheapest_attacker_move(board, target, color):
    """The least valuable legal capture of target by color, if any

    Asking the board which pieces attack the square is far cheaper than
    generating every legal move and filtering, which matters because this
    runs for each step of every exchange the search looks at.
    """
    candidates = []
    for square in board.attackers(color, target):
        piece = board.piece_at(square)
        if piece is not None:
            candidates.append((SEE_PIECE_VALUES[piece.piece_type], square))

    # Cheapest first, but attackers() ignores pins so legality still counts
    for _, square in sorted(candidates):
        move = chess.Move(square, target)
        if board.is_legal(move):
            return move

        # A pawn reaching the last rank has to promote to be legal
        promotion = chess.Move(square, target, promotion=chess.QUEEN)
        if board.is_legal(promotion):
            return promotion

    return None


def build_opening_book():
    """Mainline replies keyed by position

    The lines are written as move sequences because that is readable, then
    replayed once to key them by position. Keying on the position rather
    than the move list matters because a board set up from a FEN has no
    move history at all, and it makes transpositions work for free.
    """
    lines = {
        # First move as White
        (): ["e2e4", "d2d4", "g1f3", "c2c4"],

        # Replies to 1.e4
        ("e2e4",): ["e7e5", "c7c5", "e7e6", "c7c6"],
        ("e2e4", "e7e5"): ["g1f3"],
        ("e2e4", "e7e5", "g1f3"): ["b8c6", "g8f6"],
        ("e2e4", "e7e5", "g1f3", "b8c6"): ["f1b5", "f1c4"],
        ("e2e4", "c7c5"): ["g1f3"],
        ("e2e4", "c7c5", "g1f3"): ["d7d6", "b8c6"],
        ("e2e4", "e7e6"): ["d2d4"],
        ("e2e4", "c7c6"): ["d2d4"],

        # Replies to 1.d4
        ("d2d4",): ["d7d5", "g8f6"],
        ("d2d4", "d7d5"): ["c2c4"],
        ("d2d4", "d7d5", "c2c4"): ["e7e6", "c7c6"],
        ("d2d4", "g8f6"): ["c2c4"],
        ("d2d4", "g8f6", "c2c4"): ["e7e6", "g7g6"],

        # Replies to 1.Nf3 and 1.c4
        ("g1f3",): ["d7d5", "g8f6"],
        ("c2c4",): ["e7e5", "g8f6"],
    }

    book = {}
    for moves, replies in lines.items():
        board = chess.Board()
        for uci in moves:
            board.push(chess.Move.from_uci(uci))
        # Keep only replies that are legal in the position they belong to
        legal = [
            chess.Move.from_uci(uci)
            for uci in replies
            if chess.Move.from_uci(uci) in board.legal_moves
        ]
        if legal:
            book[board._transposition_key()] = legal

    return book


def book_move(board, book):
    """A book reply for this position, or None once out of book"""
    if board.fullmove_number > BOOK_MAX_FULLMOVES:
        return None

    replies = book.get(board._transposition_key())
    if not replies:
        return None

    # The stored moves were legal when the book was built, but a position
    # reached another way can still differ, so check before offering one
    legal = [move for move in replies if move in board.legal_moves]
    return random.choice(legal) if legal else None


def is_passed_pawn(square, color, enemy_pawns):
    """True when no enemy pawn can stop this one from promoting

    That means no enemy pawn ahead of it on its own file or on either
    adjacent file.
    """
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)

    for enemy in enemy_pawns:
        if abs(chess.square_file(enemy) - file_index) > 1:
            continue
        enemy_rank = chess.square_rank(enemy)
        if color == chess.WHITE and enemy_rank > rank:
            return False
        if color == chess.BLACK and enemy_rank < rank:
            return False

    return True


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

class SearchAborted(Exception):
    """Raised inside the search when the time budget has run out

    Iterative deepening used to only check the clock between iterations, so
    a single iteration that cost far more than the previous depth predicted
    ran to completion regardless of the budget. Aborting mid-search means
    the deepest completed depth is still available to play.
    """


class KnightmareBot:
    def __init__(self):
        self.nodes = 0
        # Wall clock time the current search must stop by, or None for a
        # search with no time limit at all
        self.deadline = None
        # Set when a root search ran out of time but had already finished
        # at least one move, so its answer is usable but incomplete
        self.aborted = False
        self.killer_moves = {}
        self.history_table = {}
        self.transposition_table = {}
        self.opening_book = build_opening_book()
        # Per instance rather than a module constant, so a host can size
        # the table for the machine it is running on
        self.tt_limit = TT_MAX_ENTRIES
        # Hosts running an opening book of their own want the engine's own
        # book out of the way, so that the book being tested is theirs
        self.use_book = True

    def store_tt(self, key, score, move, flag):
        """Cache a search result, skipping values that do not travel well

        Mate scores are relative to the ply they were found at, so caching
        them would hand back the wrong distance somewhere else in the tree.
        """
        if abs(score) >= MATE_SCORE - MAX_PLY:
            return
        if len(self.transposition_table) >= self.tt_limit:
            return
        self.transposition_table[key] = (score, move, flag)

    def extract_pv(self, board, depth):
        """Follow the stored best moves to recover the expected line

        Walks the transposition table from the current position, taking the
        best move recorded at each remaining depth. The line stops as soon
        as an entry is missing or the move is not legal, so a partial or
        overwritten table just yields a shorter line.
        """
        pv = []
        scratch = board.copy(stack=False)
        seen = set()

        for remaining in range(depth, 0, -1):
            key = scratch._transposition_key()
            if key in seen:  # a repetition would loop forever
                break
            seen.add(key)

            entry = self.transposition_table.get((key, remaining))
            if entry is None:
                break

            move = entry[1]
            if move is None or move not in scratch.legal_moves:
                break

            pv.append(move)
            scratch.push(move)

        return pv

    def has_pieces_for_null_move(self, board):
        """True when the side to move has more than just king and pawns

        With only pawns left, being forced to move is often a real
        disadvantage, and pretending a free pass is available gives a
        badly wrong answer.
        """
        colour = board.turn
        pieces = (
            board.knights | board.bishops | board.rooks | board.queens
        ) & board.occupied_co[colour]
        return chess.popcount(pieces) > 0

    def is_endgame(self, board):
        """True once the heavy pieces have largely left the board

        The king wants shelter while queens are on and activity afterwards,
        so this decides which king table to read.
        """
        if board.queens:
            majors = chess.popcount(board.rooks | board.queens)
            minors = chess.popcount(board.knights | board.bishops)
            return majors + minors <= ENDGAME_PIECE_COUNT
        return True

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
        endgame = self.is_endgame(board)

        # Material and placement
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = PIECE_VALUES[piece.piece_type]
                value += piece_square_bonus(
                    piece.piece_type, square, piece.color, endgame
                )

                if piece.color == chess.WHITE:
                    score += value
                else:
                    score -= value
        
        # Bishop pair is worth a small bonus in most positions
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += BISHOP_PAIR_BONUS
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= BISHOP_PAIR_BONUS

        # Pawn structure
        score += self.pawn_structure_score(board, chess.WHITE)
        score -= self.pawn_structure_score(board, chess.BLACK)

        # Rook placement relative to the pawns
        score += self.rook_file_score(board, chess.WHITE)
        score -= self.rook_file_score(board, chess.BLACK)

        # King shelter, which only matters while there is material to attack with
        if not self.is_endgame(board):
            score += self.king_safety_score(board, chess.WHITE)
            score -= self.king_safety_score(board, chess.BLACK)

        # Mobility bonus
        mobility = len(list(board.legal_moves)) * 3
        score += mobility if board.turn == chess.WHITE else -mobility

        return score

    def king_safety_score(self, board, color):
        """Penalise a king whose pawn cover has gone

        Looks at the three files around the king and charges for each one
        with no friendly pawn on it. Only meaningful in the middlegame,
        which the caller checks before asking.
        """
        king_square = board.king(color)
        if king_square is None:
            return 0

        king_file = chess.square_file(king_square)
        pawn_files = {chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)}

        missing = 0
        for offset in (-1, 0, 1):
            shield_file = king_file + offset
            if 0 <= shield_file <= 7 and shield_file not in pawn_files:
                missing += 1

        return -missing * KING_SHIELD_PENALTY

    def rook_file_score(self, board, color):
        """Reward rooks on files their own pawns have vacated

        A file with no pawns at all is fully open; one with only enemy
        pawns is half open and still gives the rook something to attack.
        """
        score = 0
        own_pawn_files = {chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)}
        enemy_pawn_files = {
            chess.square_file(sq) for sq in board.pieces(chess.PAWN, not color)
        }

        for square in board.pieces(chess.ROOK, color):
            file_index = chess.square_file(square)
            if file_index in own_pawn_files:
                continue
            if file_index in enemy_pawn_files:
                score += ROOK_HALF_OPEN_FILE_BONUS
            else:
                score += ROOK_OPEN_FILE_BONUS

        return score

    def pawn_structure_score(self, board, color):
        """Score one side's pawn structure

        Rewards passers, which are worth more the closer they get to
        promoting, and penalises doubled and isolated pawns because both
        are hard to defend and cannot support each other.
        """
        score = 0
        pawns = board.pieces(chess.PAWN, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)

        # How many of this side's pawns stand on each file
        files = [0] * 8
        for square in pawns:
            files[chess.square_file(square)] += 1

        for square in pawns:
            file_index = chess.square_file(square)

            if is_passed_pawn(square, color, enemy_pawns):
                rank = chess.square_rank(square)
                advanced = rank if color == chess.WHITE else 7 - rank
                score += PASSED_PAWN_BONUS[advanced]

            # Pawns stacked on one file block each other
            if files[file_index] > 1:
                score -= DOUBLED_PAWN_PENALTY

            # No friendly pawn on either neighbouring file to defend it
            left = files[file_index - 1] if file_index > 0 else 0
            right = files[file_index + 1] if file_index < 7 else 0
            if left == 0 and right == 0:
                score -= ISOLATED_PAWN_PENALTY

        return score
    
    def order_moves(self, board, moves, ply=0, tt_move=None):
        """Simple but effective move ordering

        A move that was best here in an earlier, shallower search is the
        single most likely move to be best again, so it is tried first.
        """
        scored = []

        for move in moves:
            score = 0

            # The stored best move from a previous iteration
            if tt_move is not None and move == tt_move:
                score += TT_MOVE_SCORE

            # Captures, ranked by what the whole exchange actually wins.
            # MVV-LVA alone rates QxP highly even when the pawn is defended;
            # playing the exchange out sorts those below the quiet moves.
            if board.is_capture(move):
                exchange = static_exchange_eval(board, move)
                if exchange >= 0:
                    score += 1000 + exchange
                else:
                    score += LOSING_CAPTURE_SCORE + exchange
            
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

    def check_clock(self):
        """Abort the search if the budget has run out

        Only looks at the clock every CLOCK_CHECK_INTERVAL nodes, so the
        cost of the check itself stays negligible.
        """
        if self.deadline is None:
            return
        if self.nodes % CLOCK_CHECK_INTERVAL:
            return
        if time.time() >= self.deadline:
            raise SearchAborted()

    def quiesce(self, board, alpha, beta, ply, depth=QUIESCENCE_DEPTH):
        """Search only captures until the position is quiet

        Stopping a search in the middle of a capture sequence badly
        misjudges the position, so keep resolving captures before handing
        the score back to the main search.
        """
        self.nodes += 1
        self.check_clock()

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

        # Captures that lose material are not worth resolving: the side to
        # move would simply decline them and keep the stand pat score.
        captures = [
            m for m in board.legal_moves
            if (m.promotion or board.is_capture(m))
            and (m.promotion or static_exchange_eval(board, m) >= 0)
        ]
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
        self.check_clock()

        if board.is_game_over():
            return self.evaluate(board, ply), None

        # Being in check is a forced sequence, so stopping here would cut a
        # forced line in half. Search one ply further to see how it ends.
        in_check = board.is_check()
        if in_check and depth == 0 and ply < MAX_PLY:
            depth = 1

        if depth == 0:
            return self.quiesce(board, alpha, beta, ply), None

        # A position reached by different move orders only needs searching once.
        # Stored scores may be bounds rather than exact values, so a cached
        # entry is only reusable when it still settles the current window.
        tt_key = (board._transposition_key(), depth)
        cached = self.transposition_table.get(tt_key)
        tt_move = None
        if cached is not None:
            score, move, flag = cached
            if flag == TT_EXACT:
                return score, move
            if flag == TT_LOWER and score >= beta:
                return score, move
            if flag == TT_UPPER and score <= alpha:
                return score, move
            # The score was not usable here, but the move it came from is
            # still the best guess for what to try first
            tt_move = move

        # Iterative deepening leaves an entry from the previous, shallower
        # pass for this position, which is an even better first guess
        if tt_move is None:
            shallower = self.transposition_table.get((tt_key[0], depth - 1))
            if shallower is not None:
                tt_move = shallower[1]

        # Null move pruning: if handing the opponent a free move still
        # leaves the position winning, the real move will be at least as
        # good and this branch can be cut without searching it.
        #
        # Skipped in check (passing would be illegal) and in near-pawn-only
        # endgames, where passing is often genuinely good and the shortcut
        # misjudges zugzwang.
        if (
            not in_check
            and depth >= NULL_MOVE_MIN_DEPTH
            and self.has_pieces_for_null_move(board)
        ):
            board.push(chess.Move.null())
            null_score, _ = self.minimax(
                board, depth - 1 - NULL_MOVE_REDUCTION, alpha, beta,
                not maximizing, ply + 1,
            )
            board.pop()

            if maximizing and null_score >= beta:
                return null_score, None
            if not maximizing and null_score <= alpha:
                return null_score, None

        moves = list(board.legal_moves)
        if not moves:
            return self.evaluate(board, ply), None

        # Order moves
        moves = self.order_moves(board, moves, ply, tt_move)

        best_move = moves[0]

        # The window as it was on entry. Classifying the result needs the
        # original bounds, because alpha and beta get narrowed below.
        alpha_orig = alpha
        beta_orig = beta

        if maximizing:
            max_eval = -float('inf')
            searched = 0
            for move in moves:
                board.push(move)
                try:
                    eval_score, _ = self.minimax(board, depth - 1, alpha, beta, False, ply + 1)
                except SearchAborted:
                    board.pop()
                    # A root move searched to this depth is a better answer
                    # than the whole of the previous, shallower iteration,
                    # so keep it rather than throwing the work away. Deeper
                    # in the tree a partial result is meaningless.
                    if ply == 0 and searched:
                        self.aborted = True
                        return max_eval, best_move
                    raise
                board.pop()
                searched += 1

                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move

                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    self.record_cutoff(board, move, depth, ply)
                    break

            # Classify against the window we were given. Cutting off high
            # gives a lower bound; scoring at or below the incoming alpha
            # means every move failed low and the truth may be lower still.
            if max_eval >= beta_orig:
                flag = TT_LOWER
            elif max_eval <= alpha_orig:
                flag = TT_UPPER
            else:
                flag = TT_EXACT
            self.store_tt(tt_key, max_eval, best_move, flag)
            return max_eval, best_move
        else:
            min_eval = float('inf')
            searched = 0
            for move in moves:
                board.push(move)
                try:
                    eval_score, _ = self.minimax(board, depth - 1, alpha, beta, True, ply + 1)
                except SearchAborted:
                    board.pop()
                    if ply == 0 and searched:
                        self.aborted = True
                        return min_eval, best_move
                    raise
                board.pop()
                searched += 1

                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move

                beta = min(beta, eval_score)
                if beta <= alpha:
                    self.record_cutoff(board, move, depth, ply)
                    break

            # Mirror of the maximizing case: cutting off low gives an upper
            # bound, and scoring at or above the incoming beta is a fail high
            if min_eval <= alpha_orig:
                flag = TT_UPPER
            elif min_eval >= beta_orig:
                flag = TT_LOWER
            else:
                flag = TT_EXACT
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

        # Known theory, consulted only after the mate check above so the
        # book can never talk the engine out of a forced win
        opening = book_move(board, self.opening_book) if self.use_book else None
        if opening is not None:
            print(f"info string book move {opening.uci()}", flush=True)
            return opening

        # Default to first legal move (will be replaced by search)
        best_move = legal_moves[0]
        
        # Age the history rather than wiping it. Halving keeps the ordering
        # it has learned while letting newer cutoffs overtake stale ones,
        # and drops entries that have decayed to nothing.
        if len(self.history_table) > HISTORY_MAX_ENTRIES:
            self.history_table = {
                key: value // 2
                for key, value in self.history_table.items()
                if value > 1
            }
        if len(self.transposition_table) >= self.tt_limit:
            self.transposition_table.clear()
        self.killer_moves.clear()  # Clear each search

        # A hard stop the search itself honours. The prediction below is
        # only an estimate, so without this an iteration that turns out to
        # cost far more than the last one runs to the end regardless.
        self.deadline = start_time + time_limit

        # Search a copy. Aborting on time unwinds out of the search
        # without the matching pops, so the position the search works on
        # cannot be the caller's.
        search_board = board.copy()

        # Iterative deepening with time control
        last_iteration = None

        try:
            for depth in range(1, max_depth + 1):
                self.nodes = 0
                iteration_start = time.time()
                elapsed = iteration_start - start_time

                # Starting an iteration that cannot finish wastes the rest
                # of the budget and its result is thrown away, so predict
                # the cost from how long the previous depth actually took.
                if last_iteration is not None:
                    projected = last_iteration * BRANCHING_ESTIMATE
                    if elapsed + projected > time_limit:
                        break
                elif elapsed > time_limit * 0.7:
                    break

                # Search with timeout protection
                maximizing = board.turn == chess.WHITE
                self.aborted = False
                try:
                    score, move = self.minimax(
                        search_board, depth, -float('inf'), float('inf'), maximizing
                    )
                except SearchAborted:
                    # Out of time before any root move finished, so there
                    # is nothing from this depth worth keeping
                    print("info string search aborted on time", flush=True)
                    break

                if self.aborted:
                    # Part of this depth did finish. Take its move, but do
                    # not time the depth from a run that was cut short, and
                    # do not start another one.
                    if move and move in legal_moves:
                        best_move = move
                    print(f"info string depth {depth} cut short on time", flush=True)
                    break

                last_iteration = time.time() - iteration_start
                
                if move and move in legal_moves:
                    best_move = move
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    nps = int(self.nodes / max(elapsed_ms / 1000.0, 0.001))

                    pv = self.extract_pv(board, depth)
                    # The root move is authoritative even if the table has
                    # since been overwritten for that position
                    if not pv or pv[0] != move:
                        pv = [move]
                    pv_text = " ".join(m.uci() for m in pv)

                    print(
                        f"info depth {depth} score {format_score(score)} "
                        f"nodes {self.nodes} time {elapsed_ms} nps {nps} pv {pv_text}",
                        flush=True,
                    )
                
                # Another time check
                elapsed = time.time() - start_time
                if elapsed > time_limit * 0.8:
                    break
                    
        except Exception as e:
            print(f"info string Search error: {e}", flush=True)
        finally:
            self.deadline = None

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


# The table is capped by entry count rather than by bytes, so a Hash value
# in megabytes has to be turned into a number of entries. Roughly 200 bytes
# per entry: a key tuple, a score, a move and a flag.
BYTES_PER_TT_ENTRY = 200


def hash_mb_to_entries(megabytes):
    """How many table entries fit in the given number of megabytes"""
    return max(1, int(megabytes * 1024 * 1024 / BYTES_PER_TT_ENTRY))


def entries_to_hash_mb(entries):
    """The Hash setting matching an entry count, rounded to whole megabytes"""
    return max(1, round(entries * BYTES_PER_TT_ENTRY / (1024 * 1024)))


# The options a host may set, as (name, uci type, default, min, max).
# A UCI host only offers what the engine advertises here, so an option
# that is not listed can never be set even if the code would honour it.
#
# The Hash default is derived from the table size the engine actually uses,
# so a host that sets nothing gets what was advertised.
UCI_OPTIONS = [
    ("Hash", "spin", entries_to_hash_mb(TT_MAX_ENTRIES), 1, 1024),
    ("OwnBook", "check", True, None, None),
]


def option_lines():
    """The `option` lines to send in reply to `uci`"""
    lines = []
    for name, kind, default, low, high in UCI_OPTIONS:
        text = f"option name {name} type {kind}"
        if kind == "check":
            text += f" default {str(default).lower()}"
        else:
            text += f" default {default} min {low} max {high}"
        lines.append(text)
    return lines


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
                    except ValueError:
                        break
                    if move not in board.legal_moves:
                        break
                    board.push(move)
        
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
                    except ValueError:
                        break
                    if move not in board.legal_moves:
                        break
                    board.push(move)
    except ValueError:
        # Unparseable FEN or command, fall back to the initial position
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
                for option in option_lines():
                    print(option)
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
    except (KeyboardInterrupt, EOFError):
        # A host closing the pipe or a user interrupting is a normal exit
        sys.exit(0)