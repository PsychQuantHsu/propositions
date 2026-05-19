# Smoke test scenarios (#69 Locke project)

Synthetic proposition sets simulating pre-fix manuscript states. Used to
prove that the validator can mechanically detect the bugs we already fixed
(#59 / #60 / #61 / #62 / #63 / #68). If the validator catches them here, we
know it will catch the next regression in production.

## Usage

```bash
# Run validator against a smoke-test scenario (NOT against current .tex)
python3 scripts/validate-propositions.py \
  --jsonl manuscript/propositions/_smoke_tests/rollback_60.jsonl \
  --meta manuscript/propositions/_smoke_tests/rollback_60_meta.json \
  --tex manuscript/propositions/_smoke_tests/rollback_60.tex
```

Expected: each scenario should produce an R4-PATTERN-A or similar error,
demonstrating the validator catches the bug.

## Scenarios

| File pair | Simulates | Expected catch |
|-----------|-----------|----------------|
| `rollback_60.jsonl` + `rollback_60_meta.json` | Pre-#60-fix synthetic: Theorem 1 with `η=f(s)` + "f may be any continuous" extension | R4 PATTERN-A (boundary axiom + non-id-f hypothesis + extension claim) |
| `rollback_60_real.jsonl` + `rollback_60_real_meta.json` | Pre-#60-fix real wording (verbatim from `manuscript@a11db6c^`, #74) | Same — proves PATTERN-A catches authentic historical state |

## Why these are separate files

The main `propositions/main.jsonl` represents the CURRENT (post-fix) state.
Smoke-test scenarios live separately so:

- Running validator on `main.jsonl` against current `main.tex` should PASS
  (modulo Phase 1 known R1.5 surjective coverage warnings + R3 orphan warnings)
- Running validator on `_smoke_tests/rollback_60.jsonl` should FAIL
  (PATTERN-A catches the would-be regression)

## See also

- SCHEMA.md — proposition schema
- ../EXTRACTION-PROMPT.md — extraction prompt
- ../../../scripts/validate-propositions.py — validator
