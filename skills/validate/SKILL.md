---
name: validate
description: 跑 propositions R1-R13 mechanical validator,確認 main.jsonl ↔ main.tex 之間的 bijection 沒漂移、cite chain 不形成 cycle、UUID 唯一、claim_type/evidence_class 合 enum、location 對齊。
user_invocable: true
---

# validate

對一個 propositions JSONL 跑完整 R1-R13 validator。

## When to use

- 改完 `main.tex` 後快速 sanity check
- 在 IDD lifecycle 的 verify phase 想確認 prop-iso 沒被破壞
- CI gate 之外想本地先 catch 問題
- 評估某個 candidate prop 變更是否合 schema

## Inputs

必填:

- `<jsonl-path>` — propositions JSONL 路徑(e.g. `manuscript/propositions/main.jsonl`)
- `<tex-path>` — manuscript LaTeX 來源(e.g. `manuscript/main.tex`)

選填(若 schema_version ≥ 1.2):

- `<meta-path>` — `_meta.json` 路徑,提供 schema_version + extraction provenance

## Procedure

### Step 1: Resolve plugin script path

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/propositions}"
VALIDATOR="$PLUGIN_ROOT/scripts/validate-propositions.py"
[ -f "$VALIDATOR" ] || { echo "validator not found at $VALIDATOR"; exit 2; }
```

### Step 2: Resolve user's manuscript paths

若 args 沒給,從當前 working tree 推導:

```bash
# Default: working tree 內找 manuscript/propositions/main.jsonl + manuscript/main.tex
JSONL="${1:-manuscript/propositions/main.jsonl}"
TEX="${2:-manuscript/main.tex}"
META="${3:-manuscript/propositions/_meta.json}"

# If user's working tree has different layout, ask
[ -f "$JSONL" ] || abort "JSONL not found at $JSONL — pass explicit path as arg 1"
[ -f "$TEX" ] || abort "TeX not found at $TEX — pass explicit path as arg 2"
```

### Step 3: Run validator

```bash
if [ -f "$META" ]; then
  python3 "$VALIDATOR" --jsonl "$JSONL" --meta "$META" --tex "$TEX"
else
  python3 "$VALIDATOR" --jsonl "$JSONL" --tex "$TEX"
fi
EXIT=$?
```

### Step 4: Report

| Validator output | Action |
|------------------|--------|
| `✓ ALL VALIDATION CHECKS PASSED` (exit 0) | report PASS, done |
| `[WARN]` lines only (exit 0) | report PASS with N warnings (informational) — list them |
| `[FAIL]` line (exit 1) | report FAIL, surface the failing rule + offending prop IDs |
| Crash / exit 2 | tool error — show stderr |

## What gets checked

| Rule | Invariant |
|------|-----------|
| R1 | `prop.text` ⊆ `main.tex` (normalize-aware substring) |
| R1.5 | every top-level section has ≥1 prop (informational coverage WARN) |
| R2 | every `cites` UUID resolves to existing prop |
| R3 | no cite cycles + orphan detection (structural leaves exempt) |
| R4 | mechanical-contradiction patterns (boundary axiom + Track A/B) |
| R7 | every `id` is canonical UUID v7 (schema v1.2+) |
| R8 | `id` unique across file |
| R9 | `containing_block` env boundaries match `location` line ranges |
| R10 | `connective`/`reference` claim_types have empty `asserts` |
| R11 | `evidence_class` in 5-element canonical enum (schema v1.2+) |
| R12 | `claim_type` in 12-element canonical enum (schema v1.2+) |
| R13 | single-line `location` anchors to text's actual starting line |

See `docs/SCHEMA.md` (in this plugin) for the full schema contract.

## Exit codes

- 0 — all PASS (or PASS with informational WARN)
- 1 — at least one rule FAILed
- 2 — usage / IO error (e.g., JSONL not found)

## Related

- `/propositions:refresh-locations` — fix `location` field drift after main.tex line shifts
- `/propositions:audit` — broader manuscript-consistency audit (R1-R4) including this validator
- `docs/SCHEMA.md` — canonical schema
- `rules/manuscript-jsonl-sync.md` — per-commit sync discipline
