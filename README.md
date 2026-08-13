# Intelligent Chess AI Platform ♟️🤖

**A unified chess platform featuring both a Classical Minimax Engine and an Experimental LLM-based Agent.**

This project merges two distinct approaches to computer chess:
1.  **Classic Agent (Knightmare)**: A high-performance Minimax engine with Alpha-Beta pruning (100% win rate vs random).
2.  **LLM Agent (ChessGPT)**: An experimental bot that uses Large Language Models (via Ollama) to decide moves.

## 📂 Project Structure

```
Intelligent-Chess-AI/
├── classic_agent/            # Knightmare Engine & Web UI
│   ├── knightmare_bot.py     # Core Minimax Logic
│   ├── simple_web_chess.py   # Web Interface
│   ├── simple_tournament.py  # Tournament Runner (PGN output)
│   ├── test_evaluation.py    # Evaluation & Search Unit Tests
│   ├── test_bots.py          # UCI Protocol Smoke Test
│   └── ...
├── llm_agent/                # LLM-based Bots (Ollama)
│   ├── knightmare_llm.py     # LLM Bot Logic
│   ├── tournament.py         # Multi-bot Tournament
│   └── ...
├── requirements.txt          # Unified Dependencies
└── README.md                 # Documentation
```

## 🚀 Quick Start

### Prerequisites

1.  **Python 3.8+**
2.  **Ollama** (Required for LLM Agent)
    *   [Download Ollama](https://ollama.com/)
    *   Pull models: `ollama run llama3.2` (or mistral)
3.  **Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

---

## ♟️ Classic Agent (Knightmare)

An intelligent chess AI implementing minimax with alpha-beta pruning.

### Key Features
*   **Strength**: Beat random bots 20/20 games.
*   **Search**: Minimax with Alpha-Beta pruning, Iterative Deepening.
*   **Optimizations**: Killer Moves, History Heuristic, Quiescence Search.
*   **Evaluation**: Material, pawn advancement, piece centralization, bishop pair, mobility.

### Usage

**Web Interface (vs Random)**
```bash
cd classic_agent
python simple_web_chess.py
# Open http://localhost:5001
```

**Play Against Stockfish**
```bash
cd classic_agent
python knightmare_vs_stockfish.py
# Open http://localhost:5002
```

**Run Tournament**
```bash
cd classic_agent
python simple_tournament.py 20                 # 20 games, 1s per move
python simple_tournament.py 20 --time 500      # faster games
python simple_tournament.py 20 --pgn games.pgn # choose the PGN output path
```
Every game is written to `tournament.pgn` by default so results can be replayed.

**Run Tests**
```bash
cd classic_agent
python -m unittest test_evaluation   # evaluation and search unit tests
python test_bots.py                  # UCI protocol smoke test
```

---

## 🤖 LLM Agent (ChessGPT)

An experimental agent that prompts local LLMs to play chess.

### Key Features
*   **Ollama Integration**: Runs locally with models like llama3.2.
*   **Prompt Engineering**: Explores different prompting strategies (UCI vs Algebraic).
*   **Resiliency**: Implements retry logic for invalid LLM moves.

### Usage

**Run LLM Bot**
*Ensure Ollama is running (`ollama serve`).*

```bash
cd llm_agent
# Example script usage (adjust based on specific script needs)
python knightmare_llm.py
```
*(Note: You may need to edit the script to select your specific model name)*

---

## 🏆 Performance Comparison

| Agent | Technology | Win Rate (vs Random) | Notes |
| :--- | :--- | :--- | :--- |
| **Knightmare** | Minimax + Alpha-Beta | **100%** | Highly tactical, reliable. |
| **ChessGPT** | Llama 3.2 (Prompted) | ~4% | Experimental, struggles with exact syntax. |

## 👨‍💻 Author

**Vatsal Patel**
*   [LinkedIn](https://linkedin.com/in/vatsalp20)
*   [GitHub](https://github.com/vatsalp2008)

---
*Merged and Unified - Jan 2026*