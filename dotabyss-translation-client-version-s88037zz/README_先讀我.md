# 先讀我（接手者入門）

## 你拿到的是哪一種？？

### A. 從 GitHub clone —— 建議走這條

```bash
git clone https://github.com/liuyuns2/Dot-abyess-Lienchu-version.git
```

直接跳到下面「**開始工作**」。

### B. 拿到 zip 壓縮檔

zip 可以用，但**解壓後必須先做一件事**，否則之後提交的翻譯會讓玩家載不進去：

```powershell
# 確認這個檔存在（本資料夾內應該有）
Get-Content .gitattributes
# 應顯示：*.json text eol=lf
```

若要把 zip 內容變成能提交的 git repo：

```powershell
git init
git add .gitattributes          # ← 一定要第一個加，且先於任何 json
git commit -m "chore: line ending policy"
git add .
git commit -m "init from zip"
```

**為什麼**：Windows 預設把文字檔存成 CRLF 換行，但 manifest 的 md5 必須用
LF 內容計算（GitHub raw 服務的也是 LF）。`.gitattributes` 就是強制 JSON 用
LF 的設定。少了它 → md5 對不上 → **玩家永遠拿到舊翻譯**，而且不會有任何錯誤訊息。
（細節見 `HANDOVER.md` 陷阱一）

> ⚠️ zip 沒有 git 歷史，所以你**無法**：
> - 用 `git show :path` 驗證 blob md5（`HANDOVER.md` 驗證清單的必要步驟）
> - 用 `git log --grep` 查歷次踩坑的原因（都寫在 commit message 裡）
> - 把修改推回 GitHub 給其他人
>
> 有機會的話還是請原作者給 GitHub 協作權限。

---

## 開始工作

### 文件導覽（依閱讀順序）

| 順序 | 文件 | 內容 |
|---|---|---|
| 1 | **`HANDOVER.md`** | **官方更新的完整流程 + 六個踩過的坑**，最重要 |
| 2 | `translation_rules.md` | 譯文風格：台灣用語、角色語氣、標點 |
| 3 | `AGENTS.md` | 技術鐵律：manifest hash、禁翻表、紋章色標 |
| 4 | `It will be used to extract plot text/README.md` | 劇情文本抓取工具鏈 |

### 一句話理解這個專案

> 翻譯是**用日文原文當 key 去精確比對**。
> 所以最大的風險不是翻錯，而是**「翻了但沒生效」**——
> key 差一個字元、manifest 沒更新、寫錯檔案，都會讓翻譯靜默失效。

### 目錄速查

| 路徑 | 是什麼 |
|---|---|
| `static/` | masterdata 翻譯（按 表/欄位/原文 定址） |
| `ui_texts/` | UI 字串查表（執行期比對） |
| `names/` | 角色譯名權威表 |
| `add-on/` | 額外字串（裝備組合等） |
| `novels/` | 劇情文本**來源**（已上線） |
| `novels_untranslated_only/` | 劇情文本來源（未上線） |
| `novels_*_all/` | 劇情**分包**（產物，遊戲實際讀這個，勿手改） |
| `manifest/` | 各檔 md5 + 總 hash（**改任何東西都要更新**） |
| `tools/` | UI／系統文字的工具 |
| `It will be used to extract plot text/` | 劇情文本抓取工具鏈 |

### 環境

- Python 3.12（`tools/*.py` 只用標準函式庫，不必裝套件）
- 劇情抓取工具鏈需另建 venv，見該資料夾 README
- 需要能實機進遊戲驗證（有些字串只有實機才驗得出來）
