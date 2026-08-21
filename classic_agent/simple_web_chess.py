#!/usr/bin/env python3
"""
Simple Web Chess Interface - Direct Integration
Works directly with the Knightmare bot code without UCI
"""

from flask import Flask, Response, render_template_string, jsonify, request
import argparse
import threading

import chess
import chess.svg
import random
import os

# Default port for this interface
DEFAULT_PORT = 5001

# Seconds the engine may think about each move
THINK_SECONDS = 1.0

from bot_loader import ask_engine, game_pgn, load_bot_class, random_move

bot_class = load_bot_class()

app = Flask(__name__)

# Global game state, guarded by board_lock because the dev server is threaded
game_board = chess.Board()
move_history = []
knightmare = None
board_lock = threading.Lock()

# What the engine last reported about its search, shown in the interface
last_engine_info = None

# Who plays which side. "watch" is the original behaviour, a random bot
# against Knightmare. "play" hands White to whoever is at the keyboard.
WATCH_MODE = "watch"
PLAY_MODE = "play"
mode = WATCH_MODE

# Which side the person is playing when the mode is play. Stored rather
# than assumed to be White, so the engine can be given the first move.
human_colour = chess.WHITE

def reset_game():
    global game_board, move_history, knightmare, last_engine_info
    game_board = chess.Board()
    move_history = []
    last_engine_info = None
    if bot_class:
        knightmare = bot_class()


def human_to_move():
    """True when the interface is waiting for a person rather than a bot"""
    return mode == PLAY_MODE and game_board.turn == human_colour


def legal_by_origin(board):
    """Legal moves as {from_square: [uci, ...]}

    Sent to the browser so it can show a piece's options and reject an
    impossible drag without having to know how chess works. Promotions
    appear as the full UCI including the piece, so the client can offer a
    choice when several share the same destination.
    """
    grouped = {}
    for move in board.legal_moves:
        grouped.setdefault(chess.square_name(move.from_square), []).append(move.uci())
    return grouped

def get_knightmare_move(board):
    """Get move from Knightmare bot, remembering what it reported"""
    global knightmare, last_engine_info

    if bot_class and knightmare is None:
        knightmare = bot_class()

    move, info = ask_engine(knightmare, board, THINK_SECONDS)
    last_engine_info = info
    return move

def get_random_move(board):
    """Get random move"""
    return random_move(board)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Chess: Knightmare vs Random</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            display: flex;
            gap: 30px;
            align-items: flex-start;
        }
        /* Pieces are drawn on top of the square rectangles, so without
           this a click on a piece never reaches the square under it */
        #board use {
            pointer-events: none;
        }
        .board-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        #fen {
            width: 100%;
            box-sizing: border-box;
            padding: 8px;
            margin-bottom: 8px;
            font-family: monospace;
            font-size: 12px;
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            min-width: 300px;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            font-size: 16px;
        }
        button:hover {
            background: #764ba2;
        }
        button.active {
            background: #e91e63;
        }
        #status {
            padding: 10px;
            background: #f0f0f0;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
        }
        #engine {
            padding: 8px;
            background: #eef2ff;
            border-radius: 5px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 13px;
            color: #333;
        }
        #moves {
            max-height: 400px;
            overflow-y: auto;
            background: #f9f9f9;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
        }
        .move-pair {
            padding: 3px 0;
        }
        .move-pair:hover {
            background: #e0e0e0;
        }
        .player-indicator {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            font-weight: bold;
        }
        .player-indicator.active {
            background: #4caf50;
            color: white;
        }
        .player-indicator.inactive {
            background: #f0f0f0;
        }
    </style>
