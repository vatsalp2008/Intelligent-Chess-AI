#!/usr/bin/env python3
"""
Knightmare vs Stockfish Web Interface
Test your bot against the world's strongest chess engine
"""

from flask import Flask, Response, render_template_string, jsonify, request
import argparse
import chess
import chess.svg
import chess.engine
import random
import shutil
import threading
import time
import os

from bot_loader import ask_engine, game_pgn, load_bot_class, random_move
from web_common import legal_by_origin, render_board

bot_class = load_bot_class()

app = Flask(__name__)

# Global game state, guarded by board_lock because the dev server is threaded
game_board = chess.Board()
move_history = []
knightmare = None
stockfish_engine = None
stockfish_level = 1  # 1-20 (1 is easiest)
stockfish_time = 0.1  # Time in seconds for Stockfish to think
board_lock = threading.Lock()

# What Knightmare last reported about its search, shown in the interface
last_engine_info = None

# Watching two engines play, or playing one of them yourself. The opponent
# in play mode is Stockfish, since a person wanting a real game wants the
# stronger of the two and its level is already adjustable here.
WATCH_MODE = "watch"
PLAY_MODE = "play"
mode = WATCH_MODE

# Which side the person has in play mode
human_colour = chess.WHITE


def human_to_move():
    """True when the interface is waiting for a person rather than an engine"""
    return mode == PLAY_MODE and game_board.turn == human_colour

# Range Stockfish accepts for its Skill Level option
MIN_SKILL_LEVEL = 0
MAX_SKILL_LEVEL = 20

# Sensible bounds for per-move thinking time, in seconds
MIN_THINK_TIME = 0.01
MAX_THINK_TIME = 10.0

# Default port for this interface
DEFAULT_PORT = 5002

# Seconds the engine may think about each move
THINK_SECONDS = 2.0

def stockfish_candidates():
    """Paths worth trying for the Stockfish binary, best first"""
    configured = os.environ.get("STOCKFISH_PATH")
    if configured:
        yield configured

    # Resolving through PATH avoids launching anything just to look
    on_path = shutil.which("stockfish")
    if on_path:
        yield on_path

    yield from (
        "/usr/local/bin/stockfish",     # Mac/Linux homebrew
        "/opt/homebrew/bin/stockfish",  # Mac M1 homebrew
        "/usr/bin/stockfish",           # Linux apt
        "/usr/games/stockfish",         # Ubuntu/Debian
        "C:\\Program Files\\Stockfish\\stockfish.exe",  # Windows
    )


def find_stockfish():
    """Try to find and initialize Stockfish"""
    global stockfish_engine

    # Drop any engine from a previous call so it is not orphaned
    if stockfish_engine is not None:
        try:
            stockfish_engine.quit()
        except chess.engine.EngineError:
            pass
        stockfish_engine = None

    tried = set()
    for path in stockfish_candidates():
        if path in tried:
            continue
        tried.add(path)

        if not os.path.isfile(path):
            continue

        try:
            stockfish_engine = chess.engine.SimpleEngine.popen_uci(path)
        except (OSError, chess.engine.EngineError) as exc:
            print(f"⚠️  Found {path} but could not start it: {exc}")
            continue

        print(f"✅ Stockfish found at: {path}")
        return True

    print("❌ Stockfish not found. Please install it:")
    print("   Mac: brew install stockfish")
    print("   Ubuntu/Debian: sudo apt-get install stockfish")
    print("   Windows: Download from https://stockfishchess.org/download/")
    print("   Or set STOCKFISH_PATH to the binary")
    return False

def reset_game():
    global game_board, move_history, knightmare, last_engine_info
    game_board = chess.Board()
    move_history = []
    last_engine_info = None
    if bot_class:
        knightmare = bot_class()

def get_knightmare_move(board):
    """Get move from Knightmare bot, remembering what it reported"""
    global knightmare, last_engine_info

    if bot_class and knightmare is None:
        knightmare = bot_class()

    move, info = ask_engine(knightmare, board, THINK_SECONDS)
    last_engine_info = info
    return move

