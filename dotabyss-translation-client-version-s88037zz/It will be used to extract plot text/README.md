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

**路徑會自動推導，不用改腳本。** 執行時會先印出它推導的位置，確認無誤再讓它跑：

```
工具目錄 : ...\It will be used to extract plot text\tools
Repo 根  : ...\GITHUB-dotabyss-translation
輸出根   : ...\dotabyss-output        ← 在 repo 外，不會污染版控
```

推導規則：`Repo 根` = 從 `tools/` 往上 4 層（即含 `-X-` 與
`Dot-abyess-Lienchu-version` 的那層）；`輸出根` = repo 根的同層 `dotabyss-output`。

### 需要覆寫時

若你的目錄結構不同（例如 repo 放在別處、想把輸出放到別的磁碟）：

```powershell
.\OfficialNovelUpdate.ps1 -RepoRoot "X:\你的\GITHUB-dotabyss-translation" -BaseDir "X:\輸出"
.\OfficialNovelUpdate.ps1 -UpdateDate "2026-08-06"      # 補跑指定日期
.\OfficialNovelUpdate.ps1 -PythonExe "C:\Python312\python.exe"
```

`RepoRoot` 一定要指對，因為腳本會讀底下三個 novels 位置當「翻譯記憶」
（把能沿用的舊翻譯自動填好，只留真正的新句子給你翻）：

- `-X-\novels`
- `Dot-abyess-Lienchu-version\...\novels`
- `Dot-abyess-Lienchu-version\...\novels_untranslated_only`

指錯的話腳本會直接報錯停下（不會默默跑出錯誤結果）。

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