</head>
<body>
    <h1>♔ Knightmare vs Random Bot ♚</h1>

    <div class="container">
        <div class="board-container">
            <div id="board">Loading...</div>
        </div>

        <div class="controls">
            <h2>Game Controls</h2>

            <div class="player-indicator" id="white-player">
                ⚪ White: Random Bot
            </div>
            <div class="player-indicator" id="black-player">
                ⚫ Black: Knightmare
            </div>

            <div id="status">Ready</div>
            <div id="engine">Engine: waiting</div>

            <button onclick="newGame()">New Game</button>
            <button onclick="makeMove()">Make Move</button>
            <button onclick="toggleAuto()" id="auto-btn">Auto Play: OFF</button>
            <button onclick="toggleMode()" id="mode-btn">Mode: Watch</button>
            <button onclick="takeBack()" id="undo-btn">Take Back</button>
            <button onclick="savePgn()">Save PGN</button>

            <h3>Set Up A Position</h3>
            <input type="text" id="fen" placeholder="Paste a FEN" />
            <button onclick="loadFen()">Load</button>

            <h3>Move History</h3>
            <div id="moves"></div>
        </div>
    </div>

    <script>
        let autoPlay = false;
        let autoTimer = null;
        let playMode = false;
        let legalMoves = {};
        let selected = null;

        // The colour used to outline the square you picked and the squares
        // that piece can reach
        const HIGHLIGHT = '#2f9e44';

        // Breathing room between moves so the board is visible
        const AUTO_PLAY_GAP_MS = 250;

        function updateBoard() {
            return fetch('/board')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('board').innerHTML = data.svg;
                    document.getElementById('status').textContent = data.status;

                    // The server owns the mode: a reload would otherwise
                    // show Watch while a game against a person is running
                    if (playMode !== (data.mode === 'play')) {
                        playMode = data.mode === 'play';
                        showMode();
                    }

                    // What the engine reported about its own search
                    const engine = data.engine;
                    document.getElementById('engine').textContent = engine
                        ? 'Engine: depth ' + engine.depth + '  score ' +
                          engine.score_text + '  line ' + engine.pv_text
                        : 'Engine: no search (book move or random bot)';

                    // Update move history
                    let movesHtml = '';
                    for (let i = 0; i < data.moves.length; i += 2) {
                        let moveNum = Math.floor(i/2) + 1;
                        let white = data.moves[i] || '';
                        let black = data.moves[i+1] || '';
                        movesHtml += '<div class="move-pair">' + moveNum + '. ' + white + ' ' + black + '</div>';
                    }
                    document.getElementById('moves').innerHTML = movesHtml;
                    document.getElementById('moves').scrollTop = document.getElementById('moves').scrollHeight;

                    // Update player indicators
                    if (data.white_to_move) {
                        document.getElementById('white-player').className = 'player-indicator active';
                        document.getElementById('black-player').className = 'player-indicator inactive';
                    } else {
                        document.getElementById('white-player').className = 'player-indicator inactive';
                        document.getElementById('black-player').className = 'player-indicator active';
                    }

                    // Redrawing replaces the squares, so the handlers and
                    // the move list have to be attached to the new ones
                    legalMoves = data.your_turn ? (data.legal || {}) : {};
                    if (!data.your_turn) {
                        selected = null;
                    }
                    wireBoard();

                    // Stop auto play if game over
                    if (data.game_over && autoPlay) {
                        stopAuto();
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent =
                        'Could not load the board: ' + error;
                });
        }

        function newGame() {
            stopAuto();
            fetch('/new_game', {method: 'POST'})
                .then(() => updateBoard());
        }

        function makeMove() {
            // Returns a promise so auto play can wait for the move to land
            return fetch('/move', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.error && !autoPlay) {
                        alert(data.error);
                    }
                    return updateBoard();
                })
                .catch(error => {
                    // A dead server would otherwise just stop updating
                    document.getElementById('status').textContent =
                        'Lost contact with the server: ' + error;
                    stopAuto();
                });
        }

        function autoStep() {
            // Chained rather than on a timer: a move can take longer than
            // any fixed interval, and overlapping requests would each play
            // for the same side.
            if (!autoPlay) { return; }
            makeMove().then(() => {
                if (autoPlay) {
                    autoTimer = setTimeout(autoStep, AUTO_PLAY_GAP_MS);
                }
            });
        }

        function squareName(rect) {
            // python-chess names each square in the rect's class, as in
            // "square dark a1", so the board needs no coordinate maths
            const parts = rect.getAttribute('class').split(' ');
            return parts[parts.length - 1];
        }

        function boardSquares() {
            return document.querySelectorAll('#board rect.square');
        }

        function wireBoard() {
            const clickable = playMode && !document.getElementById('board').dataset.locked;
            boardSquares().forEach(rect => {
                const name = squareName(rect);
                rect.style.cursor = clickable ? 'pointer' : 'default';
                rect.onclick = clickable ? () => clickSquare(name) : null;
            });
            showSelection();
        }

        function showSelection() {
            boardSquares().forEach(rect => {
                const name = squareName(rect);
                const reachable = selected && (legalMoves[selected] || [])
                    .some(uci => uci.slice(2, 4) === name);
                if (name === selected) {
                    rect.setAttribute('stroke', HIGHLIGHT);
                    rect.setAttribute('stroke-width', '4');
                } else if (reachable) {
                    rect.setAttribute('stroke', HIGHLIGHT);
                    rect.setAttribute('stroke-width', '2');
                } else {
                    rect.setAttribute('stroke', 'none');
                }
            });
        }

        function clickSquare(name) {
            if (selected === null) {
                // Only squares holding a piece of yours that can move
                if (legalMoves[name]) {
                    selected = name;
                    showSelection();
                }
                return;
            }

            if (name === selected) {
                selected = null;
                showSelection();
                return;
            }

            const options = (legalMoves[selected] || [])
                .filter(uci => uci.slice(2, 4) === name);

            if (options.length === 0) {
                // Clicking another of your own pieces picks that one up
                // instead of being treated as an illegal move
                selected = legalMoves[name] ? name : null;
                showSelection();
                return;
            }

            const uci = options.length === 1 ? options[0] : choosePromotion(options);
            selected = null;
            showSelection();
            if (uci) {
                sendMove(uci);
            }
        }

        function choosePromotion(options) {
            // Several moves share a destination only when a pawn is
            // promoting, and the piece has to come from the player
            const answer = prompt('Promote to q, r, b or n?', 'q');
            if (answer === null) {
                return null;
            }
            const wanted = options.find(uci => uci.endsWith(answer.trim().toLowerCase()));
            if (!wanted) {
                alert('Pick one of q, r, b or n');
            }
            return wanted || null;
        }

        function sendMove(uci) {
            // Locked while the engine replies, so a second click cannot
            // queue a move onto a position that is about to change
            document.getElementById('board').dataset.locked = '1';
            return fetch('/human_move', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({move: uci})
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        delete document.getElementById('board').dataset.locked;
                        return updateBoard();
                    }
                    return updateBoard().then(() => makeMove());
                })
                .catch(error => {
                    document.getElementById('status').textContent =
                        'Could not send the move: ' + error;
                })
                .finally(() => {
                    delete document.getElementById('board').dataset.locked;
                    wireBoard();
                });
        }

        function toggleMode() {
            // Switching sides restarts the game, so stop auto play first:
            // a move already in flight would land on the new position
            stopAuto();
            const wanted = playMode ? 'watch' : 'play';
            fetch('/set_mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: wanted})
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    playMode = data.mode === 'play';
                    showMode();
                    return updateBoard();
                });
        }

        function takeBack() {
            fetch('/takeback', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    selected = null;
                    return updateBoard();
                });
        }

        function loadFen() {
            const box = document.getElementById('fen');
            fetch('/set_position', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({fen: box.value})
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    // Show the position as the library writes it, which is
                    // not always exactly what was pasted in
                    box.value = data.fen;
                    selected = null;
                    return updateBoard();
                });
        }

        function savePgn() {
            // A plain navigation rather than a fetch, so the browser's own
            // download handling names and saves the file
            window.location = '/pgn';
        }

        function showMode() {
            const button = document.getElementById('mode-btn');
            button.textContent = playMode ? 'Mode: You vs Knightmare' : 'Mode: Watch';
            button.className = playMode ? 'active' : '';
            // Nothing to step through by hand when it is your turn
            document.getElementById('auto-btn').disabled = playMode;
            // There is no side of yours to take a move back for otherwise
            document.getElementById('undo-btn').disabled = !playMode;
            document.getElementById('white-player').textContent =
                playMode ? '⚪ White: You' : '⚪ White: Random Bot';
        }

        function toggleAuto() {
            if (autoPlay) {
                stopAuto();
            } else {
                autoPlay = true;
                document.getElementById('auto-btn').textContent = 'Auto Play: ON';
                document.getElementById('auto-btn').className = 'active';
                autoStep();
            }
        }

        function stopAuto() {
            if (autoPlay || autoTimer) {
                autoPlay = false;
                clearTimeout(autoTimer);
                autoTimer = null;
                document.getElementById('auto-btn').textContent = 'Auto Play: OFF';
                document.getElementById('auto-btn').className = '';
            }
        }

        // Load board on startup
        showMode();
        updateBoard();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/board')
