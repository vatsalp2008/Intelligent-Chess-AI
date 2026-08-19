#!/usr/bin/env bash
#
# Run every test suite in the project.
#
# The suites live in two directories and have different dependencies, so
# running them by hand means remembering ten commands and which ones need
# Flask or Stockfish. This runs what it can and says what it skipped.
#
#   ./run_tests.sh            # everything available
#   ./run_tests.sh --quick    # skip the slow end-to-end checks
#
set -u

PYTHON="${PYTHON:-python3}"
QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

passed=0
failed=0
skipped=0
failures=""

have_module() {
    "$PYTHON" -c "import $1" >/dev/null 2>&1
}

run() {
    local name="$1" dir="$2"
    shift 2
    printf '%-34s ' "$name"
    if ( cd "$dir" && "$@" ) >/tmp/run_tests_out 2>&1; then
        echo "ok"
        passed=$((passed + 1))
    else
        echo "FAILED"
        failed=$((failed + 1))
        failures="${failures}\n  $name\n$(tail -15 /tmp/run_tests_out | sed 's/^/    /')"
    fi
}

skip() {
    printf '%-34s %s\n' "$1" "skipped ($2)"
    skipped=$((skipped + 1))
}

echo "Running test suites"
echo "===================================================="

# Engine and search: only need python-chess
run "classic: evaluation"    classic_agent "$PYTHON" -m unittest test_evaluation
run "classic: search safety"  classic_agent "$PYTHON" -m unittest test_search_safety
run "classic: engine loader"  classic_agent "$PYTHON" -m unittest test_bot_loader
run "classic: tournament"     classic_agent "$PYTHON" -m unittest test_tournament
run "classic: tuner"          classic_agent "$PYTHON" -m unittest test_tune_eval
run "classic: selfplay harness" classic_agent "$PYTHON" -m unittest test_selfplay
run "classic: benchmark harness" classic_agent "$PYTHON" -m unittest test_benchmark
run "classic: diagnostics"     classic_agent "$PYTHON" -m unittest test_diagnose
run "classic: tactics"        classic_agent "$PYTHON" tactics.py

run "llm: baseline search"    llm_agent "$PYTHON" -m unittest test_knightmare
run "llm: prompt parsing"     llm_agent "$PYTHON" -m unittest test_llm_parsing
run "llm: recovery escalation" llm_agent "$PYTHON" -m unittest test_llm_recovery
run "llm: retry loop"         llm_agent "$PYTHON" -m unittest test_llm_retry
run "llm: tournament scoring" llm_agent "$PYTHON" -m unittest test_tournament_scoring
run "llm: shared tables"      llm_agent "$PYTHON" -m unittest test_shared_tables
run "llm: tactics"            llm_agent "$PYTHON" tactics.py

# The generator tests need networkx, which the minimal install omits
if have_module networkx; then
    run "llm: game tree generator" llm_agent "$PYTHON" -m unittest test_generator
else
    skip "llm: game tree generator" "networkx not installed"
fi

# The visualiser tests need matplotlib, which the minimal install omits
if have_module matplotlib; then
    run "classic: tree visualiser" classic_agent "$PYTHON" -m unittest test_tree_viz
else
    skip "classic: tree visualiser" "matplotlib not installed"
fi

# The web tests drive Flask, which the minimal install does not include
if have_module flask; then
    run "classic: web concurrency" classic_agent "$PYTHON" -m unittest test_web_concurrency
else
    skip "classic: web concurrency" "flask not installed"
fi

# Slower end-to-end checks that start real subprocesses
if [ "$QUICK" -eq 0 ]; then
    run "classic: UCI protocol"  classic_agent "$PYTHON" test_bots.py
else
    skip "classic: UCI protocol" "--quick"
fi

echo "===================================================="
"$PYTHON" -c "
import subprocess
files = subprocess.run(['git','ls-files','*.py'], capture_output=True, text=True).stdout.split()
import py_compile
for f in files:
    py_compile.compile(f, doraise=True)
print('every tracked module compiles')
" && passed=$((passed + 1)) || failed=$((failed + 1))

echo "===================================================="
echo "$passed passed, $failed failed, $skipped skipped"
if [ "$failed" -gt 0 ]; then
    printf 'Failures:%b\n' "$failures"
    exit 1
fi
