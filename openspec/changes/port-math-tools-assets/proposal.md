## Why

propositions plugin 已完成 math-tools roadmap 7/9 條（scripts、tests、validator R1→R13），但 math-tools plugin 還有三件獨有資產沒被吸收：proofread skill scaffolding、code-and-manuscript-sync discipline rule、mcs references。本次先把這些獨有資產 port 進 propositions，讓 propositions plugin 的 surface area 真正涵蓋 math-tools 的內容，後續才能進入兩個 sister change（proofread 完整實作 / math-tools deprecation）。

## What Changes

- **新增 skill scaffolding**：把 proofread skill 的 SKILL.md（來源 math-tools plugin）port 進 propositions 的 skills/proofread/，維持 v0.1.0 SCAFFOLDING 狀態（execution body 不在本次 scope，留給 sister change implement-proofread-skill）
- **新增 discipline rule**：把 code-and-manuscript-sync.md（149 行）port 進 propositions 的 rules/，讓 propositions plugin 被載入時這條 rule 就會生效
- **新增 references 目錄**：建立 propositions/references/，放入 mcs.md（32 行 metadata pointer）+ mcs.pdf（13 MB，proofread workflow 引用的論文）
- **不動 plugin metadata**：.claude-plugin/plugin.json、.claude-plugin/marketplace.json 已是 self-hosted single-plugin marketplace，沿用現狀

## Non-Goals (optional)

- 不在本次完成 proofread skill 的 execution body — 那是 v0.1.0 → v0.2.0 的工作，留給 sister change implement-proofread-skill
- 不在本次刪除或退場 math-tools plugin（在 psychquant-claude-plugins marketplace 底下）— 等 propositions 驗證可用後，sister change deprecate-math-tools-plugin 處理
- 不在本次把 propositions 加進 psychquant-claude-plugins marketplace — 目前 self-hosted single-plugin marketplace 已運作，不改 distribution 路徑
- 不改 proofread SKILL.md 的內容、不調整 v0.1.0 SCAFFOLDING 文字 — 純檔案搬移，內容 byte-identical

## Capabilities

### New Capabilities

- `manuscript-code-sync-discipline`: propositions plugin 載入時，新增 code-and-manuscript-sync rule 提供的 discipline — 當 Claude Code 在 propositions 環境下協助使用者改動會同時影響 code 與 manuscript 的工作時，這條 rule 約束兩邊必須同步變更（不單側改 code 不改 manuscript，反之亦然）

### Modified Capabilities

(none)

## Impact

- Affected specs：新建 specs/manuscript-code-sync-discipline/spec.md
- Affected code：
  - New: skills/proofread/SKILL.md
  - New: rules/code-and-manuscript-sync.md
  - New: references/mcs.md
  - New: references/mcs.pdf
- 影響範圍：propositions plugin 被載入時，新 rule 會被 Claude Code 自動 pick up；新 skill 會在 /propositions:proofread 可見（雖然狀態仍是 SCAFFOLDING，但 skill description 已能 trigger）
- 來源 plugin（psychquant-claude-plugins 底下的 math-tools）不動，本次純單向 port，不刪不改不退場