def get_board():
    """Snapshot the position for the browser

    Read under board_lock so a request that lands mid update sees
    a whole position rather than one being changed underneath it.
    """
    global game_board, move_history, last_engine_info

    with board_lock:

        svg = chess.svg.board(game_board, size=500)

        # Determine game status
        if game_board.is_checkmate():
            winner = "White (Random)" if game_board.turn == chess.BLACK else "Black (Knightmare)"
            status = f"Checkmate! {winner} wins!"
        elif game_board.is_stalemate():
            status = "Stalemate - Draw!"
        elif game_board.is_insufficient_material():
            status = "Draw - Insufficient material"
        elif game_board.is_fifty_moves():
            status = "Draw - 50 move rule"
        elif game_board.is_game_over():
            status = "Game Over"
        else:
            if mode == PLAY_MODE:
                # Phrased as a prompt rather than "X to move", which reads
                # oddly when the side to move is the person reading it
                status = ("Your move" if human_to_move()
                          else "Knightmare is thinking...")
            else:
                turn = ("White (Random)" if game_board.turn == chess.WHITE
                        else "Black (Knightmare)")
                status = f"{turn} to move"
            if game_board.is_check():
                status += " - CHECK!"

        return jsonify({
            'svg': svg,
            'status': status,
            'moves': move_history,
            'game_over': game_board.is_game_over(),
            'white_to_move': game_board.turn == chess.WHITE,
            'engine': last_engine_info,
            'mode': mode,
            'your_turn': human_to_move(),
            # Legal moves grouped by origin square, so the interface can
            # highlight where a piece may go without knowing the rules
            'legal': legal_by_origin(game_board),
        })

