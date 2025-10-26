#!/usr/bin/env python3
"""
Knightmare vs Stockfish Web Interface
Test your bot against the world's strongest chess engine
"""

from flask import Flask, render_template_string, jsonify, request
import chess
import chess.svg
import chess.engine
import random
import time
import sys
import os
import subprocess

# Add the current directory to path to import knightmare_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Knightmare bot class directly
try:
    import knightmare_bot
    
    # Find the bot class
    bot_class = None
    for name in dir(knightmare_bot):
        obj = getattr(knightmare_bot, name)
        if isinstance(obj, type) and 'Knightmare' in name:
            bot_class = obj
            break
    
    if not bot_class:
        print("Warning: Could not find Knightmare class in knightmare_bot.py")
        bot_class = None
except Exception as e:
    print(f"Warning: Could not import knightmare_bot.py: {e}")
    bot_class = None

app = Flask(__name__)

# Global game state
game_board = chess.Board()
move_history = []
knightmare = None
stockfish_engine = None
stockfish_level = 1  # 1-20 (1 is easiest)
stockfish_time = 0.1  # Time in seconds for Stockfish to think

def find_stockfish():
    """Try to find and initialize Stockfish"""
    global stockfish_engine
    
    # Common Stockfish locations
    stockfish_paths = [
        "stockfish",  # In PATH
        "/usr/local/bin/stockfish",  # Mac/Linux homebrew
        "/opt/homebrew/bin/stockfish",  # Mac M1 homebrew
        "/usr/bin/stockfish",  # Linux apt
        "/usr/games/stockfish",  # Ubuntu/Debian
        "C:\\Program Files\\Stockfish\\stockfish.exe",  # Windows
    ]
    
    for path in stockfish_paths:
        try:
            # Test if stockfish exists at this path
            result = subprocess.run([path, "help"], capture_output=True, timeout=1)
            if result.returncode == 0 or "Stockfish" in str(result.stdout):
                stockfish_engine = chess.engine.SimpleEngine.popen_uci(path)
                print(f"✅ Stockfish found at: {path}")
                return True
        except:
            continue
    
    print("❌ Stockfish not found. Please install it:")
    print("   Mac: brew install stockfish")
    print("   Ubuntu/Debian: sudo apt-get install stockfish")
    print("   Windows: Download from https://stockfishchess.org/download/")
    return False

def reset_game():
    global game_board, move_history, knightmare
    game_board = chess.Board()
    move_history = []
    if bot_class:
        knightmare = bot_class()

def get_knightmare_move(board):
    """Get move from Knightmare bot"""
    global knightmare
    
    if not bot_class:
        # Fallback to random if bot not available
        moves = list(board.legal_moves)
        return random.choice(moves) if moves else None
    
    try:
        if not knightmare:
            knightmare = bot_class()
        
        # Try different method names that might exist
        if hasattr(knightmare, 'get_best_move'):
            return knightmare.get_best_move(board.copy(), max_time=2.0)
        elif hasattr(knightmare, 'get_move'):
            return knightmare.get_move(board.copy(), 2.0)
        else:
            # Try minimax directly
            if hasattr(knightmare, 'minimax'):
                _, move = knightmare.minimax(
                    board.copy(), 
                    4,  # depth
                    -float('inf'), 
                    float('inf'), 
                    board.turn == chess.WHITE
                )
                return move
    except Exception as e:
        print(f"Error getting Knightmare move: {e}")
    
    # Fallback to random
    moves = list(board.legal_moves)
    return random.choice(moves) if moves else None

def get_stockfish_move(board, level=1, think_time=0.1):
    """Get move from Stockfish"""
    global stockfish_engine
    
    if not stockfish_engine:
        # Fallback to random if Stockfish not available
        moves = list(board.legal_moves)
        return random.choice(moves) if moves else None
    
    try:
        # Configure Stockfish strength (1-20)
        stockfish_engine.configure({"Skill Level": level})
        
        # Get move with time limit
        result = stockfish_engine.play(board, chess.engine.Limit(time=think_time))
        return result.move
    except Exception as e:
        print(f"Error getting Stockfish move: {e}")
        moves = list(board.legal_moves)
        return random.choice(moves) if moves else None

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
            
            <button onclick="newGame()">🆕 New Game</button>
            <button onclick="makeMove()">▶️ Make Move</button>
            <button onclick="toggleAuto()" id="auto-btn">🔄 Auto Play: OFF</button>
            
            <h3>📋 Move History</h3>
            <div id="moves"></div>
        </div>
    </div>
    
    <script>
        let autoPlay = null;
        let stockfishLevel = 1;
        let stockfishTime = 0.1;
        let whiteIsKnightmare = false;
        
        function updateBoard() {
            fetch('/board')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('board').innerHTML = data.svg;
                    
                    // Update status with styling
                    const statusEl = document.getElementById('status');
                    statusEl.textContent = data.status;
                    statusEl.className = '';
                    
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
        
        function newGame() {
            stopAuto();
            fetch('/new_game', {method: 'POST'})
                .then(() => updateBoard());
        }
        
        function makeMove() {
            fetch('/move', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error(data.error);
                    }
                    updateBoard();
                });
        }
        
        function toggleAuto() {
            if (autoPlay) {
                stopAuto();
            } else {
                document.getElementById('auto-btn').textContent = '⏸️ Auto Play: ON';
                document.getElementById('auto-btn').className = 'active';
                autoPlay = setInterval(makeMove, 1500);
                makeMove();  // Make first move immediately
            }
        }
        
        function stopAuto() {
            if (autoPlay) {
                clearInterval(autoPlay);
                autoPlay = null;
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
    global game_board, move_history, stockfish_engine
    
    svg = chess.svg.board(game_board, size=500)
    
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
        'stockfish_available': stockfish_engine is not None
    })

@app.route('/new_game', methods=['POST'])
def new_game():
    reset_game()
    return jsonify({'success': True})

@app.route('/set_stockfish_level', methods=['POST'])
def set_stockfish_level():
    global stockfish_level
    data = request.get_json()
    stockfish_level = data.get('level', 1)
    return jsonify({'success': True})

@app.route('/set_stockfish_time', methods=['POST'])
def set_stockfish_time():
    global stockfish_time
    data = request.get_json()
    stockfish_time = data.get('time', 0.1)
    return jsonify({'success': True})

@app.route('/set_colors', methods=['POST'])
def set_colors():
    data = request.get_json()
    app.config['white_is_knightmare'] = data.get('white_is_knightmare', False)
    return jsonify({'success': True})

@app.route('/move', methods=['POST'])
def make_move():
    global game_board, move_history, stockfish_level, stockfish_time
    
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

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if stockfish_engine:
        stockfish_engine.quit()
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Server shutting down...'

if __name__ == '__main__':
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
        print(f"   Default level: {stockfish_level} (adjustable 1-20)")
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
    print("Open your browser to: http://localhost:5002")
    print("="*60)
    print("\nFeatures:")
    print("• Adjustable Stockfish difficulty (1-20)")
    print("• Configurable thinking time")
    print("• Choose who plays White/Black")
    print("• Auto-play mode")
    print("• Move history tracking")
    print("="*60 + "\n")
    
    try:
        app.run(debug=False, port=5002)
    finally:
        if stockfish_engine:
            stockfish_engine.quit()