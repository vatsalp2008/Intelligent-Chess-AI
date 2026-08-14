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
│   ├── knightmare.py         # Minimax Baseline Opponent
│   ├── test_knightmare.py    # Baseline Search Unit Tests
│   ├── tournament.py         # Multi-bot Tournament
│   └── ...
├── requirements.txt          # Unified Dependencies
├── requirements-dev.txt      # Just what the tests need
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
    pip install -r requirements.txt      # everything, including the web UIs
    pip install -r requirements-dev.txt  # just the engines and tests
    ```

---

## ♟️ Classic Agent (Knightmare)

An intelligent chess AI implementing minimax with alpha-beta pruning.

### Key Features
*   **Strength**: Beat random bots 20/20 games.
*   **Search**: Minimax with Alpha-Beta pruning, Iterative Deepening.
*   **Optimizations**: Killer Moves, History Heuristic, Quiescence Search, Transposition Table.
*   **Evaluation**: Material, pawn advancement, piece centralization, bishop pair, mobility.

### How the search works

| Piece | Where | Notes |
| :--- | :--- | :--- |
| Iterative deepening | `get_move` | Searches depth 1 upward, stopping when the time budget runs low. The deepest completed iteration wins. |
| Alpha-beta minimax | `minimax` | Absolute scores: positive favours White whichever side is to move. |
| Quiescence search | `quiesce` | Past the horizon, keeps resolving captures and promotions so the engine is not fooled by a half-finished trade. |
| Transposition table | `store_tt` | Keyed on position and depth. Entries record whether the score is exact or only a bound, and are reused only when they still settle the current window. Mate scores are never cached because they are relative to the ply they were found at. |
| Move ordering | `order_moves` | MVV-LVA captures, promotions, checks, killer moves, history heuristic, then central squares. |
| Mate distance | `evaluate` | Mate scores shrink with depth, so a mate in 1 outranks a mate in 4. |

Draw conditions that require a claim (threefold repetition, the fifty-move
rule) are scored as draws during the search, so a winning engine will not
shuffle into one.

### Time control

`go` understands `movetime`, `depth`, `infinite`, and the usual
`wtime`/`btime`/`winc`/`binc`/`movestogo` clock fields. With only a clock,
the engine spends roughly one thirtieth of the time remaining plus most of
the increment, and never more than 40% of what is left.

### Usage

**Web Interface (vs Random)**
```bash
cd classic_agent
python simple_web_chess.py                  # http://127.0.0.1:5001
python simple_web_chess.py --port 8080      # pick another port
```

**Play Against Stockfish**
```bash
cd classic_agent
python knightmare_vs_stockfish.py           # http://127.0.0.1:5002
# Set STOCKFISH_PATH if the binary is somewhere unusual
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

Only `chess` is needed for the test suites:
```bash
pip install -r requirements-dev.txt

cd classic_agent
python -m unittest test_evaluation   # evaluation, search and UCI parsing
python test_bots.py                  # UCI protocol smoke test
python diagnose_knight.py            # per-position search diagnostics

cd ../llm_agent
python -m unittest test_knightmare   # KnightmareFast search tests
```
These also run on every push via [GitHub Actions](.github/workflows/tests.yml).

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
python knightmare_llm.py                     # llama3.2
python knightmare_llm_mistral.py             # mistral, with recovery strategies
```

The mistral bot reads two environment variables:

| Variable | Purpose |
| :--- | :--- |
| `KNIGHTMARE_MODEL` | Ollama model to prompt (default `mistral`) |
| `KNIGHTMARE_LOG_DIR` | Where to write the `llm_log_recovery_*.jsonl` interaction log |

It tries four prompting strategies in order — standard, error feedback,
numbered list, simplified — falling back to a random legal move if all of
them fail, and stops early once the `movetime` budget is spent.

`knightmare.py` is a plain minimax engine (no LLM) used as a strong
baseline opponent in the tournament.

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