@app.route('/set_mode', methods=['POST'])
def set_mode():
    """Switch between watching two bots and playing one yourself

    Changing mode starts a new game: carrying a half-played position across
    would leave the side you just took over having already moved.
    """
    global mode

    data = request.get_json(silent=True) or {}
    requested = data.get('mode', WATCH_MODE)
    if requested not in (WATCH_MODE, PLAY_MODE):
        return jsonify({'error': f'unknown mode {requested!r}'}), 400

    with board_lock:
        mode = requested
        reset_game()

    return jsonify({'success': True, 'mode': mode})


@app.route('/human_move', methods=['POST'])
def human_move():
    """Play the move a person chose, given as UCI

    Rejected rather than silently ignored when it is not that person's turn
    or the move is not legal, so the interface can say why.
    """
    global game_board, move_history

    data = request.get_json(silent=True) or {}
    uci = str(data.get('move', ''))

    with board_lock:
        if game_board.is_game_over():
            return jsonify({'error': 'Game is over'}), 400

        if not human_to_move():
            return jsonify({'error': 'It is not your turn'}), 400

        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            # A pawn reaching the last rank needs a promotion piece
            return jsonify({'error': f'Could not read the move {uci!r}'}), 400

        if move not in game_board.legal_moves:
            return jsonify({'error': f'{uci} is not legal here'}), 400

        san = game_board.san(move)
        game_board.push(move)
        move_history.append(f"You: {san}")

    return jsonify({'success': True, 'san': san})


@app.route('/pgn')
def download_pgn():
    """The current game as a PGN file"""
    with board_lock:
        if mode == PLAY_MODE:
            white, black = (('Human', 'Knightmare') if human_colour == chess.WHITE
                            else ('Knightmare', 'Human'))
        else:
            white, black = 'Random bot', 'Knightmare'
        text = game_pgn(game_board, white, black)

    return Response(
        text,
        mimetype='application/x-chess-pgn',
        headers={'Content-Disposition': 'attachment; filename=knightmare.pgn'},
    )


