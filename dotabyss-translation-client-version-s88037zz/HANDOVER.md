# 官方更新處理流程（交接手冊）

這份文件寫給**接手維護漢化的人**：官方每次改版後，從拿到資料到推上線的完整步驟。

其他文件的分工：

| 文件 | 內容 |
|---|---|
| `AGENTS.md` | 技術鐵律（manifest hash、禁翻表、紋章色標） |
| `translation_rules.md` | 譯文風格（台灣用語、角色語氣、標點） |
| **`HANDOVER.md`（本檔）** | **UI／系統文字的更新流程與踩坑清單** |
| `It will be used to extract plot text/` | **劇情文本的抓取工具鏈**（已收進 repo，見下方「兩條產線」） |

---

## 兩條產線（先看懂這個）

漢化內容分成兩塊，**來源不同、工具不同、流程也不同**：

### A. 劇情文本（novels）

| | |
|---|---|
| 來源 | 官方 CDN 的 Unity bundle（要下載解包） |
| 工具 | `It will be used to extract plot text/tools/OfficialNovelUpdate.ps1`（一鍵） |
| 手冊 | `It will be used to extract plot text/`（先讀該資料夾的 `README.md`） |
| 產出 | `pending_novels\<id>\zh_Hant.json`（只補空 value） |
| 進 repo | `novels/` 或 `novels_untranslated_only/` |

### B. UI／系統文字（本檔負責）

| | |
|---|---|
| 來源 | masterdata（GitHub 鏡像）＋ dump（mod 傾印） |
| 工具 | 本 repo 的 `tools/*.py` |
| 產出 | `static` / `ui_texts` / `add-on` / `names` |

**兩條線都做完，才算完成一次官方更新。**

A 線的細節（環境安裝、一鍵腳本、驗證、L2D 差異比對）全在 `It will be used to extract plot text/` 裡（先讀該資料夾的 `README.md`），本檔不重複。只提三個銜接重點：

1. **A 線產出的劇情要進 repo**，之後 B 線的 `build_novels_all.py` 才會把它打包進 `novels_*_all/`（遊戲實際讀的是分包，不是逐檔）。
2. **A 線有兩個 repo 位置**：`-X-\novels`（主要翻譯庫）與本 repo 的 `novels/`、`novels_untranslated_only/`。A 線的翻譯記憶會同時比對這三處。
3. **A 線不會動 manifest**。劇情進 repo 後，仍要回到本檔第 3 節重建分包＋更新 manifest，否則玩家拿不到。

---

## 0. 事前準備

### 需要的東西

| 項目 | 位置 | 說明 |
|---|---|---|
| masterdata | <https://github.com/DotAbyss/Masterdata> | 官方 masterdata 鏡像，每次改版後抓最新一份 |
| dump | `<遊戲>/BepInEx/plugins/AbyssMod/dump/*_raw.json` | mod 把「查不到翻譯的字串」傾印於此 |
| 遊戲本體 | 需能實際進遊戲驗證 | 有些字串只有實機才驗得出來 |

建議把歷次 masterdata 用日期分資料夾保留（例：`Masterdata-main0731/`），**diff 新舊兩份才知道官方改了什麼**。

### 三個資料檔的角色（最重要的觀念）

翻譯資料分別走**兩條完全不同的管線**，這決定新字串該寫進哪裡：

```
static/zh_Hant.json   ← AbyssStaticFix 插件抓取後「改寫遊戲的 masterdata」
                        按 (表, 欄位, 原文) 定址；只注入非空的 m_* 表

ui_texts/zh_Hant.json ← AbyssMod 插件合成「執行期字串查表」
add-on/**/zh_Hant.json  純字串比對，不管資料來自哪
names/zh_Hant.json
```

**判準**：

- masterdata 裡真有那筆資料 → 寫 `static` 對應的表
- UI 標籤、`{N}` 模板、組合再查詢 key → 寫 `ui_texts`
- ⚠️ **兩者都要寫的情況見第 5 節「陷阱三」**

---

## 1. 比對 masterdata，找出官方改了什麼

```bash
# 用 Python 逐檔 md5 比對新舊兩份 masterdata
# 輸出「內容有變的檔案清單」
```

檔案數量會告訴你更新規模：

- **10 檔以內** → 小改（多半只是數值/獎勵調整，可翻的很少）
- **100 檔以上** → 大改（通常是新角色或新活動）

接著從有變動的檔案抽出「**含日文、且不在現有翻譯庫**」的字串。要掃的主要欄位：

```
m_characters/name              角色名
m_character_profiles/profile   角色檔案
m_character_profiles/another_name  角色副標（要翻）
m_novel_characters/title       劇情標題
m_novel_characters/description 劇情簡介
m_novel_events/title           活動劇情標題
m_novel_homes/title            日常劇情標題
m_ability_details/description  能力描述（量最大，多為模板族）
m_character_action_skills/description  主動技能描述
m_missions/title               任務
m_items/name                   道具
m_events/name, m_gacha_groups/name, m_dungeons/name  活動/轉蛋/副本
m_character_skins/name+description+serif  服裝（三欄都要看）
m_enemy_skills/name            敵人技能（要翻）
m_nether_codes/name+description 深淵代碼
```

