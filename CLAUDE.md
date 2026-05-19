# propositions plugin — author-claim infrastructure for academic LaTeX manuscripts

> 「**確認你在說什麼**」— 把 `main.tex` 每一個 declarative claim 提煉成 author cognitive atom,存進 line-addressable JSONL,配 mechanical validator 確保 manuscript 與 jsonl 之間的雙向對應永遠 falsifiable。

## What this plugin provides

| Skill | What |
|-------|------|
| `/propositions:validate` | 跑 R1-R13 mechanical validator 確認 jsonl ↔ main.tex bijection |
| `/propositions:refresh-locations` | Windowed locator 修 `prop.location` 行號漂移 |
| `/propositions:audit` | 跑完整 manuscript-consistency audit (R1 symbols / R2 citations / R3 code-manuscript / R4 prop-iso) |

| Rule (shipped) | When applies |
|----------------|--------------|
| `rules/manuscript-jsonl-sync.md` | PR-time prevention: 改一邊 main.tex 該同步 jsonl |
| `rules/manuscript-consistency-audit.md` | Audit-time detection SOP + 觸發時機 |

| Doc (shipped) | What |
|---------------|------|
| `docs/SCHEMA.md` | Canonical schema contract for propositions JSONL |
| `docs/EXTRACTION-PROMPT.md` | LLM extraction discipline (餵給 Claude / GPT 抽 prop 用) |

## Architecture (three layers)

```
┌─ Layer 3: Discipline ─────────────────────────────────────┐
│  rules/manuscript-jsonl-sync.md       (per-commit)        │
│  rules/manuscript-consistency-audit.md (audit-time SOP)   │
└───────────────────────────────────────────────────────────┘
                      ↑ enforces
┌─ Layer 2: Validator + Tooling ────────────────────────────┐
│  scripts/validate-propositions.py   (R1-R13 gates)        │
│  scripts/refresh-prop-locations.py  (location refresh)    │
│  scripts/audit-theorem-boundaries.py (LaTeX env CI gate)  │
│  scripts/audit-{citations,symbols,code-manuscript}.py     │
│  scripts/run-audit.sh               (orchestrator)        │
│  scripts/migrate-*.py               (historical tools)    │
│  scripts/_lib/latex_env_parser.py   (shared parser)       │
└───────────────────────────────────────────────────────────┘
                      ↑ verifies
┌─ Layer 1: Data Artifacts (user's manuscript repo) ────────┐
│  manuscript/propositions/main.jsonl     (per-paper)       │
│  manuscript/propositions/_meta.json     (per-paper)       │
│  manuscript/main.tex                    (per-paper)       │
└───────────────────────────────────────────────────────────┘
```

Layer 1 lives in the **user's manuscript repo** (data, paper-specific).
Layers 2 + 3 are this plugin (reusable across any prop-iso manuscript).

## Quick start (in a user's manuscript repo)

```bash
# 1. Validate the bijection
/propositions:validate

# 2. After a main.tex restructure, refresh location fields
/propositions:refresh-locations

# 3. Before submission, run the full audit suite
/propositions:audit
```

All three commands auto-detect `manuscript/propositions/main.jsonl` + `manuscript/main.tex` from the working tree. Pass explicit paths if your layout differs.

## Validator rules (R1-R13)

See `docs/SCHEMA.md` for the full contract. Summary:

| Rule | Invariant | Failure mode |
|------|-----------|--------------|
| R1 | `prop.text` ⊆ `main.tex` (normalize-aware) | Silent drift between jsonl and tex |
| R1.5 | each `\section{}` has ≥1 prop | Coverage gap (informational) |
| R2 | every `cites` UUID resolves | Dangling reference |
| R3 | no cite cycles + orphan detection | Circular reasoning / isolated claim |
| R4 | mechanical-contradiction patterns | Two props contradict |
| R7 | UUID v7 ID format (schema v1.2+) | Stable identity broken |
| R8 | unique IDs | Duplicate prop |
| R9 | `containing_block` ⊆ env line range | Theorem boundary misjudged |
| R10 | `connective`/`reference` empty `asserts` | LLM claim_type mistag |
| R11 | `evidence_class` ∈ canonical 5-enum (v1.2+) | LLM hallucinated value |
| R12 | `claim_type` ∈ canonical 12-enum (v1.2+) | LLM hallucinated value |
| R13 | single-line `location` anchors to actual start | location field drift |

## Originally developed as

The "Locke project" for `PsychQuantHsu/psychophysical_representations` — a manuscript on psychophysical representation theory. The project name references John Locke's epistemological "clarity of ideas" discipline (every declarative claim must be authoritatively addressable). Packaged here as a plugin so other LaTeX-heavy manuscript projects can adopt the same prop-iso infrastructure without copying scripts repo-by-repo.

The umbrella narrative doc (philosophy + lifecycle + concrete state of the source project) lives at `docs/locke-project.md` in `PsychQuantHsu/psychophysical_representations`, not in this plugin.

## Compatibility

- Python 3.10+ (uses 3.10+ type hints + `match` statements in some scripts)
- pytest 7+ for test suite
- LaTeX manuscript with `manuscript/main.tex` + `manuscript/propositions/main.jsonl` convention(可自訂 path via skill args)
- Schema versions: v1.0 / v1.1 / v1.2 / v1.3 — validator handles all four with backward-compat skip for v1.2-only rules (R7 / R11 / R12)

## Hard rules for contributors

- **不修 user 的 main.jsonl 不問**:任何會 write jsonl 的 skill (e.g., refresh-locations) 必須先 dry-run + AskUserQuestion 確認再寫
- **Loud failure over silent fix**:寧可 anchor_failed 不要亂猜 line number
- **Schema 升級走 spec 流程**:不要 ad-hoc 加 enum 值;先改 `docs/SCHEMA.md` 確定新 canonical set,再更 validator + tests
- **Test 覆蓋每條 rule**:R1-R13 各自有獨立 fixture;改 normalize_for_match 等 shared helper 必跑全 R-rule test suite

## Test suite

```bash
pytest tests/  # 期待 142+ passed
```

`tests/` 含 each rule 的 fixture + edge cases。Smoke tests live in the user's manuscript repo under `propositions/_smoke_tests/`(per-paper),不在 plugin。
