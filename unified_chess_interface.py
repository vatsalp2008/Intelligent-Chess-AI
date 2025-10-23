#!/usr/bin/env python3
"""
Unified Chess Web Interface - Fixed Version
Properly handles illegal moves and game state validation
"""

from flask import Flask, render_template_string, jsonify, request
import chess
import chess.svg
import chess.engine
import random
import time
import traceback

# Import the fixed Knightmare bot
try:
    from knightmare_bot import KnightmareFast
    KnightmareClass = KnightmareFast
except ImportError:
    print("Warning: knightmare_bot.py not found")
    KnightmareClass = None

app = Flask(__name__)

# Global game state
game_board = chess.Board()
knightmare_bot = None
move_history = []
stockfish_engine = None
current_game_type = "knightmare_vs_random"

# Try to initialize Stockfish
def init_stockfish():
    global stockfish_engine
    try:
        for path in ["stockfish", "/usr/local/bin/stockfish", "/opt/homebrew/bin/stockfish"]:
            try:
                stockfish_engine = chess.engine.SimpleEngine.popen_uci(path)
                print(f"✓ Stockfish found at: {path}")
                return True
            except:
                continue
        print("✗ Stockfish not found - Stockfish option will be disabled")
        return False
    except Exception as e:
        print(f"✗ Error initializing Stockfish: {e}")
        return False

