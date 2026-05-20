#!/usr/bin/env bash
# test_run_audit.sh — smoke test for scripts/run-audit.sh orchestrator.
#
# Verifies:
#   - run-audit.sh produces dated report at manuscript/docs/audit/audit-YYYY-MM-DD.md
#   - exit code reflects findings (1 if any, 0 if clean)
#   - error path: missing manuscript root → exit 2

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Set up fixture: manuscript with one R1 violation, no R2 or R3
mkdir -p "$TMP/manuscript/docs" "$TMP/analysis"
cat > "$TMP/manuscript/main.tex" <<'EOF'
The audit at \texttt{analysis/verify_eta_fs.py}.
\cite{Smith2020}
EOF
cat > "$TMP/manuscript/refs.bib" <<'EOF'
@article{Smith2020, title={X}}
EOF
cat > "$TMP/analysis/checker.py" <<'EOF'
def compute_score():
    pass
EOF
cat > "$TMP/manuscript/docs/method.md" <<'EOF'
We compute via `compute_score`.
EOF

# Run audit
EXIT_CODE=0
"$REPO_ROOT/scripts/run-audit.sh" "$TMP/manuscript" --code-root "$TMP/analysis" > /dev/null || EXIT_CODE=$?

# Test 1: exit code should be 1 (R1 finding exists)
if [[ "$EXIT_CODE" -ne 1 ]]; then
  echo "FAIL: expected exit 1 (R1 finding), got $EXIT_CODE" >&2
  exit 1
fi

# Test 2: report file should exist
REPORT="$TMP/manuscript/docs/audit/audit-$(date +%F).md"
if [[ ! -f "$REPORT" ]]; then
  echo "FAIL: report file not created at $REPORT" >&2
  exit 1
fi

# Test 3: report should contain all three pass headers
if ! grep -q "Audit (R1 symbols)" "$REPORT"; then
  echo "FAIL: R1 section missing from report" >&2
  exit 1
fi
if ! grep -q "Audit (R2 + R2-bis citations)" "$REPORT"; then
  echo "FAIL: R2 section missing from report" >&2
  exit 1
fi
if ! grep -q "Audit (R3 code-manuscript drift)" "$REPORT"; then
  echo "FAIL: R3 section missing from report" >&2
  exit 1
fi

# Test 4: missing manuscript root → exit 2
EXIT_CODE=0
"$REPO_ROOT/scripts/run-audit.sh" "$TMP/nonexistent" 2>/dev/null || EXIT_CODE=$?
if [[ "$EXIT_CODE" -ne 2 ]]; then
  echo "FAIL: expected exit 2 (missing root), got $EXIT_CODE" >&2
  exit 1
fi

echo "PASS: all run-audit.sh smoke tests passed"
