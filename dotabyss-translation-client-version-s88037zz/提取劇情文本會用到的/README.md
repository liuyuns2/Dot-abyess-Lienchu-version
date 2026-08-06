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

```powershell
Set-ExecutionPolicy -Scope Process Bypass
Set-Location "<這個 tools 資料夾>"
.\OfficialNovelUpdate.ps1
```

首次使用要先裝 Python 依賴（`requests msgpack pycryptodome rich UnityPy`），
詳見手冊第 2 節。

## ⚠️ 路徑要改

`OfficialNovelUpdate.ps1` 的預設路徑是原作者的環境：

```powershell
$BaseDir  = "E:\離線板"                                  # 輸出根目錄
$RepoRoot = "D:\dotabyss-translation\GITHUB-dotabyss-translation"   # repo 根
```

接手者請用參數覆寫，或直接改檔案裡的 `param()` 預設值：

```powershell
.\OfficialNovelUpdate.ps1 -BaseDir "你的路徑" -RepoRoot "你的 repo 根"
```

腳本會讀 repo 的三個 novels 位置當「翻譯記憶」（把能沿用的舊翻譯自動填好），
所以 `-RepoRoot` 一定要指對：

- `-X-\novels`
- `Dot-abyess-Lienchu-version\...\novels`
- `Dot-abyess-Lienchu-version\...\novels_untranslated_only`

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