**⚠️ 存在性檢查要對「全庫」**，不能只查該表——同一句話可能已在 ui_texts 或別的表翻過了。

---

## 2. 翻譯

### 鐵律：翻之前先 grep 既有句式

**這是最容易出錯的一步。** dump/masterdata 出現的字串，常常屬於某個已有大量既有譯法的句式。憑感覺翻會製造不一致。

做法：抽出句子的固定框架（例如 `に出撃します`、`を再生します`、`をクリア`），grep 現有 `ui_texts`/`static`，有既有譯法就**照抄句式**。

實例（真的發生過）：

- 補活動劇情標題時沒查，結果同一標題有「觀測氣球傳回的照片」和「觀測氣球傳回來的照片」兩種譯文
- 補災厄名時沒查，用了「出擊討伐」但既有 20 條都是「即將出擊挑戰」

### 模板族用機械生成

能力描述常常是同一句話換數字，例如：

```
自身の最大HPが【{7%}】上昇
自身の最大HPが【{13%}】上昇   ← 80 條只有數字不同
```

**寫正規表示式模板批次生成**，不要逐條手翻。**生成前先自證**：拿模板回套既有條目，確認產出與現有譯文逐字相同，才套用到新條目。

### 政策：技能名維持原文

```
m_character_abilities/name        ← 整表清空，不翻
m_character_action_skills/name    ← 整表清空，不翻
m_gacha_group_movies/skill_name   ← 整表清空，不翻
```

新版本冒出的能力名/技能名**一律不翻**。補完後要驗證這三表仍為空。

二つ名（帶 `[LvN]` 的稱號）同樣維持原文，且**不可加進 ui_texts**——會害二つ名畫面顯示中文。

---

## 3. 跑工具

### 劇情有變動 → 重建分包

```bash
python tools/build_novels_all.py
```

`novels/` 和 `novels_untranslated_only/` 是**來源**，`novels_*_all/` 是**產物**。
永遠改來源再重建，不要直接改分包（下次重建會被覆蓋）。

### 補完 masterdata → 生成組合 key

```bash
# 指到你這次用的 masterdata
DOTABYSS_MASTERDATA="D:/.../Masterdata-mainXXXX/data" python tools/build_combo_keys.py

# 只檢查不寫檔（有缺口 exit 1，可掛 CI）
python tools/build_combo_keys.py --check
```

這支工具管五族「組合式再查詢 key」——遊戲會先翻片段、組成整句、再查一次，所以字典必須預存完整組合句。詳見工具內註解。

### 更新 manifest（**絕對不能漏**）

```bash
python tools/update_manifest.py
```

或手動重算：改過的檔案各自的 md5 + 頂層 `hash`。

> **hash 對不上 = 玩家永遠拿到舊版**，因為 mod 靠 hash 判斷要不要重抓。

---

## 4. 驗證與提交

提交前逐項確認：

```
□ JSON 合法（json.load 過）
□ manifest 各檔 md5 與檔案內容相符
□ manifest 頂層 hash = 去掉 hash 欄位後最小化 JSON 的 md5
□ 用 git show :path 取「暫存區 blob」驗 md5（不是工作區檔案，見陷阱一）
□ 技能名三表仍為空
□ python tools/build_combo_keys.py --check 通過
□ git status 只有預期的檔案
```

⚠️ **不要用 `git add -A`**——上層有未追蹤的 `.zip` 和 TEST 資料夾。逐檔 `git add`。

---

## 5. 踩過的坑（按嚴重度排序）

### 陷阱一：CRLF 讓 manifest hash 全錯 🩸

repo 的 `.gitattributes` 設定 `*.json text eol=lf`，git 存的 blob 是 **LF**，CDN 服務的也是 LF。但 Windows 工作區的檔案常是 **CRLF**。

若拿工作區檔案算 md5 → 算出 CRLF 的值 → 與 LF blob 對不上 → **玩家載不進翻譯**。

```python
# 正確：算 hash 前先正規化
md5 = hashlib.md5(open(p,'rb').read().replace(b'\r\n', b'\n')).hexdigest()

# 驗證要用 blob，不是工作區檔
git show :path/to/file.json | md5
```

### 陷阱二：key 差一個字元，永遠命不中

翻譯是**用日文原文當 key 精確比對**，差一個字元就完全失效。而且**在 repo 端完全看不出來**（key/value/JSON 都正常），只有拿 dump 或官方原文逐字元比對才抓得到。

真實案例：

| 庫裡的 key | 遊戲實際查的 | 差異 |
|---|---|---|
| `このままお話しを続けても…` | `このままお話を続けても…` | 多一個「し」 |
| `雪明り` | `月明り` | 雪/月 |
| `問題が……。` | `問題が……` | 多一個句號 |
| `討伐成功です！⏎やりましたね！` | `討伐成功です！\nやりましたね！` | 真換行 vs **字面** `\n` |