def get_stockfish_move(board, level=1, think_time=0.1):
    """Get move from Stockfish"""
    global stockfish_engine

    if not stockfish_engine:
        return random_move(board)

    try:
        # Configure Stockfish strength (1-20)
        stockfish_engine.configure({"Skill Level": level})

        # Get move with time limit
        result = stockfish_engine.play(board, chess.engine.Limit(time=think_time))
        return result.move
    except Exception as e:
        print(f"Error getting Stockfish move: {e}")
        return random_move(board)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Chess: Knightmare vs Stockfish</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        }
        .header {
            color: white;
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin: 10px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .container {
            display: flex;
            gap: 30px;
            justify-content: center;
        }
        .board-container {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            min-width: 350px;
        }
        .settings {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .settings h3 {
            margin-top: 0;
            color: #1e3c72;
        }
        .setting-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
        }
        .setting-row label {
            font-weight: bold;
            color: #333;
        }
        .setting-row select, .setting-row input {
            padding: 5px 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .setting-row input[type="range"] {
            width: 150px;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        button.active {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        #status {
            padding: 15px;
            background: #f0f0f0;
            border-radius: 5px;
            margin: 10px 0;
            font-weight: bold;
            text-align: center;
            font-size: 1.1em;
        }
        #status.check {
            background: #fff3cd;
            color: #856404;
            border: 2px solid #ffc107;
        }
        #status.checkmate {
            background: #d4edda;
            color: #155724;
            border: 2px solid #28a745;
        }
        #engine {
            padding: 8px;
            background: #eef2ff;
            border-radius: 5px;
            margin: 10px 0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #333;
        }
        #moves {
            max-height: 300px;
            overflow-y: auto;
            background: #f9f9f9;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
        }
        .move-pair {
            padding: 4px;
            border-bottom: 1px solid #e0e0e0;
        }
        .move-pair:hover {
            background: #e8f4f8;
        }
        .player-card {
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            font-weight: bold;
            transition: all 0.3s;
        }
        .player-card.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        .player-card.inactive {
            background: #f0f0f0;
            color: #666;
        }
        .player-name {
            font-size: 1.2em;
            margin-bottom: 5px;
        }
        .player-color {
            font-size: 0.9em;
            opacity: 0.8;
        }
        .stockfish-status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            text-align: center;
        }
        .stockfish-status.connected {
            background: #d4edda;
            color: #155724;
        }
        .stockfish-status.disconnected {
            background: #f8d7da;
            color: #721c24;
        }
        #level-display {
            font-weight: bold;
            color: #1e3c72;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>♔ Knightmare vs Stockfish ♚</h1>
        <p>Test your bot against the world champion chess engine!</p>
    </div>

    <div class="container">
        <div class="board-container">
            <div id="board">Loading...</div>
        </div>

        <div class="controls">
            <h2>Battle Control Center</h2>

            <div class="stockfish-status" id="stockfish-status">
                Checking Stockfish connection...
            </div>

            <div class="settings">
                <h3>⚙️ Stockfish Settings</h3>
                <div class="setting-row">
                    <label>Difficulty Level:</label>
                    <input type="range" id="level-slider" min="1" max="20" value="1" onchange="updateLevel()">
                    <span id="level-display">1</span>
                </div>
                <div class="setting-row">
                    <label>Think Time:</label>
                    <select id="think-time" onchange="updateThinkTime()">
                        <option value="0.1" selected>0.1s (Fast)</option>
                        <option value="0.5">0.5s (Normal)</option>
                        <option value="1.0">1.0s (Slow)</option>
                        <option value="2.0">2.0s (Deep)</option>
                    </select>
                </div>
                <div class="setting-row">
                    <label>Who plays White:</label>
                    <select id="white-player" onchange="updateColors()">
                        <option value="knightmare">Knightmare</option>
                        <option value="stockfish" selected>Stockfish</option>
                    </select>
                </div>
            </div>

            <div class="player-card" id="white-player-card">
                <div class="player-name" id="white-name">⚪ Stockfish</div>
                <div class="player-color">Playing White</div>
            </div>

            <div class="player-card" id="black-player-card">
                <div class="player-name" id="black-name">⚫ Knightmare</div>
                <div class="player-color">Playing Black</div>
            </div>

            <div id="status">Ready</div>
            <div id="engine">Knightmare: waiting</div>

            <button onclick="newGame()">🆕 New Game</button>
            <button onclick="makeMove()">▶️ Make Move</button>
            <button onclick="toggleAuto()" id="auto-btn">🔄 Auto Play: OFF</button>
            <button onclick="savePgn()">💾 Save PGN</button>

            <h3>📋 Move History</h3>
            <div id="moves"></div>
        </div>
    </div>

    <script>
        let autoPlay = false;
        let autoTimer = null;

        // Breathing room between moves so the board is visible
        const AUTO_PLAY_GAP_MS = 250;
        let stockfishLevel = 1;
        let stockfishTime = 0.1;
        let whiteIsKnightmare = false;

        function updateBoard() {
            return fetch('/board')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('board').innerHTML = data.svg;

                    // Update status with styling
                    const statusEl = document.getElementById('status');
                    statusEl.textContent = data.status;
                    statusEl.className = '';

                    // What Knightmare reported about its own search
                    const engine = data.engine;
                    document.getElementById('engine').textContent = engine
                        ? 'Knightmare: depth ' + engine.depth + '  score ' +
                          engine.score_text + '  line ' + engine.pv_text
                        : 'Knightmare: no search yet';

                    if (data.status.includes('Checkmate')) {
                        statusEl.className = 'checkmate';
                    } else if (data.status.includes('CHECK')) {
                        statusEl.className = 'check';
                    }

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
                        document.getElementById('white-player-card').className = 'player-card active';
                        document.getElementById('black-player-card').className = 'player-card inactive';
                    } else {
                        document.getElementById('white-player-card').className = 'player-card inactive';
                        document.getElementById('black-player-card').className = 'player-card active';
                    }

                    // Update Stockfish status
                    if (data.stockfish_available) {
                        document.getElementById('stockfish-status').className = 'stockfish-status connected';
                        document.getElementById('stockfish-status').textContent = '✅ Stockfish Connected';
                    } else {
                        document.getElementById('stockfish-status').className = 'stockfish-status disconnected';
                        document.getElementById('stockfish-status').textContent = '❌ Stockfish Not Found (using random moves)';
                    }

                    // Stop auto play if game over
                    if (data.game_over && autoPlay) {
                        stopAuto();
                        // Show result alert
                        setTimeout(() => {
                            if (confirm(data.status + '\\n\\nPlay another game?')) {
                                newGame();
                            }
                        }, 500);
                    }
                })
                .catch(error => {
                    document.getElementById('status').textContent =
                        'Could not load the board: ' + error;
                });
        }

        function updateLevel() {
            stockfishLevel = document.getElementById('level-slider').value;
            document.getElementById('level-display').textContent = stockfishLevel;

            fetch('/set_stockfish_level', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({level: parseInt(stockfishLevel)})
            });
        }

        function updateThinkTime() {
            stockfishTime = parseFloat(document.getElementById('think-time').value);

            fetch('/set_stockfish_time', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({time: stockfishTime})
            });
        }

        function updateColors() {
            whiteIsKnightmare = document.getElementById('white-player').value === 'knightmare';

            if (whiteIsKnightmare) {
                document.getElementById('white-name').textContent = '⚪ Knightmare';
                document.getElementById('black-name').textContent = '⚫ Stockfish';
            } else {
                document.getElementById('white-name').textContent = '⚪ Stockfish';
                document.getElementById('black-name').textContent = '⚫ Knightmare';
            }

            // Tell server about the change
            fetch('/set_colors', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({white_is_knightmare: whiteIsKnightmare})
            });

            // Start new game with new colors
            newGame();
        }

        function savePgn() {
            // A plain navigation rather than a fetch, so the browser's own
            // download handling names and saves the file
            window.location = '/pgn';
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
                    if (data.error) {
                        console.error(data.error);
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
            // Chained rather than on a timer: Knightmare may think for
            // longer than any fixed interval, and overlapping requests
            // would each play a move for the same side.
            if (!autoPlay) { return; }
            makeMove().then(() => {
                if (autoPlay) {
                    autoTimer = setTimeout(autoStep, AUTO_PLAY_GAP_MS);
                }
            });
        }

        function toggleAuto() {
            if (autoPlay) {
                stopAuto();
            } else {
                autoPlay = true;
                document.getElementById('auto-btn').textContent = '⏸️ Auto Play: ON';
                document.getElementById('auto-btn').className = 'active';
                autoStep();
            }
        }

        function stopAuto() {
            if (autoPlay || autoTimer) {
                autoPlay = false;
                clearTimeout(autoTimer);
                autoTimer = null;
                document.getElementById('auto-btn').textContent = '🔄 Auto Play: OFF';
                document.getElementById('auto-btn').className = '';
            }
        }

        // Load board on startup
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
    global game_board, move_history, stockfish_engine, last_engine_info

    with board_lock:

        # Drawn from your side when you are playing, and otherwise from
        # Knightmare's, so the engine being developed is at the bottom
        if mode == PLAY_MODE:
            flipped = human_colour == chess.BLACK
        else:
            flipped = not app.config.get('white_is_knightmare', False)
        svg = render_board(game_board, flipped=flipped)

        # Determine game status
        if game_board.is_checkmate():
            winner = "White" if game_board.turn == chess.BLACK else "Black"
            if app.config.get('white_is_knightmare', False):
                winner += " (Knightmare)" if winner == "White" else " (Stockfish)"
            else:
                winner += " (Stockfish)" if winner == "White" else " (Knightmare)"
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
            if app.config.get('white_is_knightmare', False):
                turn = "White (Knightmare)" if game_board.turn == chess.WHITE else "Black (Stockfish)"
            else:
                turn = "White (Stockfish)" if game_board.turn == chess.WHITE else "Black (Knightmare)"
            status = f"{turn} to move"
            if game_board.is_check():
                status += " - CHECK!"

        return jsonify({
            'svg': svg,
            'status': status,
            'moves': move_history,
            'game_over': game_board.is_game_over(),
            'white_to_move': game_board.turn == chess.WHITE,
            'stockfish_available': stockfish_engine is not None,
            'engine': last_engine_info,
            'knightmare_is_white': app.config.get('white_is_knightmare', False),
            'mode': mode,
            'colour': 'white' if human_colour == chess.WHITE else 'black',
            'your_turn': human_to_move(),
            # Grouped by origin square, so the interface can show where a
            # piece may go without knowing how chess works
            'legal': legal_by_origin(game_board),
        })

@app.route('/pgn')
def download_pgn():
    """The current game as a PGN file

    Named by which engine is on which side, so a saved game says what was
    actually played rather than just White and Black.
    """
    with board_lock:
        knightmare_white = app.config.get('white_is_knightmare', False)
        stockfish = f'Stockfish level {stockfish_level}'
        white, black = ('Knightmare', stockfish) if knightmare_white else (stockfish, 'Knightmare')
        text = game_pgn(game_board, white, black)

    return Response(
        text,
        mimetype='application/x-chess-pgn',
        headers={'Content-Disposition': 'attachment; filename=knightmare.pgn'},
    )


@app.route('/new_game', methods=['POST'])
def new_game():
    with board_lock:
        reset_game()
    return jsonify({'success': True})

@app.route('/set_stockfish_level', methods=['POST'])
def set_stockfish_level():
    """Set Stockfish skill level, rejecting values it would not accept

    An out-of-range level makes engine.configure() raise, which used to
    leave the opponent quietly playing random moves instead.
    """
    global stockfish_level

    data = request.get_json(silent=True) or {}
    try:
        level = int(data.get('level', MIN_SKILL_LEVEL))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'level must be a number'}), 400

    if not MIN_SKILL_LEVEL <= level <= MAX_SKILL_LEVEL:
        return jsonify({
            'success': False,
            'error': f'level must be between {MIN_SKILL_LEVEL} and {MAX_SKILL_LEVEL}',
        }), 400

    # Under the lock so a setting cannot change halfway through a move
    with board_lock:
        stockfish_level = level
    return jsonify({'success': True, 'level': stockfish_level})