@app.route('/takeback', methods=['POST'])
def takeback():
    """Undo back to your own turn

    A single pop would hand the move back to the engine, which would just
    play again, so this unwinds whole move pairs: the engine's reply and
    the move of yours it answered.
    """
    global game_board, move_history, last_engine_info

    with board_lock:
        if mode != PLAY_MODE:
            return jsonify({'error': 'Takeback is only for a game you are playing'}), 400

        if not game_board.move_stack:
            return jsonify({'error': 'No moves to take back'}), 400

        undone = 0
        # Stop once it is your turn again, or once nothing is left. A game
        # that has ended is still unwound, so a loss can be replayed.
        while game_board.move_stack:
            game_board.pop()
            undone += 1
            if move_history:
                move_history.pop()
            if game_board.turn == chess.WHITE:
                break

        # The line the engine reported was for a position that no longer
        # exists, so showing it would be misleading
        last_engine_info = None

    return jsonify({'success': True, 'undone': undone})


@app.route('/set_position', methods=['POST'])
def set_position():
    """Start from a given FEN rather than the opening position

    Useful for practising an endgame or checking what the engine does in
    one particular position, neither of which is reachable by playing from
    the start.
    """
    global game_board, move_history, last_engine_info

    data = request.get_json(silent=True) or {}
    fen = str(data.get('fen', '')).strip()
    if not fen:
        return jsonify({'error': 'No position given'}), 400

    try:
        board = chess.Board(fen)
    except ValueError as exc:
        return jsonify({'error': f'Could not read that position: {exc}'}), 400

    # A position with no king, or with the side not to move already in
    # check, is not one any game can reach, and the search assumes it will
    # never see one
    if not board.is_valid():
        # The flag names read as NO_WHITE_KING or OPPOSITE_CHECK, which say
        # what is wrong once the enum decoration is stripped off
        reasons = ', '.join(
            flag.name.lower().replace('_', ' ')
            for flag in chess.Status
            if flag.name != 'VALID' and flag & board.status()
        )
        return jsonify({'error': f'That position is not legal: {reasons}'}), 400

    with board_lock:
        game_board = board
        move_history = []
        last_engine_info = None

    return jsonify({'success': True, 'fen': board.fen()})


@app.route('/new_game', methods=['POST'])
def new_game():
    with board_lock:
        reset_game()
    return jsonify({'success': True})

@app.route('/move', methods=['POST'])
def make_move():
    """Play one move for whoever is to move

    Held under board_lock: the dev server is threaded, so overlapping
    requests would each read the same position and all push a move for the
    same side. Auto play makes that routine rather than rare, because a
    move can take longer than the interval the browser fires on.
    """
    global game_board, move_history, last_engine_info

    with board_lock:
        if game_board.is_game_over():
            return jsonify({'error': 'Game is over'})

        # In play mode White belongs to the person, so this endpoint must
        # not move for them. Without the guard the random bot answers on
        # their behalf and they never get a turn.
        if human_to_move():
            return jsonify({'error': 'Waiting for your move'}), 409

        try:
            # Determine whose turn it is
            if game_board.turn == chess.WHITE:
                # Random bot plays White
                move = get_random_move(game_board)
                player = "Random"
            else:
                # Knightmare plays Black
                move = get_knightmare_move(game_board)
                player = "Knightmare"

            if move and move in game_board.legal_moves:
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"{player}: {san}")
                return jsonify({'success': True})

            return jsonify({'error': f'{player} failed to make valid move'})

        except Exception as e:
            print(f"Error in make_move: {e}")
            # Fallback to random move
            moves = list(game_board.legal_moves)
            if moves:
                move = random.choice(moves)
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"Emergency: {san}")
                return jsonify({'success': True})
            return jsonify({'error': str(e)})

def parse_args():
    """Parse command line options"""
    parser = argparse.ArgumentParser(description="Web UI for Knightmare vs the random bot")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="run Flask in debug mode")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # Initialize
    reset_game()

    print("\n" + "="*60)
    print("Simple Chess Web Interface")
    print("="*60)

    if bot_class:
        print("✅ Knightmare bot loaded successfully!")
        print(f"   Bot class: {bot_class.__name__}")
    else:
        print("⚠️  Knightmare bot not found - using random moves")

    print(f"\nOpen your browser to: http://{args.host}:{args.port}")
    print("="*60 + "\n")

    app.run(debug=args.debug, host=args.host, port=args.port)