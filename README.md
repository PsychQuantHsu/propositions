# propositions

**Author-claim infrastructure for academic LaTeX manuscripts.**

Line-addressable propositions (JSONL) extracted from `main.tex` + R1-R13 mechanical validator + audit tooling + extraction discipline. Originally developed as the "Locke project" for `PsychQuantHsu/psychophysical_representations` and packaged as a reusable Claude Code plugin.

## What it does

Solves three problems that LaTeX-heavy academic manuscripts run into:

1. **"What did I claim in §4?"** — every declarative claim has a UUID + verbatim text + line range. Grep `prop.text` is faster than re-reading.
2. **"Does my proof actually use what it cites?"** — `cites` UUID chain + R3 DAG validation surface orphans and circular references.
3. **"Did I just silently break the manuscript by reformulating Theorem 3?"** — R1 substring containment + R13 line-anchoring fire LOUD when the propositions JSONL drifts from `main.tex`.

## Install

This repo is a **self-hosted single-plugin marketplace** — one `claude plugin marketplace add` adds both the marketplace and exposes the plugin for install.

```bash
# Add the marketplace from GitHub
claude plugin marketplace add <owner>/propositions

# Install the plugin
claude plugin install propositions@propositions
```

## Quick start

```bash
# Inside your manuscript repo (with manuscript/main.tex + manuscript/propositions/main.jsonl)

/propositions:validate              # R1-R13 mechanical gates
/propositions:refresh-locations     # fix line drift after main.tex restructure
/propositions:audit                 # full manuscript-consistency audit before submission
```

## Architecture

| Layer | Lives where | Purpose |
|-------|-------------|---------|
| **Discipline** | `rules/` (this plugin) | per-commit sync + audit-time SOP |
| **Tooling** | `scripts/` (this plugin) | validator + locator + audit suite |
| **Data** | `manuscript/propositions/main.jsonl` (your repo) | the actual propositions |

## Validator rules (R1-R13)

| Rule | What |
|------|------|
| R1 | every `prop.text` is a substring of `main.tex` (normalize-aware) |
| R1.5 | every `\section{}` has ≥1 prop (informational coverage) |
| R2 | every `cites` UUID resolves |
| R3 | no cite cycles + orphan detection |
| R4 | mechanical-contradiction patterns |
| R7 | UUID v7 ID format (schema v1.2+) |
| R8 | unique IDs |
| R9 | `containing_block` env line range consistency |
| R10 | `connective`/`reference` claim_types have empty `asserts` |
| R11 | `evidence_class` enum membership (schema v1.2+) |
| R12 | `claim_type` enum membership (schema v1.2+) |
| R13 | single-line `location` anchors to actual text start |

See `docs/SCHEMA.md` for the canonical schema contract.

## Project history

The infrastructure was built from 2026-05-12 onward through a marathon of 30+ issues in `PsychQuantHsu/psychophysical_representations` (#69 onward). The Locke / John Locke reference encodes the epistemological discipline behind the project: every author-level claim must be authoritatively addressable, not buried in LaTeX bytes.

See `docs/locke-project.md` in `PsychQuantHsu/psychophysical_representations` for the full origin narrative.

## Layout

```
propositions/
├── .claude-plugin/
│   ├── plugin.json          # Claude Code plugin manifest
│   └── marketplace.json     # single-plugin marketplace catalog
├── CLAUDE.md                # plugin-level instructions
├── README.md                # this file
├── scripts/                 # validator + audit tooling
│   ├── validate-propositions.py
│   ├── refresh-prop-locations.py
│   ├── audit-theorem-boundaries.py
│   ├── audit-{citations,symbols,code-manuscript}.py
│   ├── run-audit.sh
│   ├── migrate-{prop-id-to-uuid,json-to-jsonl}.py
│   └── _lib/latex_env_parser.py
├── tests/                   # pytest test suite (142+ tests)
├── skills/                  # user-invocable slash commands
│   ├── validate/SKILL.md
│   ├── refresh-locations/SKILL.md
│   └── audit/SKILL.md
├── rules/                   # discipline rules (ship with plugin)
│   ├── manuscript-jsonl-sync.md
│   └── manuscript-consistency-audit.md
└── docs/                    # contract docs (ship with plugin)
    ├── SCHEMA.md
    └── EXTRACTION-PROMPT.md
```

## Compatibility

- Python 3.10+
- pytest 7+
- LaTeX manuscript with `manuscript/main.tex` + `manuscript/propositions/main.jsonl` layout (paths configurable via skill args)
- Schema versions v1.0 / v1.1 / v1.2 / v1.3

## License

MIT