@app.route('/set_stockfish_time', methods=['POST'])
def set_stockfish_time():
    """Set Stockfish thinking time, clamped to a sane range"""
    global stockfish_time

    data = request.get_json(silent=True) or {}
    try:
        think_time = float(data.get('time', MIN_THINK_TIME))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'time must be a number'}), 400

    if not MIN_THINK_TIME <= think_time <= MAX_THINK_TIME:
        return jsonify({
            'success': False,
            'error': f'time must be between {MIN_THINK_TIME} and {MAX_THINK_TIME} seconds',
        }), 400

    with board_lock:
        stockfish_time = think_time
    return jsonify({'success': True, 'time': stockfish_time})

@app.route('/set_colors', methods=['POST'])
def set_colors():
    """Swap which engine plays White

    Under the lock: changing sides mid move would have one engine finish a
    search for a colour it no longer plays.
    """
    data = request.get_json(silent=True) or {}
    with board_lock:
        app.config['white_is_knightmare'] = bool(data.get('white_is_knightmare', False))
    return jsonify({'success': True})

@app.route('/move', methods=['POST'])
def make_move():
    """Play one move for whoever is to move

    Held under board_lock: the dev server is threaded, so overlapping
    requests would each read the same position and all push a move for
    the same side. Auto play makes that routine here, because the
    browser fires every 1500ms while a move can take 2000ms.
    """
    global game_board, move_history, stockfish_level, stockfish_time

    with board_lock:
        if game_board.is_game_over():
            return jsonify({'error': 'Game is over'})

        try:
            white_is_knightmare = app.config.get('white_is_knightmare', False)

            # Determine whose turn it is and which engine to use
            if game_board.turn == chess.WHITE:
                if white_is_knightmare:
                    # Knightmare plays White
                    move = get_knightmare_move(game_board)
                    player = "Knightmare"
                else:
                    # Stockfish plays White
                    move = get_stockfish_move(game_board, stockfish_level, stockfish_time)
                    player = f"Stockfish(L{stockfish_level})"
            else:
                if white_is_knightmare:
                    # Stockfish plays Black
                    move = get_stockfish_move(game_board, stockfish_level, stockfish_time)
                    player = f"Stockfish(L{stockfish_level})"
                else:
                    # Knightmare plays Black
                    move = get_knightmare_move(game_board)
                    player = "Knightmare"

            if move and move in game_board.legal_moves:
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"{san}")  # Just the move notation
                return jsonify({'success': True})
            else:
                return jsonify({'error': f'{player} failed to make valid move'})

        except Exception as e:
            print(f"Error in make_move: {e}")
            # Fallback to random move
            moves = list(game_board.legal_moves)
            if moves:
                move = random.choice(moves)
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"{san}")
                return jsonify({'success': True})
            return jsonify({'error': str(e)})


