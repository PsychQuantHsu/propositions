---
name: audit
description: 跑 manuscript-consistency audit suite (R1 symbols / R2 citations / R3 code-manuscript drift / R4 proposition-iso) — 在大改稿 / 投稿前掃整本 manuscript 的 source-of-truth drift。比 validate 範圍更廣;validate 只查 prop-iso 一條軸,audit 查 4 條軸。
user_invocable: true
---

# audit

跑完整 manuscript consistency audit (R1-R4)。

## When to use

依 `rules/manuscript-consistency-audit.md` 的 SOP §5:

- 大改稿後(整個 section rewrite、新增 theorem、reorganize)
- **投稿前最後一輪**檢查
- Manuscript 進新階段(initial submission / major revision / camera-ready)前

不該用的場合:

- 每個 PR 都跑(太重,~30-60 秒)— 那是 pre-commit hook + CI gate 的範圍
- Minor typo / 單詞替換後 — 不必

## What gets audited

| Rule | Coverage |
|------|----------|
| **R1 symbols** (`audit-symbols.py`) | 抓 `\texttt{}` working-file path leak、`note (<date>).tex` working-note reference |
| **R2 citations** (`audit-citations.py`) | 抓 `\cite{}` label leak(citing internal LaTeX label as if it were a published reference)+ bib orphan / dangling cite |
| **R3 code-manuscript drift** (`audit-code-manuscript.py`) | 比對 `analysis/*.py` AST vs `manuscript/docs/*.md` 的 backtick code refs |
| **R4 proposition-iso** (`validate-propositions.py`) | R1-R13 prop ↔ tex bijection(此 plugin 的 `validate` skill 全部包含) |

## Procedure

### Step 1: Resolve manuscript root

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/propositions}"
RUNNER="$PLUGIN_ROOT/scripts/run-audit.sh"

# Audit 對 manuscript root 跑(不是單一檔案)— root 通常含 main.tex + propositions/
MANUSCRIPT_ROOT="${1:-manuscript/}"
[ -d "$MANUSCRIPT_ROOT" ] || abort "Manuscript root not found at $MANUSCRIPT_ROOT — pass explicit path as arg 1"
```

### Step 2: Working tree clean precheck (recommended)

依 SOP §8 Pre-flight,跑 audit 前確認沒 concurrent editing race:

```bash
cd "$(dirname "$MANUSCRIPT_ROOT")"
git status --short  # should be empty
git submodule status  # ensure manuscript pointer correct
```

若 working tree 髒,問 user 是否要先 commit / stash 再跑。

### Step 3: Run audit

```bash
bash "$RUNNER" "$MANUSCRIPT_ROOT"
```

`run-audit.sh` 會:

1. 跑 R1 + R2 + R3 + R4 四個 rule
2. 把結果寫到 `$MANUSCRIPT_ROOT/docs/audit/audit-YYYY-MM-DD.md`
3. Exit 0 if all clean, exit 1 if any rule fired definite/likely finding

### Step 4: Review findings

讀 `$MANUSCRIPT_ROOT/docs/audit/audit-YYYY-MM-DD.md`:

- **Definite / Likely** findings → 必修(或 conscious decision 不修並記錄理由)
- **Suspicious / FYI** → review,大部分可忽略

若有 definite finding,建議 file 成 `audit-finding` GitHub issue 走後續 IDD lifecycle(對應 caller repo 的 issue tracker)。

## Output structure

落地路徑(在 `MANUSCRIPT_ROOT` 內):

```
docs/audit/
├── .gitkeep         # 目錄持續 tracked
└── audit-YYYY-MM-DD.md  # 每次 run 的 report;gitignore pattern 通常會 ignore
```

`.gitignore` pattern 建議(per rules/manuscript-consistency-audit.md):

```
docs/audit/audit-20[2-9][0-9]-[0-1][0-9]-[0-3][0-9].md
```

## Exit codes

- 0 — all clean
- 1 — at least 1 definite/likely finding
- 2 — tool error (missing file, script crash)

## Related

- `/propositions:validate` — 只跑 R4 (prop-iso),不查 R1/R2/R3
- `rules/manuscript-consistency-audit.md` — 完整 SOP + 觸發時機 + 已知 patterns
- `rules/manuscript-jsonl-sync.md` — 防止 jsonl 漂移的 per-commit discipline(audit 的補強)
