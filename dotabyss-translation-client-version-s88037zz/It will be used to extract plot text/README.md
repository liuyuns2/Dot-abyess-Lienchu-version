# 提取劇情文本的工具鏈

官方改版後，**劇情文本（novels）**要從官方 CDN 的 Unity bundle 下載解包才拿得到——
不像 UI／系統文字可以從 masterdata 直接讀。這個資料夾放的就是那套工具。

> 這是「A 產線」。另一條「B 產線」（UI／系統文字）見上層的 `HANDOVER.md`。
> **兩條都做完才算一次完整更新。**

## 檔案

| 項目 | 說明 |
|---|---|
| `官方更新交接手冊.md` | **完整操作手冊**，先讀這份 |
| `tools/OfficialNovelUpdate.ps1` | 一鍵入口，依序跑完 9 個步驟 |
| `tools/*.py` | 各階段工具（抓 catalog、下載、解包、套翻譯記憶、驗證…） |

## 快速開始

首次使用先建 Python 環境（在 `tools/` 裡）：

```powershell
Set-Location "<這個資料夾>\tools"
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install requests msgpack pycryptodome rich UnityPy
```

之後每次官方更新只要：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
Set-Location "<這個資料夾>\tools"
.\OfficialNovelUpdate.ps1
```

**路徑全部自動推導，clone 下來直接能跑，不用改腳本。**
執行時會先印出推導結果，確認無誤再讓它跑：

```
工具目錄   : ...\It will be used to extract plot text\tools
本 repo    : ...\Dot-abyess-Lienchu-version
輸出根     : ...\dotabyss-output      ← 在 repo 外，不會污染版控
額外記憶庫 : （無 -X-，僅用本 repo 的 novels 當翻譯記憶）
```

推導規則以**本腳本的位置**為基準，不依賴外層目錄叫什麼名字。

### 關於「翻譯記憶」

腳本會拿既有翻譯自動填好能沿用的句子，只留真正的新句子給你翻。來源：

| 來源 | 說明 |
|---|---|
| `<本 repo>\...\novels` | 一定會用 |
| `<本 repo>\...\novels_untranslated_only` | 一定會用 |
| `<同層>\-X-\novels` | **選用**。這是原作者的另一個獨立 repo，接手者通常沒有；偵測不到就自動略過，不影響執行 |

若你手上也有 `-X-` 那個 repo，把它跟本 repo 放在同一層即可自動被認出。

### 需要覆寫時

```powershell
.\OfficialNovelUpdate.ps1 -UpdateDate "2026-08-06"        # 補跑指定日期
.\OfficialNovelUpdate.ps1 -BaseDir "X:\輸出"               # 換輸出位置
.\OfficialNovelUpdate.ps1 -RepoRoot "X:\含-X-的那層"        # 指定額外記憶庫
.\OfficialNovelUpdate.ps1 -PythonExe "C:\Python312\python.exe"
```

## 這裡「沒有」什麼

為了不把 repo 撐大，以下**刻意不收**，需要時自行取得或由腳本產生：

- `MasterData.json`（約 30MB，每次改版都不同，跑腳本會自動抓最新的）
- `assets.json`、`catalog_1.bin`（下載產物，數百 MB）
- Unity 安裝檔、build log 等與劇情提取無關的檔案

## 跑完之後

產出在 `<BaseDir>\output\official_update_<日期>\`，重點看：

| 項目 | 意義 |
|---|---|
| `pending_novels\` | **要翻的東西**（只補空 value，別動日文 key） |
| `new_folders_only\` | 全新劇情資料夾 |
| `empty_translations\*.html` | 空值報告，可視化 |
| `l2d_changes.txt` | 相對上一版新增／移除的 L2D |

翻完 → 驗證（手冊第 6 節）→ 同步回 repo → **再回上層 `HANDOVER.md` 第 3 節重建分包＋更新 manifest**。

> 這最後一步最容易漏：本工具鏈**不會動 manifest**，
> 漏了的話劇情進了 repo，玩家還是拿不到。