def stop_process_soon(delay=0.5):
    """Exit once the current response has had time to reach the browser"""
    def stopper():
        time.sleep(delay)
        os._exit(0)

    threading.Thread(target=stopper, daemon=True).start()


@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Stop the server and the Stockfish subprocess

    Werkzeug removed the request-time 'werkzeug.server.shutdown' hook in
    2.1 and offers no replacement, so shut the engine down here and then
    stop the process from a helper thread.
    """
    if stockfish_engine:
        stockfish_engine.quit()
    stop_process_soon()
    return 'Server shutting down...'

def parse_args():
    """Parse command line options"""
    parser = argparse.ArgumentParser(description="Web UI for Knightmare vs Stockfish")
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
    print("Knightmare vs Stockfish Web Interface")
    print("="*60)

    # Check for Knightmare
    if bot_class:
        print("✅ Knightmare bot loaded successfully!")
        print(f"   Bot class: {bot_class.__name__}")
    else:
        print("⚠️  Knightmare bot not found - using random moves")

    # Check for Stockfish
    if find_stockfish():
        print("✅ Stockfish engine initialized!")
        print(f"   Default level: {stockfish_level} "
              f"(adjustable {MIN_SKILL_LEVEL}-{MAX_SKILL_LEVEL})")
        print(f"   Default time: {stockfish_time}s per move")
    else:
        print("⚠️  Stockfish not available - opponent will use random moves")
        print("\nTo install Stockfish:")
        print("   Mac: brew install stockfish")
        print("   Linux: sudo apt-get install stockfish")
        print("   Windows: Download from stockfishchess.org")

    # Set default colors
    app.config['white_is_knightmare'] = False

    print("\n" + "="*60)
    print(f"Open your browser to: http://{args.host}:{args.port}")
    print("="*60)
    print("\nFeatures:")
    print(f"• Adjustable Stockfish difficulty ({MIN_SKILL_LEVEL}-{MAX_SKILL_LEVEL})")
    print("• Configurable thinking time")
    print("• Choose who plays White/Black")
    print("• Auto-play mode")
    print("• Move history tracking")
    print("="*60 + "\n")

    try:
        app.run(debug=args.debug, host=args.host, port=args.port)
    finally:
        if stockfish_engine:
            stockfish_engine.quit()