# Reset game state
def reset_game():
    global game_board, knightmare_bot, move_history
    game_board = chess.Board()
    if KnightmareClass:
        knightmare_bot = KnightmareClass()
    move_history = []

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Chess Bot Arena</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 3em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        .main-content {
            display: flex;
            gap: 30px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .board-section {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .control-panel {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            min-width: 350px;
        }
        #board {
            margin: 10px 0;
        }
        .game-selector {
            background: #f0f8ff;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border: 2px solid #1e3c72;
        }
        .game-option {
            display: flex;
            align-items: center;
            margin: 10px 0;
            padding: 15px;
            background: white;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid transparent;
        }
        .game-option:hover {
            transform: translateX(5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .game-option.selected {
            border-color: #2a5298;
            background: #e8f4f8;
        }
        .game-option input[type="radio"] {
            margin-right: 15px;
            width: 20px;
            height: 20px;
        }
        .game-description {
            flex: 1;
        }
        .game-title {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .game-subtitle {
            color: #666;
            font-size: 0.9em;
        }
        .start-button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.2em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 10px;
        }
        .start-button:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 15px rgba(76, 175, 80, 0.3);
        }
        button {
            padding: 10px 20px;
            margin: 5px;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        button.active {
            background: linear-gradient(135deg, #e91e63, #c2185b);
        }
        #status {
            padding: 15px;
            background: #f5f5f5;
            border-radius: 8px;
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
        #status.error {
            background: #f8d7da;
            color: #721c24;
            border: 2px solid #f5c6cb;
        }
        #moves {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 8px;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
        }
        .move-entry {
            padding: 5px;
            border-bottom: 1px solid #e0e0e0;
        }
        .move-entry:hover {
            background: #e8f4f8;
        }
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 10px 0;
        }
        select {
            padding: 8px;
            font-size: 14px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        .info-section {
            margin: 20px 0;
        }
        .info-section h3 {
            color: #1e3c72;
            border-bottom: 2px solid #1e3c72;
            padding-bottom: 5px;
        }
        .player-info {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            background: #f0f8ff;
            border-radius: 5px;
            margin: 5px 0;
        }
        .player-info.active {
            background: #1e3c72;
            color: white;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        .stockfish-warning {
            background: #fff3cd;
            color: #856404;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            border: 1px solid #ffc107;
        }
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            border: 1px solid #f5c6cb;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>♚ Chess Bot Arena ♔</h1>
            <p>Test Your Knightmare AI Against Different Opponents</p>
        </div>
        
        <div id="errorMessage" class="error-message"></div>
        
        <div class="main-content">
            <div class="board-section">
                <div id="board">Loading board...</div>
                <div class="controls">
                    <button onclick="newGame()">New Game</button>
                    <button onclick="toggleAutoPlay()" id="autoBtn">Auto Play: OFF</button>
                    <select id="speedSelect" onchange="updateSpeed()">
                        <option value="500">Fast (0.5s)</option>
                        <option value="1000" selected>Normal (1s)</option>
                        <option value="2000">Slow (2s)</option>
                    </select>
                </div>
            </div>
            
            <div class="control-panel">
                <div class="game-selector">
                    <h3>Choose Your Battle</h3>
                    
                    <div class="game-option selected" onclick="selectGame('knightmare_vs_random')">
                        <input type="radio" name="game_type" value="knightmare_vs_random" checked>
                        <div class="game-description">
                            <div class="game-title">Knightmare vs Random</div>
                            <div class="game-subtitle">Test your AI against random moves</div>
                        </div>
                    </div>
                    
                    <div class="game-option" onclick="selectGame('knightmare_vs_stockfish')" id="stockfish_option">
                        <input type="radio" name="game_type" value="knightmare_vs_stockfish">
                        <div class="game-description">
                            <div class="game-title">Knightmare vs Stockfish</div>
                            <div class="game-subtitle">Challenge the world's best engine</div>
                        </div>
                    </div>
                    
                    <div id="stockfish_warning" class="stockfish-warning" style="display: none;">
                        ⚠️ Stockfish not found. Install with: brew install stockfish
                    </div>
                    
                    <button class="start-button" onclick="startSelectedGame()">
                        Start New Game
                    </button>
                </div>
                
                <div class="info-section">
                    <h3>Players</h3>
                    <div class="player-info" id="whitePlayer">
                        <span id="whiteName">Random Bot</span>
                        <span>♔ White</span>
                    </div>
                    <div class="player-info" id="blackPlayer">
                        <span id="blackName">Knightmare</span>
                        <span>♚ Black</span>
                    </div>
                </div>
                
                <div class="info-section">
                    <h3>Game Status</h3>
                    <div id="status">Ready to start</div>
                </div>
                
                <div class="info-section">
                    <h3>Move History</h3>
                    <div id="moves"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let autoPlayInterval = null;
        let moveSpeed = 1000;
        let selectedGameType = 'knightmare_vs_random';
        let stockfishAvailable = false;
        
        // Check if Stockfish is available on page load
        fetch('/check_stockfish')
            .then(response => response.json())
            .then(data => {
                stockfishAvailable = data.available;
                if (!stockfishAvailable) {
                    document.getElementById('stockfish_warning').style.display = 'block';
                    document.getElementById('stockfish_option').style.opacity = '0.5';
                }
            });
        
        function showError(message) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
        
        function selectGame(gameType) {
            if (gameType === 'knightmare_vs_stockfish' && !stockfishAvailable) {
                alert('Stockfish is not available. Please install it first.');
                return;
            }
            
            selectedGameType = gameType;
            document.querySelectorAll('.game-option').forEach(option => {
                option.classList.remove('selected');
            });
            event.currentTarget.classList.add('selected');
            document.querySelector(`input[value="${gameType}"]`).checked = true;
            
            // Update player names preview
            if (gameType === 'knightmare_vs_random') {
                document.getElementById('whiteName').textContent = 'Random Bot';
            } else {
                document.getElementById('whiteName').textContent = 'Stockfish';
            }
        }
        
        function startSelectedGame() {
            stopAutoPlay();
            fetch('/new_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_type: selectedGameType})
            }).then(() => {
                updateBoard();
                // Auto-start playing
                setTimeout(() => toggleAutoPlay(), 500);
            });
        }
        
        function updateBoard() {
            fetch('/board')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showError(data.error);
                        if (data.reset) {
                            // Game was reset due to invalid state
                            setTimeout(() => newGame(), 1000);
                        }
                        return;
                    }
                    
                    document.getElementById('board').innerHTML = data.svg;
                    document.getElementById('status').innerHTML = data.status;
                    
                    // Update status styling
                    const statusEl = document.getElementById('status');
                    statusEl.className = '';
                    if (data.status.includes('Check') && !data.game_over) {
                        statusEl.className = 'check';
                    } else if (data.game_over) {
                        statusEl.className = 'checkmate';
                    } else if (data.status.includes('Error')) {
                        statusEl.className = 'error';
                    }
                    
                    // Update moves
                    document.getElementById('moves').innerHTML = data.moves.map((m, i) => 
                        `<div class="move-entry">${Math.floor(i/2) + 1}. ${m}</div>`
                    ).join('');
                    document.getElementById('moves').scrollTop = document.getElementById('moves').scrollHeight;
                    
                    // Update active player
                    if (data.white_to_move !== undefined) {
                        document.getElementById('whitePlayer').classList.toggle('active', data.white_to_move);
                        document.getElementById('blackPlayer').classList.toggle('active', !data.white_to_move);
                    }
                    
                    // Stop auto-play if game is over
                    if (data.game_over && autoPlayInterval) {
                        stopAutoPlay();
                        setTimeout(() => {
                            if (confirm(data.status + '\\n\\nStart a new game?')) {
                                startSelectedGame();
                            }
                        }, 1000);
                    }
                })
                .catch(error => {
                    showError('Error updating board: ' + error.message);
                });
        }
        
        function newGame() {
            stopAutoPlay();
            fetch('/new_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_type: selectedGameType})
            }).then(() => updateBoard());
        }
        
        function makeMove() {
            fetch('/move', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showError(data.error);
                        if (data.reset) {
                            // Game was reset, start new game
                            setTimeout(() => newGame(), 1000);
                        }
                    } else {
                        updateBoard();
                    }
                });
        }
        
        function toggleAutoPlay() {
            if (autoPlayInterval) {
                stopAutoPlay();
            } else {
                document.getElementById('autoBtn').textContent = 'Auto Play: ON';
                document.getElementById('autoBtn').classList.add('active');
                autoPlayInterval = setInterval(makeMove, moveSpeed);
                makeMove(); // Make first move immediately
            }
        }
        
        function stopAutoPlay() {
            if (autoPlayInterval) {
                clearInterval(autoPlayInterval);
                autoPlayInterval = null;
                document.getElementById('autoBtn').textContent = 'Auto Play: OFF';
                document.getElementById('autoBtn').classList.remove('active');
            }
        }
        
        function updateSpeed() {
            moveSpeed = parseInt(document.getElementById('speedSelect').value);
            if (autoPlayInterval) {
                stopAutoPlay();
                toggleAutoPlay();
            }
        }
        
        // Initialize board on load
        updateBoard();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/check_stockfish')