最後一項特別注意：**dump 的 JSON 值裡看到 `\\n`，那是字面的兩個字元（`0x5c 0x6e`），不是換行（`0xa`）**。比對時印字元碼確認，別憑外觀判斷。

**根治法**：跟官方原文做全量 key diff。若能拿到官方劇情原文，逐篇比對 key 集合，一次抓出所有錯字。

### 陷阱三：只寫 static 不夠 🔁

**已經踩了三次的坑。**

masterdata 有的資料放 `static` 是對的，但**同一個名稱若也會被 UI 元件當字串畫出來**，那個畫面走 runtime fallback（ui_texts），static 注入對它無效 → 只寫 static 就顯示日文。

三次實例：活動橫幅、災厄戰結算台名、關卡列表劇情標題。

**判準（補名稱類時自問）**：這個名字會不會出現在 **關卡/劇情列表、播放確認框、活動橫幅、服裝/道具選擇框**？

- 會 → **static 和 ui_texts 都要寫**（譯文相同）
- 只在詳情面板顯示 → 可只放 static

省事作法：**整張表鏡射進 ui_texts**，別等玩家逐條回報。

### 陷阱四：改譯名要連改組合 key

若某名詞已被用來預生成組合 key，改譯名時必須同步改所有含它的組合 key，否則遊戲用新譯名組出的 key 會對不上。

改名詞前先 grep 它有沒有出現在組合 key 裡。

### 陷阱五：全域替換會誤傷

修正譯名時**不要無條件全域替換**，要用「key 含該日文詞」當條件。

實例：`ヒマリ` 誤譯「向日葵」要改成「葵」，但另有一句「如**向日葵**般燦爛的笑容」原文是 `ひまわり`（真的花），不能動。

同理：`兇`（兇猛/元兇）不能因為要統一「凶化災厄」就全掃。

### 陷阱六：酒館色標靠對照表，不是 `<color>` 標籤

酒館提案描述的紫/綠字，是遊戲拿 `m_tavern_text_color`（詞→顏色對照表）比對描述文字**自動上色**。

所以描述譯文**不該自己加 `<color>`**，但**色標表的譯文必須與描述譯文逐字相同**，否則對不上就不上色（靜默失效，很難發現）。

改酒館用詞時兩邊都要改。

> 注意這跟**紋章色標**相反——紋章的 `<color=#FF5050>紋章：情熱</color>` 是譯者刻意加的，詳見 `AGENTS.md`。

---

## 6. 玩家回報「某處沒翻」的排查順序

1. **查 dump** —— 有的話用它的精確位元組當 key（最可靠）
2. **dump 沒有 → 查 masterdata** —— 找出它屬於哪張表哪個欄位
3. **兩處都查無 → 是客戶端寫死的 UI 字串** —— 照截圖逐字轉錄，補進 `ui_texts`，請玩家實機確認
4. **庫裡明明有譯文卻顯示日文** → 依序懷疑：
   - key 差字元（陷阱二）
   - 只寫了 static（陷阱三）
   - manifest hash 沒更新（陷阱一）
   - CDN/本地快取還沒更新

---

## 7. 常用術語對照（完整版見 `translation_rules.md`）

| 日文 | 中文 | 備註 |
|---|---|---|
| 厄災 | 災厄 | 語序相反 |
| 凶化厄災 | 凶化災厄 | 非「兇化」 |
| ランク（裝備） | Rank | 但 VIPランク/プレイヤーランク＝等級 |
| 浸食率/侵食率 | 侵蝕率 | 動詞用**增加/減少**，非上升/下降 |
| 会心 | 暴擊 | 非「會心」 |
| 回避率 | 閃避率 | |
| モンスター | 魔物 | 非「怪物」（原文另有 怪物/化け物 要保留） |
| 大穴 | 大洞窟 | 非大洞穴/巨穴 |
| 掃討 / 追跡 | 掃蕩 / 追蹤 | 日文漢字詞，中文不用 |
| マナ | 魔力 | 非「能量」 |
| ツルハシ / ピッケル | 十字鎬 | 兩詞共用同一中文 |
| エネミー | 敵方 | |
| 主人公 | 主角 | |

**數值增減標準**：上升 / 下降（⚠️ 但侵蝕率例外，用增加/減少）

---

## 8. 給接手者的幾句話

- **先搞清楚自己在做哪條產線**（見開頭「兩條產線」）。劇情文本走 `It will be used to extract plot text/tools/`，UI／系統文字走本 repo 根的 `tools/`。兩條都做完才算一次完整更新。
- **這個專案最大的風險不是翻錯，是「翻了但沒生效」**——key 差一字、manifest 沒更新、寫錯檔案，都會讓翻譯靜默失效。第 4 節的驗證清單請每次都跑。
- **玩家截圖是最好的 QA**。庫裡看起來正常的東西，實機可能完全沒生效。
- **不確定就別猜**：dump 和 masterdata 是兩個 ground truth，查得到就別憑截圖轉錄。
- 歷次踩坑的細節都寫在 git commit message 裡，遇到怪問題可以 `git log --grep` 搜搜看。
