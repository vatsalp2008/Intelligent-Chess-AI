# Intelligent Chess AI Platform ♟️🤖

**A unified chess platform featuring both a Classical Minimax Engine and an Experimental LLM-based Agent.**

This project merges two distinct approaches to computer chess:
1.  **Classic Agent (Knightmare)**: A high-performance Minimax engine with Alpha-Beta pruning (100% win rate vs random).
2.  **LLM Agent (ChessGPT)**: An experimental bot that uses Large Language Models (via Ollama) to decide moves.

## 📂 Project Structure

```
Intelligent-Chess-AI/
├── classic_agent/              # Knightmare Engine & Web UI
│   ├── knightmare_bot.py       # Core Minimax Logic
│   ├── bot_loader.py           # Shared Engine Loading for the Web UIs
│   ├── simple_web_chess.py     # Web Interface (vs Random)
│   ├── knightmare_vs_stockfish.py  # Web Interface (vs Stockfish)
│   ├── simple_tournament.py    # Tournament Runner (PGN output)
│   ├── standalone_tree_viz.py  # Minimax Tree Figures
│   ├── diagnose_knight.py      # Per-position Search Diagnostics
│   ├── selfplay.py             # Measure a Change Against a Saved Engine
│   ├── benchmark_stockfish.py  # External Strength Baseline
│   ├── tune_eval.py            # Sweep Evaluation Weights
│   ├── tactics.py              # Positions With a Known Best Move
│   ├── test_bots.py            # UCI Protocol Smoke Test
│   └── test_*.py               # Unit Suites
├── llm_agent/                  # LLM-based Bots (Ollama)
│   ├── knightmare_llm.py       # LLM Bot (llama3.2)
│   ├── knightmare_llm_mistral.py   # LLM Bot With Recovery Strategies
│   ├── knightmare.py           # Minimax Baseline Opponent
│   ├── random_chess_bot.py     # Random Baseline
│   ├── mate_in_one.py          # Mate-in-one Baseline
│   ├── generator.py            # Game Tree Generator
│   ├── tournament.py           # Multi-bot Tournament
│   ├── selfplay.py             # Measure Baseline Engine Changes
│   ├── benchmark_stockfish.py  # External Strength Baseline
│   ├── tactics.py              # Positions With a Known Best Move
│   ├── REPORT.md               # Coursework Writeup
│   └── test_*.py               # Unit Suites
├── run_tests.sh                # Run Every Suite
├── requirements.txt            # Unified Dependencies
├── requirements-dev.txt        # Just What the Tests Need
└── README.md                   # Documentation
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
*   **Optimizations**: Killer Moves, History Heuristic, Quiescence Search, Transposition Table, Static Exchange Evaluation, Check Extensions.
*   **Evaluation**: Material, piece-square tables, pawn structure, passed pawns, king shelter, rook files, bishop pair, mobility.

### How the search works

| Piece | Where | Notes |
| :--- | :--- | :--- |
| Opening book | `book_move` | A short book of mainlines, keyed by position so it works through transpositions and from a FEN. Consulted after the mate check, so it can never talk the engine out of a forced win. |
| Iterative deepening | `get_move` | Searches depth 1 upward, stopping when the time budget runs low. The deepest completed iteration wins. |
| Alpha-beta minimax | `minimax` | Absolute scores: positive favours White whichever side is to move. |
| Quiescence search | `quiesce` | Past the horizon, keeps resolving captures and promotions so the engine is not fooled by a half-finished trade. Captures that lose material are skipped outright. |
| Static exchange evaluation | `static_exchange_eval` | Plays an exchange out with the cheapest attacker each time, so the engine knows QxP is bad when the pawn is defended without searching it. Drives capture ordering and quiescence pruning. |
| Check extensions | `minimax` | Being in check is forced, so the search goes one ply further rather than stopping mid-sequence. |
| Transposition table | `store_tt` | Keyed on position and depth. Entries record whether the score is exact or only a bound, and are reused only when they still settle the current window. Mate scores are never cached because they are relative to the ply they were found at. |
| Move ordering | `order_moves` | The best move from a previous search of the position first, then captures ranked by exchange value, promotions, checks, killer moves, history heuristic, and central squares. Losing captures sort below every quiet move. |
| Null move pruning | `minimax` | Past depth 4, checks whether giving the opponent a free move still wins; if so the branch is cut. Skipped in check and when the side to move has only pawns, where passing would be misleading. |
| Time management | `get_move` | Predicts the next iteration's cost from the previous one and stops rather than starting a depth it cannot finish. |
| Principal variation | `extract_pv` | The expected line is read back out of the table and reported on each `info` line. |
| Mate distance | `evaluate` | Mate scores shrink with depth, so a mate in 1 outranks a mate in 4. |

Draw conditions that require a claim (threefold repetition, the fifty-move
rule) are scored as draws during the search, so a winning engine will not
shuffle into one.

### Measuring a change

Search and evaluation changes are easy to get wrong in ways that look
plausible, so `selfplay.py` plays the current engine against a saved copy
of itself at a fixed depth, alternating colours across a dozen openings:

```bash
cd classic_agent
git show HEAD~1:classic_agent/knightmare_bot.py > /tmp/old_bot.py
python selfplay.py /tmp/old_bot.py --depth 3
```

Fixed depth rather than fixed time keeps the result reproducible. As a
sanity check, an engine played against an identical copy scores 50%.

Use `--seconds` instead when the change was about speed. A faster search
cannot change what a fixed-depth search returns, so ordering and pruning
work only shows up under a clock.

Self play cannot say how strong the engine actually is, because both sides
share the same blind spots. For that, `benchmark_stockfish.py` plays an
independent opponent held to a small fixed depth:

```bash
cd classic_agent
python benchmark_stockfish.py --skill-depth 2
python benchmark_stockfish.py --ladder
```

Knightmare at depth 3 scores around 46% against Stockfish limited to depth
2. Six games per rung turned out to be far too noisy to compare rungs, so
the default is the full twelve game set.

`tactics.py` complements both: each position has one clearly correct move,
so a failure names the specific weakness rather than just a lower score.

```bash
python tactics.py --verbose
```

### Tuning evaluation weights

`tune_eval.py` sweeps a weight and scores each value by how many
centipawns Stockfish thinks the resulting move gives away. That is fast
enough to try a range, which a self-play match per value is not:

```bash
cd classic_agent
python tune_eval.py --list
python tune_eval.py --weight BISHOP_PAIR_BONUS --values 0 30 50 80
python tune_eval.py --all --quick
```

It is a proxy, so treat a hit as a candidate and confirm it with
`selfplay.py`. That matters in practice:

*   `BISHOP_PAIR_BONUS` looked 9% better raised, and self-play agreed. The
    tuner's own pick of 200 scored 56%, but 50 scored 60%, so the proxy had
    the direction right and the magnitude wrong. 50 is what shipped.
*   `ISOLATED_PAWN_PENALTY` at 150 looked 2% better and then scored **27%**
    in a self-play match, a severe regression.

That second case is why the tuner now ignores gains below 5%. On freshly
sampled positions the tuner's 200 is only 4% better than the shipped 50, so
the threshold now rejects it as well.

`--sample N` generates positions from played games instead of using the
fixed set, which gives a steadier signal at the cost of a slower sweep.

### Things tried that did not survive measurement

Keeping these on record saves re-deriving them:

| Change | Result |
| :--- | :--- |
| Tapered evaluation (phase-blended king tables) | 40% — diluted the king's shelter while queens were on |
| Aspiration windows | 0% node saving once a transposition table bug was fixed; the apparent 41% gain had come from that bug |
| Late move reductions | 51-71% fewer nodes, but 40% at depth 4 (45% with a conservative setting). Buys speed by accepting less accuracy, and the speed did not pay it back at these depths |
| `ISOLATED_PAWN_PENALTY` 150 | Looked 2% better to the tuner, scored 27% in a match |

Two parameters were checked and left alone: `QUIESCENCE_DEPTH` 4 beat both 2
and 6, and `NULL_MOVE_REDUCTION` 2 beat both 1 and 3.

### Time control

`go` understands `movetime`, `depth`, `infinite`, and the usual
`wtime`/`btime`/`winc`/`binc`/`movestogo` clock fields. With only a clock,
the engine spends roughly one thirtieth of the time remaining plus most of
the increment, and never more than 40% of what is left.

Iterative deepening decides whether to start the next depth by predicting
its cost from how long the last one took. That prediction is a guess, and
when it is wrong the search used to run to the end of the iteration
regardless: the baseline engine was measured taking 28 seconds for a one
second budget. The search now also carries a hard deadline, checked every
few thousand nodes, and abandons the iteration when it passes.

Abandoning an iteration throws work away, so a root move that has already
been searched to the new depth is kept rather than discarded — it is a
better answer than the whole of the previous, shallower depth. Measured
overshoot after the change, over a range of budgets and positions:

| Engine   | Worst overshoot before | After |
| -------- | ---------------------- | ----- |
| Classic  | unbounded (1.3x seen)  | 1.4x  |
| Baseline | unbounded (28x seen)   | 1.2x  |

What remains is the fixed cost of the mate scan that runs before any
searching, plus up to one clock-check interval.

Strength is unchanged as far as these sample sizes can tell: 54% at a
fixed depth over 24 games, where the deadline never fires at all, and 38%
at 0.3s a move and 54% at 0.5s a move over 24 and 12 games. Those last two
straddle even, which is what a sample this size looks like when there is
nothing to find.

### Usage

**Web Interface (vs Random)**
```bash
cd classic_agent
python simple_web_chess.py                  # http://127.0.0.1:5001
python simple_web_chess.py --port 8080      # pick another port
```

Both interfaces show what the engine thought about its last move: the depth
it reached, the score in pawns, and the line it expected, in algebraic
notation. A book move reports no search, because none happened.

Auto play chains each move off the previous one rather than firing on a
timer. A fixed interval overlapped requests once a move took longer than the
interval, and because the board is a shared global that produced impossible
games: five consecutive Black moves in one recorded case. The board is now
also guarded by a lock on the server, since the development server is
threaded.

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

Everything at once:
```bash
./run_tests.sh          # every suite
./run_tests.sh --quick  # skip the slower end-to-end checks
```

That is also what CI runs, so there is one list of suites rather than two.
Suites needing a package that is not installed are reported as skipped
rather than failing.

There are 23 suites. Most need only `chess`; the ones covering the web
interfaces need Flask, the visualiser needs matplotlib and the game tree
generator needs networkx. Missing an optional package skips that suite
rather than failing the run.

What is covered, beyond the engines themselves:

| Area | Why it is tested |
| :--- | :--- |
| Measurement harnesses | Every strength claim comes out of `selfplay.py` and `benchmark_stockfish.py`. A colour attribution bug there would quietly invalidate all of them, so the scoring is tested directly, including that identical engines score 50%. |
| Engine process handling | The tournament runner and the diagnostic both drive engines as subprocesses. The interesting cases are engines that die, engines that go silent, and shutdown running twice. |
| Web concurrency | Overlapping requests used to produce impossible games. The test fires six concurrent moves and checks the result still replays as legal chess. |
| LLM control flow | The retry loop and the four-strategy escalation are driven with a stubbed model, so no Ollama server is needed. |
| Duplicated data | The evaluation tables exist in both engines; a test fails if the copies drift. |

Or individually:
```bash
pip install -r requirements-dev.txt

