## 1. 移植 code-and-manuscript-sync rule（承載 spec 三條 Requirements）

- [x] 1.1 把 code-and-manuscript-sync.md 從 /Users/che/Developer/psychquant-claude-plugins/plugins/math-tools/rules/ 複製到 propositions/rules/，讓 "Cross-file sync discipline when propositions plugin is loaded" requirement 由 rule 開頭的「規則(HARD RULE)」、「為什麼」、「Diagnosis 階段必檢」、「Verification 階段必檢」四段共同承載。完成條件：rule 檔案 byte-identical、四段標題與內容完整存在。驗證：`diff -q /Users/che/Developer/psychquant-claude-plugins/plugins/math-tools/rules/code-and-manuscript-sync.md /Users/che/Developer/propositions/rules/code-and-manuscript-sync.md` exit 0；`grep -c "^## " /Users/che/Developer/propositions/rules/code-and-manuscript-sync.md` 回傳 >= 11（原 rule 主要 section 數）。

- [x] 1.2 驗證移植後 rule 內「Submodule 邊界 ≠ IDD scope 邊界」section 完整存在 — 此段落實現 "Submodule boundary does not split scope" requirement。完成條件：該 section 標題、bash 範例 `git checkout -b idd/cluster-...`、「兩個 PR 互相 cross-link」段落都完整呈現。驗證：`grep -A 20 "Submodule 邊界" /Users/che/Developer/propositions/rules/code-and-manuscript-sync.md` 命中且包含 `cross-link` 字樣。

- [x] 1.3 驗證移植後 rule 內「Frozen historical record exception」與「Within-file frozen subregion exception」兩 section 完整存在 — 此兩段落實現 "Frozen subregions are exempt from sync" requirement，內含 manuscript/docs/rounds/、correspondence/、archived/ 等 frozen paths 清單與 living docs 邊界。完成條件：兩 sections 標題、frozen paths 清單、邊界說明都未被截斷。驗證：`grep "Frozen historical record exception" /Users/che/Developer/propositions/rules/code-and-manuscript-sync.md` 命中；`grep "manuscript/docs/rounds" /Users/che/Developer/propositions/rules/code-and-manuscript-sync.md` 命中。

## 2. 移植 proofread skill scaffolding 與 references

- [x] 2.1 把 proofread skill 從 /Users/che/Developer/psychquant-claude-plugins/plugins/math-tools/skills/proofread/SKILL.md 複製到 propositions/skills/proofread/SKILL.md（建立 propositions/skills/proofread/ 目錄）。執行行為留給 sister change implement-proofread-skill，本 task 只 port scaffolding。完成條件：SKILL.md byte-identical、YAML frontmatter 的 name/description/allowed-tools 完整、「Status (v0.1.0)」+「Scaffolding only」標示完整。驗證：`diff -q` 比對來源 exit 0；`grep "v0.1.0 SCAFFOLDING" /Users/che/Developer/propositions/skills/proofread/SKILL.md` 命中。

- [x] 2.2 建立 propositions/references/ 目錄並 port mcs.md（32 行 metadata pointer）與 mcs.pdf（13 MB 論文 PDF）。完成條件：兩檔存在於 propositions/references/ 下、mcs.pdf SHA-256 與來源相同（確認 13 MB binary 未被破壞）。驗證：`ls /Users/che/Developer/propositions/references/` 列出 mcs.md 與 mcs.pdf 兩檔；`shasum -a 256 /Users/che/Developer/propositions/references/mcs.pdf /Users/che/Developer/psychquant-claude-plugins/plugins/math-tools/references/mcs.pdf` 兩個 hash 一致。

## 3. 驗證 plugin 載入無回歸

- [x] 3.1 確認 propositions/.claude-plugin/plugin.json 不需修改即可讓 Claude Code 自動 pick up 新 rule、新 skill scaffolding、新 references。完成條件：git diff 在 .claude-plugin/plugin.json 為空；reload Claude Code 後 propositions plugin 仍為 v0.1.0、新 skill 出現在 /propositions:proofread 列表、新 rule 在 plugin 載入時被讀取。驗證：`git -C /Users/che/Developer/propositions diff --quiet .claude-plugin/plugin.json` exit 0；reload 後 `claude plugin list` 列出 propositions 0.1.0；`claude plugin info propositions` skills 區段包含 proofread 三個 skill（validate、refresh-locations、audit、proofread）。

- [x] 3.2 跑既有 test suite 確認 port 不破壞 plugin 內部測試。完成條件：pytest 全綠（目前 baseline 142+ passed），新增的 propositions/references/ 與 propositions/skills/proofread/ 不影響 test discovery 也不引入新的 import 衝突。驗證：`pytest tests/ -q` exit 0；output 報告至少 142 passed、0 failed、0 error。
