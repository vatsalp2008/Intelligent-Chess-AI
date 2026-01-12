#!/usr/bin/env python3
"""
Simple Web Chess Interface - Direct Integration
Works directly with the Knightmare bot code without UCI
"""

from flask import Flask, render_template_string, jsonify, request
import chess
import chess.svg
import random
import time
import sys
import os

# Add the current directory to path to import knightmare_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the KnightmareOptimized class directly
try:
    # Try to import from your working knightmare_bot.py
    import knightmare_bot
    
    # Find the bot class (it might be named differently)
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
            return knightmare.get_best_move(board.copy(), max_time=1.0)
        elif hasattr(knightmare, 'get_move'):
            return knightmare.get_move(board.copy(), 1.0)
        else:
            # Try minimax directly
            if hasattr(knightmare, 'minimax'):
                _, move = knightmare.minimax(
                    board.copy(), 
                    3,  # depth
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

def get_random_move(board):
    """Get random move"""
    moves = list(board.legal_moves)
    return random.choice(moves) if moves else None

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
        .board-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
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
            
            <button onclick="newGame()">New Game</button>
            <button onclick="makeMove()">Make Move</button>
            <button onclick="toggleAuto()" id="auto-btn">Auto Play: OFF</button>
            
            <h3>Move History</h3>
            <div id="moves"></div>
        </div>
    </div>
    
    <script>
        let autoPlay = null;
        
        function updateBoard() {
            fetch('/board')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('board').innerHTML = data.svg;
                    document.getElementById('status').textContent = data.status;
                    
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
                    
                    // Stop auto play if game over
                    if (data.game_over && autoPlay) {
                        stopAuto();
                    }
                });
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
                        alert(data.error);
                    }
                    updateBoard();
                });
        }
        
        function toggleAuto() {
            if (autoPlay) {
                stopAuto();
            } else {
                document.getElementById('auto-btn').textContent = 'Auto Play: ON';
                document.getElementById('auto-btn').className = 'active';
                autoPlay = setInterval(makeMove, 1000);
                makeMove();  // Make first move immediately
            }
        }
        
        function stopAuto() {
            if (autoPlay) {
                clearInterval(autoPlay);
                autoPlay = null;
                document.getElementById('auto-btn').textContent = 'Auto Play: OFF';
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
    global game_board, move_history
    
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
        turn = "White (Random)" if game_board.turn == chess.WHITE else "Black (Knightmare)"
        status = f"{turn} to move"
        if game_board.is_check():
            status += " - CHECK!"
    
    return jsonify({
        'svg': svg,
        'status': status,
        'moves': move_history,
        'game_over': game_board.is_game_over(),
        'white_to_move': game_board.turn == chess.WHITE
    })

@app.route('/new_game', methods=['POST'])
def new_game():
    reset_game()
    return jsonify({'success': True})

@app.route('/move', methods=['POST'])
def make_move():
    global game_board, move_history
    
    if game_board.is_game_over():
        return jsonify({'error': 'Game is over'})
    
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
            move_history.append(f"Emergency: {san}")
            return jsonify({'success': True})
        return jsonify({'error': str(e)})

if __name__ == '__main__':
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
    
    print("\nOpen your browser to: http://localhost:5001")
    print("="*60 + "\n")
    
    app.run(debug=False, port=5001)