cd classic_agent
python -m unittest test_evaluation     # evaluation, search and UCI parsing
python -m unittest test_search_safety  # legal moves and time budget
python -m unittest test_tournament     # tournament runner and scoring
python -m unittest test_bot_loader     # shared engine loading fallbacks
python tactics.py                      # positions with a known best move
python test_bots.py                    # UCI protocol smoke test
python diagnose_knight.py              # per-position search diagnostics

cd ../llm_agent
python -m unittest test_knightmare          # baseline search tests
python -m unittest test_llm_parsing         # prompt parsing (no Ollama needed)
python -m unittest test_tournament_scoring  # tournament scoring (no chester needed)
python -m unittest test_shared_tables       # duplicated tables still match
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

**Run the Tournament**

A round robin between the LLM bot and the three classical baselines. Needs
`chester` (in `requirements.txt`) and Ollama running for the LLM bot:

```bash
cd llm_agent
python tournament.py                  # 4 games per pairing
python tournament.py --games 8 --quiet
```

**Run LLM Bot**
*Ensure Ollama is running (`ollama serve`).*

```bash
cd llm_agent
python knightmare_llm.py                     # llama3.2
python knightmare_llm_mistral.py             # mistral, with recovery strategies
```

Both LLM bots read the same environment variables:

| Variable | Purpose |
| :--- | :--- |
| `KNIGHTMARE_MODEL` | Ollama model to prompt (defaults to `llama3.2` or `mistral` depending on the script) |
| `KNIGHTMARE_LOG_DIR` | Where to write the `llm_log_recovery_*.jsonl` interaction log |