def check_stockfish():
    return jsonify({'available': stockfish_engine is not None})

@app.route('/board')
def get_board():
    global game_board, move_history
    
    try:
        # Check for invalid game state
        if game_board.king(chess.WHITE) is None or game_board.king(chess.BLACK) is None:
            reset_game()
            return jsonify({
                'error': 'Invalid game state detected - game has been reset',
                'reset': True,
                'svg': chess.svg.board(game_board, size=500),
                'status': 'Game reset due to invalid state',
                'moves': [],
                'game_over': False,
                'white_to_move': True
            })
        
        svg = chess.svg.board(game_board, size=500)
        
        if game_board.is_checkmate():
            winner = "White" if game_board.turn == chess.BLACK else "Black"
            status = f"Checkmate! {winner} wins!"
        elif game_board.is_stalemate():
            status = "Stalemate - Draw!"
        elif game_board.is_insufficient_material():
            status = "Draw - Insufficient material"
        elif game_board.is_fifty_moves():
            status = "Draw - Fifty move rule"
        elif game_board.can_claim_threefold_repetition():
            status = "Draw - Threefold repetition"
        elif game_board.is_game_over():
            status = "Game Over!"
        elif game_board.is_check():
            status = f"{'White' if game_board.turn else 'Black'} to move - Check!"
        else:
            status = f"{'White' if game_board.turn else 'Black'} to move"
        
        return jsonify({
            'svg': svg,
            'status': status,
            'moves': move_history,
            'game_over': game_board.is_game_over(),
            'white_to_move': game_board.turn == chess.WHITE
        })
    except Exception as e:
        print(f"Error in get_board: {e}")
        reset_game()
        return jsonify({
            'error': f'Board error: {str(e)}',
            'reset': True,
            'svg': chess.svg.board(game_board, size=500),
            'status': 'Error - game reset',
            'moves': [],
            'game_over': False,
            'white_to_move': True
        })

@app.route('/new_game', methods=['POST'])
def new_game():
    global game_board, move_history, current_game_type, knightmare_bot
    
    data = request.get_json() if request.is_json else {}
    current_game_type = data.get('game_type', 'knightmare_vs_random')
    
    # Reset everything
    game_board = chess.Board()
    move_history = []
    
    # Create fresh bot instance
    if KnightmareClass:
        knightmare_bot = KnightmareClass()
    
    print(f"Starting new game: {current_game_type}")
    return jsonify({'success': True})

