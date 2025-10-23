# Knightmare Chess Engine ♟️

A chess engine implementing minimax search with alpha-beta pruning, built to explore adversarial search algorithms and game AI.

## Overview

Knightmare is a chess engine that plays competitively using classic game tree search techniques. It combines traditional chess programming concepts from Claude Shannon's pioneering 1950 paper with modern optimizations.

### Key Features

- **Minimax Algorithm** with configurable search depth
- **Alpha-Beta Pruning** for efficient branch elimination  
- **Iterative Deepening** for robust time management
- **Move Ordering** to maximize pruning effectiveness
- **Opening Book** for common opening positions
- **UCI Protocol** compatible with standard chess GUIs

## Performance Metrics

- Win rate: ~90% vs random play
- Tournament testing: 18-2 record
- Search efficiency: 45% reduction in nodes evaluated with alpha-beta
- Evaluation speed: 1000-5000 positions/second

## Quick Start

### Installation
```bash
# Core dependencies
pip install chess pyinstaller networkx matplotlib

# Optional: Web interface
pip install flask

# Optional: For testing against Stockfish
brew install stockfish  # Mac
apt-get install stockfish  # Linux
```

### Running the Engine
```bash
# Direct execution
python knightmare_bot.py

# Web interface (recommended)
python unified_chess_interface.py
# Navigate to http://localhost:5000
```

### Play a Tournament
```bash
# Run automated matches
python tournament_mac.py
```

## Technical Implementation

### Evaluation Function

The position evaluator combines:
- **Material Balance**: Piece values based on Shannon's recommendations
- **Piece Activity**: Central control and mobility bonuses
- **King Safety**: Dynamic evaluation based on game phase
- **Pawn Structure**: Advancement bonuses for passed pawns

### Search Strategy

The engine employs several optimization techniques:

1. **Alpha-Beta Pruning**: Cuts branches that provably won't affect the outcome
2. **Move Ordering**: Examines forcing moves (captures, checks) first
3. **Iterative Deepening**: Progressively deeper searches within time limits
4. **Quiescence Search**: (Planned) Extend search in tactical positions

## Architecture
```
knightmare_bot.py         # Main engine implementation
unified_chess_interface.py # Web-based GUI
tournament_mac.py          # Automated testing framework
standalone_tree_viz.py     # Search tree visualization
random_chess_bot.py        # Baseline opponent
```

## Search Tree Visualization

The project includes visual analysis tools showing:
- Complete minimax tree exploration
- Alpha-beta pruning in action
- Node evaluation propagation

Generate visualizations with:
```bash
python knightmare_bot.py draw
```

## Current Limitations

- **Tactical Horizon**: 4-ply lookahead may miss deep combinations
- **Endgame Knowledge**: No tablebase integration
- **Positional Play**: Limited long-term strategic planning

## Roadmap

- [ ] Transposition table for position caching
- [ ] Quiescence search for tactical stability
- [ ] Endgame tablebase integration
- [ ] Neural network evaluation experiments
- [ ] Opening book expansion

## Testing

Run comprehensive testing suite:
```bash
# Modify max_games in tournament_mac.py for different sample sizes
python tournament_mac.py
```

## Contributing

This is an active project exploring classical AI techniques in game playing. Suggestions and improvements are welcome.

## References

- Shannon, C.E. (1950). "Programming a Computer for Playing Chess"
- Chess Programming Wiki: https://www.chessprogramming.org/
- Python-Chess Documentation: https://python-chess.readthedocs.io/

## Author

**Vatsal Patel**  
[GitHub](https://github.com/yourusername)

---

*Exploring adversarial search and game AI through chess*