`knightmare_llm_mistral.py` tries four prompting strategies in order —
standard, error feedback, numbered list, simplified — falling back to a
random legal move if all of them fail. Both bots stop asking once the
`movetime` budget is spent, and both parse replies by scanning for the
first legal UCI move in the text.

`knightmare.py` is a plain minimax engine (no LLM) used as a strong
baseline opponent in the tournament. It has the same measurement tools as
the classic agent:

```bash
cd llm_agent
git show HEAD~1:llm_agent/knightmare.py > /tmp/old.py
python selfplay.py /tmp/old.py --depth 3   # did a change help?
python benchmark_stockfish.py              # how strong is it really?
```

It scores about 17% against Stockfish limited to depth 2, against roughly
46% for the classic agent engine, so it is clearly the weaker of the two
despite sharing the same evaluation tables.

Those tables are duplicated in both engines rather than shared, because
the two are standalone scripts with no package between them to import
from. `test_shared_tables.py` fails if the copies drift apart.

Sharing the tables does not mean sharing the tuning. Several search
features that clearly helped the classic agent measured as neutral or
worse when ported to this engine, and were not kept:

| Ported feature | classic_agent | baseline engine |
| :--- | :--- | :--- |
| Piece-square tables | 75% | 56% (kept) |
| Searching every move at shallow depth | 65% | 62% (kept) |
| Stored-move ordering | 26% fewer nodes | 2% fewer, one position worse |
| Static exchange evaluation | 32-38% fewer nodes | 19% *slower* overall |
| Check extensions | 67% | 25% (clear regression) |
| Bishop pair bonus at 50 | 60% | 44% (regression) |

Two of six ports helped. The two engines differ enough in evaluation and
move ordering that a feature has to be measured on each one separately;
"it helped the other engine" has turned out to be a poor predictor.

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