@app.route('/move', methods=['POST'])
def make_move():
    global game_board, move_history, knightmare_bot, stockfish_engine, current_game_type
    
    if game_board.is_game_over():
        return jsonify({'error': 'Game is over'})
    
    # Verify game state is valid
    if game_board.king(chess.WHITE) is None or game_board.king(chess.BLACK) is None:
        print("ERROR: King is missing! Resetting game.")
        reset_game()
        return jsonify({'error': 'Invalid game state - king missing', 'reset': True})
    
    try:
        if game_board.turn == chess.WHITE:
            # White's turn - either Random or Stockfish
            if current_game_type == 'knightmare_vs_stockfish' and stockfish_engine:
                try:
                    result = stockfish_engine.play(game_board, chess.engine.Limit(time=0.1))
                    move = result.move
                    player = "Stockfish"
                except Exception as e:
                    print(f"Stockfish error: {e}")
                    # Fallback to random
                    legal_moves = list(game_board.legal_moves)
                    move = random.choice(legal_moves) if legal_moves else None
                    player = "Random (Stockfish failed)"
            else:
                # Random bot
                legal_moves = list(game_board.legal_moves)
                if not legal_moves:
                    return jsonify({'error': 'No legal moves available'})
                move = random.choice(legal_moves)
                player = "Random"
        else:
            # Black's turn - always Knightmare
            if knightmare_bot:
                # Pass a copy to avoid side effects
                board_copy = game_board.copy()
                move = knightmare_bot.get_best_move(board_copy, max_time=1.0)
                player = "Knightmare"
            else:
                # Fallback if bot not initialized
                legal_moves = list(game_board.legal_moves)
                move = random.choice(legal_moves) if legal_moves else None
                player = "Random (Knightmare failed)"
        
        # Verify move is legal
        if move and move in game_board.legal_moves:
            # Additional safety check - ensure move won't capture king
            test_board = game_board.copy()
            test_board.push(move)
            
            if test_board.king(chess.WHITE) is None or test_board.king(chess.BLACK) is None:
                print(f"ERROR: Move {move} would capture a king!")
                # Find a safe move
                for safe_move in game_board.legal_moves:
                    test_board = game_board.copy()
                    test_board.push(safe_move)
                    if test_board.king(chess.WHITE) and test_board.king(chess.BLACK):
                        move = safe_move
                        player += " (safe fallback)"
                        break
                else:
                    return jsonify({'error': 'No safe moves available'})
            
            # Make the move
            san = game_board.san(move)
            game_board.push(move)
            move_history.append(f"{player}: {san}")
            
            return jsonify({'success': True})
        else:
            # Move is not legal
            print(f"Illegal move attempted: {move}")
            print(f"Current position: {game_board.fen()}")
            
            # Try to find any legal move
            legal_moves = list(game_board.legal_moves)
            if legal_moves:
                move = random.choice(legal_moves)
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"Emergency: {san}")
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'No legal moves available'})
        
    except Exception as e:
        print(f"Error in move generation: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        
        # Emergency fallback
        try:
            legal_moves = list(game_board.legal_moves)
            if legal_moves:
                move = random.choice(legal_moves)
                san = game_board.san(move)
                game_board.push(move)
                move_history.append(f"Emergency: {san}")
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Critical error - no moves available'})
        except:
            reset_game()
            return jsonify({'error': 'Critical error - game reset', 'reset': True})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if stockfish_engine:
        stockfish_engine.quit()
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Server shutting down...'

if __name__ == '__main__':
    # Initialize Stockfish if available
    has_stockfish = init_stockfish()
    
    # Initialize Knightmare bot
    if KnightmareClass:
        knightmare_bot = KnightmareClass()
        print("✓ Knightmare bot initialized")
    else:
        print("✗ Knightmare bot not found")
    
    print("\n" + "="*60)
    print("Chess Bot Arena - Web Interface")
    print("="*60)
    
    if has_stockfish:
        print("✓ Stockfish is available")
        print("  You can play: Knightmare vs Random OR Knightmare vs Stockfish")
    else:
        print("✗ Stockfish not found")
        print("  You can play: Knightmare vs Random")
        print("\nTo enable Knightmare vs Stockfish:")
        print("  Mac: brew install stockfish")
        print("  Linux: apt-get install stockfish")
    
    print("\n" + "="*60)
    print("Open your browser to: http://localhost:5000")
    print("="*60 + "\n")
    
    try:
        app.run(debug=False, port=5000)
    finally:
        if stockfish_engine:
            stockfish_engine.quit()