from flask import Flask, render_template_string
import chess
import chess.svg

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple Chess Viewer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            text-align: center;
        }
        #board-container {
            margin: 20px auto;
        }
        button {
            padding: 10px 20px;
            margin: 10px;
            font-size: 16px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>Chess Game Viewer</h1>
    <div id="board-container">
        {{ board_svg|safe }}
    </div>
    <div>
        <button onclick="location.reload()">Refresh Board</button>
    </div>
    <p>Move {{ move_num }}: {{ status }}</p>
</body>
</html>
"""

@app.route('/')
def index():
    board = chess.Board()
    # Make a few random moves to show something happening
    import random
    for i in range(5):
        if not board.is_game_over():
            move = random.choice(list(board.legal_moves))
            board.push(move)
    
    svg = chess.svg.board(board, size=400)
    status = "Game in progress" if not board.is_game_over() else "Game over"
    
    return render_template_string(HTML_TEMPLATE, 
                                 board_svg=svg, 
                                 move_num=len(board.move_stack),
                                 status=status)

if __name__ == '__main__':
    print("Open http://localhost:5003 in your browser")
    app.run(port=5003, debug=True)
