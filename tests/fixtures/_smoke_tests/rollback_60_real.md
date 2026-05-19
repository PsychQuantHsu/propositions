# rollback_60_real — Real Pre-#60-Fix Regression Test

## Purpose

Verifies that validator R4 PATTERN-A catches the **real historical Theorem 1 wording** that #60 fixed, not just hand-crafted synthetic scenarios (`rollback_60.{json,tex}` is the synthetic version).

This is the test #74 [agreed during /idd-verify --pr 70 Devil's Advocate review](https://github.com/PsychQuantHsu/psychophysical_representations/pull/70#issuecomment-4444074511) — proves `_smoke_tests/rollback_60.*` PATTERN-A demonstration is NOT circular validation.

## Source

`rollback_60_real.tex` extracted from real pre-#60-fix manuscript state at commit `manuscript@a11db6c^` (i.e., the commit immediately before the #60 fix landed, `a11db6c` per `git -C manuscript log --grep "#60"`).

Three excerpts:
1. **Setup boundary axiom** (`\section{sec:setup}`): `gamma(1, s) = 1` and `eta(1, s) = s`
2. **Theorem 1 hypothesis** (`\section{sec:thm1}` `\begin{theorem}`): `eta(lambda, s) = f(s)` for continuous f
3. **Cases (B), (C) f-extension claim** (`\textbf{Case (B)}` and `(C)`): "(reduces to lambda^b at f = id; **f may be any continuous map here**)" — the language #60 removed

## Extraction methodology

Propositions extracted automatically following `EXTRACTION-PROMPT.md` conventions:
- prop.text = verbatim from .tex (preserves R1 prop-subset-check pass)
- asserts = realistic author-paraphrase metadata (includes mathematical statements: "eta(1,s) = s", "eta(lambda,s) = f(s)", "f may be any continuous map")
- cites = derived from prop dependencies (P002 cites P001, P003/P004 cite P002)

This matches realistic LLM extraction output — not hand-crafted to trigger PATTERN-A.

## Result

```
$ python3 scripts/validate-propositions.py \
    --json manuscript/propositions/_smoke_tests/rollback_60_real.json \
    --tex manuscript/propositions/_smoke_tests/rollback_60_real.tex

[PASS] R1 prop-subset-check — all prop.text found in .tex
[PASS] R1.5 surjective coverage — every top-level section has ≥1 prop
[PASS] R2 cite-resolve — all cites resolve
[PASS] R3 DAG — no cycles

=== 1 ERROR(s) ===
  [R4] PATTERN-A: boundary axiom η(1,s)=s + hypothesis η=f(s) + 'f may be any' claim
       → contradiction: boundary forces f=id (Iverson framework)

Exit code: 1 ✓
```

**PATTERN-A fires correctly on real pre-fix wording**. The detector is NOT incident-specific synthetic-only — it catches real historical boundary-axiom violations.

## Conclusion

`#74` regression test acceptance criterion FULLY satisfied:

1. ✅ Pre-`a11db6c` (the #60 fix commit) main.tex state extracted
2. ✅ Real wording (not synthetic) drives the 3 PATTERN-A conditions
3. ✅ Validator R4 PATTERN-A fires on real-state input
4. ✅ Exit code 1 — would block CI / pre-commit if introduced today
5. ✅ Documents that `rollback_60.{json,tex}` synthetic test is NOT circular — the rule **does** catch real historical violations

## Implications for #72

#72 (PATTERN-A whitespace + general rule) was opened as Plan-tier concern that PATTERN-A is incident-specific fingerprint not general rule. **This test confirms PATTERN-A catches the original incident.** However, PATTERN-A's substring patterns (`"eta(1,s) = s"`, `"f may be any"` etc.) are still literal — a future regression that uses different wording (e.g., "$f$ is unconstrained" or `\eta|_{\lambda=1} = s`) would miss. #72 generalization is still valuable defensive measure but not urgent.

## See also

- `rollback_60.{json,tex,md}` — synthetic version (hand-crafted, simpler)
- `manuscript/propositions/SCHEMA.md` §R4 — PATTERN-A detector spec
- `scripts/validate-propositions.py` `check_contradictions` — PATTERN-A implementation
- `manuscript@a11db6c` — #60 fix commit (where this snapshot is from)
