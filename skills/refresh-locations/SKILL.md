---
name: refresh-locations
description: 對 propositions JSONL 跑 windowed locator,把每個 prop 的 location 行範圍重新對齊到當前 main.tex 的實際位置。在 main.tex 大改動或行 shift 後 R13 location-drift WARN 飆高時使用。
user_invocable: true
---

# refresh-locations

修復 `prop.location` 行號漂移。

## When to use

- `main.tex` 加減過行(refactor / add new section / restructure)後,validator R13 報「N 個 prop 的 text 不在 declared location 範圍」
- 從一個 stable manuscript snapshot 跨度大改稿後,jsonl 的 `location` 已 stale
- 看到 `[WARN] R13 location-anchoring — N prop(s) with text outside declared location range` 且 N > 5

**不該用的場合**:

- `prop.text` 改了(那是 manuscript-jsonl-sync 違反,不是 location drift)
- 想對 jsonl 做 wholesale re-extraction(用 `extract` 或重跑 EXTRACTION-PROMPT.md flow)
- R1 prop-subset-check FAIL(R1 fail 表示 text 不在 main.tex 任何位置,refresh 救不了)

## Procedure

### Step 1: Resolve paths

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/propositions}"
REFRESH="$PLUGIN_ROOT/scripts/refresh-prop-locations.py"

JSONL="${1:-manuscript/propositions/main.jsonl}"
TEX="${2:-manuscript/main.tex}"
[ -f "$JSONL" ] || abort "JSONL not found at $JSONL"
[ -f "$TEX" ] || abort "TeX not found at $TEX"
```

### Step 2: Dry-run first (mandatory)

**絕對不要直接寫入** — 先跑 `--dry-run` 看會改什麼:

```bash
python3 "$REFRESH" --jsonl "$JSONL" --tex "$TEX" --dry-run
```

Output 會列出每個會被 update 的 prop:

```
✓ <prop-id-prefix>: main.tex:L<old-start>-L<old-end> → main.tex:L<new-start>-L<new-end>
...
total props: N
updated: M  (這是 dry-run 會改的數量)
R1 match failed: K  (這些 prop 的 text 連 main.tex whole-file 都不在 — refresh 救不了)
anchor failed: J  (R1 PASS 但 windowed locator 找不到 anchor — markup-heavy / source span > MAX_SPAN)
```

### Step 3: User confirmation (gate)

Show dry-run output, then **AskUserQuestion** before writing:

> "Refresh 將 update M 個 prop 的 location field。K 個 R1-fail(救不了)+ J 個 anchor-fail(留原值)。確認套用嗎?"
>
> - **apply** — 寫入 jsonl
> - **abort** — 取消,jsonl 不動

只有 user 明確 confirm 才往下走。

### Step 4: Apply (idempotent)

```bash
python3 "$REFRESH" --jsonl "$JSONL" --tex "$TEX"
```

實際寫入。Idempotent — 跑兩次第二次就 0 updated。

### Step 5: Re-validate

```bash
/propositions:validate "$JSONL" "$TEX"
```

確認 R13 從 N WARN 降到接近 0(剩下的是 source-span-exceeds-MAX_SPAN 的 inherent un-anchorable,需要拆 prop 或改 long-range 用 range-form `Lx-Ly` location)。

## Tooling note

- Locator 是 **windowed**(per validator R13 `_find_start_anchor`)— 在 MAX_SPAN 範圍內找 unique anchor
- 有 **degeneracy guard**:若 prop 的 normalized text 在 scan range 內出現太多次(span > MAX_SPAN),refuse to anchor 回傳 `anchor_failed` 而非亂猜
- 不會 silently mis-write `location` — 任何不確定都是 loud failure

## Exit codes

- 0 — 全部 refresh 完成,JSONL 已寫入
- 1 — 至少 1 個 prop 的 text 連 main.tex 都找不到(R1 fail)— jsonl 留原值,user 需先處理 R1
- 2 — usage / IO error

## Related

- `/propositions:validate` — 跑 R1-R13 confirm refresh 後狀態
- `rules/manuscript-jsonl-sync.md` — 改 main.tex 該同步 jsonl 的 PR-time prevention
- Background:`docs/SCHEMA.md` § location field 規範
