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

每份文件各自負責一塊，**同一件事只寫在一個地方**，其他地方只放指路：

| 順序 | 文件 | 只有這裡有 |
|---|---|---|
| 1 | **`HANDOVER.md`** | **UI／系統文字（B 產線）的完整流程 ＋ 七個踩過的坑**，最重要 |
| 2 | `translation_rules.md` | 譯文風格與遊戲術語對照：台灣用語、標點、角色語氣、禁翻欄位 |
| 3 | `AGENTS.md` | 技術鐵律：manifest hash、CDN 驗證、禁翻欄位、紋章色標 |
| 4 | `It will be used to extract plot text/README.md` | 劇情（A 產線）環境安裝與一鍵指令 |
| 5 | `It will be used to extract plot text/官方更新交接手冊.md` | A 產線的原理、產出結構、驗證與常見錯誤 |
| 6 | **另一個 repo**：`hook/DotAbyssHook-frida/更新流程.md` | Android 漢化 APK 的重打包與發布。Android 把翻譯**內嵌進 APK**，不走 CDN，所以 manifest／verify_cdn 那些步驟與它無關 |
| 7 | 同上 repo 的 `NOTES.md` | Android 端的技術細節與實機現況（會隨版本更新）|

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
| `tools/` | UI／系統文字的工具（含 `check_names.py` 譯名一致性檢查） |
| `It will be used to extract plot text/` | 劇情文本抓取工具鏈 |

### 環境

- Python 3.12（`tools/*.py` 只用標準函式庫，不必裝套件）
- 劇情抓取工具鏈需另建 venv，見該資料夾 README
- 需要能實機進遊戲驗證（有些字串只有實機才驗得出來）

---

## 官方改版時的總順序（兩個 repo、三條線）

這一節只管**次序**與**接縫**，每一步的細節仍在各自的文件裡。
今天會出事的地方幾乎都在接縫上，不在單一步驟裡。

```
0. 確認更新真的上線了     ← 最容易憑「公告說幾點」腦補
1. A 產線：劇情           2. B 產線：UI／系統文字
        └──────────┬──────────┘
                   3. 重建分包 + 更新 manifest
                   4. commit + push
                   5. verify_cdn.py --purge   ← PC 版玩家到此才真的拿得到
                   6. Android：重打包 APK
                   7. 發 GitHub Release
```

### 0. 先確認官方更新上線了沒（別信公告時間）

```bash
python "It will be used to extract plot text/tools/check_update.py"
```

看 `AssetVersionAndroidDmmR18` 與 `resource` 有沒有跳號。改版當天可以掛
`wait_for_update.sh` 輪詢到變動為止。

> 🩸 **2026-08-20**：公告寫下午三點，實際上 `resource` 中午 12:03 就從 53 跳到 54。
> 只往前輪詢而不查歷史，會永遠看到「無變化」。

### 0.5 已經有 Masterdata clone 的話，要 pull

```bash
git -C "<Masterdata>" pull --ff-only
```

> 🩸 **2026-08-20**：忘了這步，`extract_masterdata_missing.py` 拿三個版本前的
> clone 去比，報「只缺 8 條」。實際上是 **395 條**。
> 這個錯誤不會有任何警告——工具只會老實地比對你給它的東西。

### 1～2. 兩條產線

見下方「指令速查」。兩條互不相干，可以並行。

### 3～5. 收尾與發布（PC 版到此結束）

見下方「收尾」清單。**`verify_cdn.py --purge` 沒跑等於沒推。**

### 6～7. Android（另一個 repo）

```
hook/DotAbyssHook-frida/更新流程.md
```

那份分「情境 A：只改了翻譯」與「情境 B：官方改版了」。判斷依據是**官方 APK 版號有沒有變**：

| 官方版號 | 做法 | 耗時 |
|---|---|---|
| 沒變 | `python build.py --reinject` | 約 1 分鐘 |
| 變了 | `python build.py`（**不給 `--input` 就會自動向 DMM API 查最新版並下載**）| 約 3～4 分鐘（多半在下載）|

版號查詢就是第 0 步那支 `check_update.py` 印的 `APK: x.y.z code=N`。

打包完 `adb install -r` 升級（同一把 keystore，`firstInstallTime` 不變，存檔保留），
實機驗過再發 Release，把 `dist/DotAbyssX-R18-zh-Hant.apk` 傳上去。

> 驗 Release 傳對了沒，不必整包下載——比對頭尾各 64 KB 就夠：
> `curl -sL -r 0-65535 <asset_url>` 與本機檔案的前 64 KB 對 md5，尾端同理。

---

## 指令速查

⚠️ **這裡只列指令順序。每一步的參數、判準與踩過的坑一律看 `HANDOVER.md`**——
細節寫兩份一定會漂移，之後照著舊那份做就出事。第一次做請整份走完一遍。

以下都在本資料夾內執行。

### A. 劇情（novels）—— 細節見 `It will be used to extract plot text/`

```bash
# 1. 抓官方最新劇情（首次要先建 venv，見該資料夾 README）
& '.\It will be used to extract plot text\tools\OfficialNovelUpdate.ps1'
# 2. 翻 <輸出根>\output\official_update_<日期>\pending_novels\
# 3. 翻好的資料夾放回 novels/（已上線）或 novels_untranslated_only/（未上線）
python tools/build_novels_all.py      # 4. 重建分包（遊戲讀分包，不讀逐檔）
python tools/update_manifest.py       # 5. 更新 hash
```

### B. UI／系統文字（masterdata）—— 細節見 `HANDOVER.md` 第 1～3 節

```bash
git clone https://github.com/DotAbyss/Masterdata                                    # 1. 拿最新 masterdata
python tools/extract_masterdata_missing.py --current . --master "<Masterdata>" --output "<輸出夾>"
# 2. 先讀 <輸出夾>\比對報告.md 看規模，再翻 待翻譯.json（翻之前先 grep 既有句式）
python tools/merge_translated.py --input "<輸出夾>/待翻譯.json" --dry-run           # 3. 看報告，OK 再拿掉 --dry-run
python tools/build_combo_keys.py --master "<Masterdata>"                             # 4. 組合 key
python tools/update_manifest.py                                                      # 5. 更新 hash
```

### 收尾（兩條線共用，別跳過）

```
□ python tools/build_combo_keys.py --master "<Masterdata>" --check   通過
□ 禁翻的三個欄位仍為空（見 AGENTS.md）
□ python tools/check_names.py --min 5   —— 譯名一致性複查（人工判讀，不是硬性關卡）
□ git add 之後，用 git show :<路徑> 取暫存區 blob 算 md5，比對 manifest
   —— 不能驗工作區檔案，Windows 的 CRLF 會讓 md5 對不上（HANDOVER 陷阱一）
□ commit + push（逐檔 git add，本 repo 禁用 git add -A）
□ python tools/verify_cdn.py --purge   通過   ← push 之後
□ 實機進遊戲確認
```

> **最後兩件事最不能漏，而且都沒有錯誤訊息**：
> `update_manifest.py` 漏了 → hash 對不上 → mod 不重抓 → 玩家永遠拿到舊翻譯；
> `verify_cdn.py` 漏了 → CDN 還在餵舊檔 → 你以為推上去了，玩家還是日文
> （`HANDOVER.md` 陷阱一、陷阱七）。
