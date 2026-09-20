# 官方更新處理流程（交接手冊）

這份文件寫給**接手維護漢化的人**：官方每次改版後，從拿到資料到推上線的完整步驟。

其他文件的分工：

| 文件 | 只有那裡有 |
|---|---|
| `README_先讀我.md` | 入口：clone/zip 的差別、目錄速查、指令速查 |
| `AGENTS.md` | 技術鐵律（manifest hash、CDN 驗證、禁翻**欄位**、紋章色標） |
| `translation_rules.md` | 譯文風格 ＋ 遊戲術語對照（台灣用語、標點、角色語氣） |
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

### 1-1. 抓最新 masterdata

```bash
git clone https://github.com/DotAbyss/Masterdata
```

### 1-2. 跑缺漏比對

```bash
python tools/extract_masterdata_missing.py --current . --master "<Masterdata>" --output "<輸出夾>"
```

三個參數都是**資料夾**：

| 參數 | 指向 |
|---|---|
| `--current` | 本資料夾（`static/`、`ui_texts/`、`names/`、`add-on/`、`other/` 的上一層），填 `.` 即可 |
| `--master` | clone 下來的 Masterdata repo 根（裡面有 `data/`）。指到 `data/` 本身也可以 |
| `--output` | 輸出夾，不存在會自動建 |

> ℹ️ 這個 repo 的 `m_*.json` 就放在根目錄的 `data/` 底下，**沒有版本號那層**。
> 兩支工具都會自己判斷「含 `data/` 的那層」或「`data/` 本身」，給哪個都行，
> 找不到 masterdata 一律 exit 1。

它比對的是「**新 masterdata ⟷ 你現有的翻譯**」，**不是**新舊兩版 masterdata，
所以不需要保留舊版。（留舊版是為了估規模、縮小檢查範圍，是加速手段不是必要步驟。）

### 1-3. 產出五個檔

| 檔案 | 動它嗎 |
|---|---|
| `比對報告.md` | ❌ **先讀這份**，看規模與各表分佈 |
| `待翻譯.json` | ✅ **工作檔**，結構與 `static/zh_Hant.json` 完全一致，只填 value |
| `同文異欄位_不需重翻.json` | ❌ 原文已在別處翻過，附既有譯文供核對 |
| `未知欄位_待確認.json` | ⚠️ 本工具追蹤不到的欄位，**每次都要掃一眼** |
| `待翻譯_來源明細.json` | ❌ 查證用：某句出現在哪個 record、屬哪一類 |

**「同文異欄位」不要重翻。** 外掛實測是**只比對原文、不看欄位**（使用者拿 4 筆
放錯表的條目在遊戲內驗證過，全部照樣顯示中文）。所以同一句原文全庫只能有一種
譯文；再翻一次就是製造兩種譯文互搶，誰贏不可預期。除非確定既有譯文是錯的，
否則不要動。

### 1-4. 這支工具的盲點

**只掃「已知欄位」。** 若某個 `(表, 欄位)` 在現有翻譯裡從未出現過，整個欄位會被
跳過。官方**新增一整張表或啟用新欄位**時它以前是完全沉默的。現在這些字串會落進
`未知欄位_待確認.json`（只收含日文又全庫沒譯過的），**每次比對後都要看一眼**。
確認要翻的話，先在 `static/zh_Hant.json` 該表該欄位手動補一條，之後就會自動追蹤。

> 🩸 這個盲點出過一次事：兩支工具原本把 `m_character_abilities` /
> `m_character_action_skills` **整張表**排除，但政策禁的只有 `name` 一欄，
> 於是 `m_character_action_skills/description` 從來沒被抽出過，每個新角色上線都是日文。
> 現在禁翻改成欄位層級、扁平檔（`ui_texts`/`names`）也納入覆蓋判斷、未知欄位另出清單。

### 1-5. 翻譯

只翻 `待翻譯.json`，**日文 key 一個字元都不能動**。翻之前務必先做第 2 節的
「grep 既有句式」。

### 1-6. 合併回 static

```bash
python tools/merge_translated.py --input "<輸出夾>/待翻譯.json" --dry-run
```

先看報告，確認無誤再拿掉 `--dry-run` 實際寫入。它會：

- 自動跳過禁翻的三個**欄位**（`m_character_abilities/name`、
  `m_character_action_skills/name`、`m_gacha_group_movies/skill_name`）；
  同表的 `description` 不在禁翻範圍，會正常合併
- 遇到既有譯文不同時**跳過並列出對照**，不會默默覆蓋（要覆蓋加 `--allow-overwrite`）
- 追加在原位置之後，不重排（`static/zh_Hant.json` 是插入序，重排會讓 diff 爆掉）
- 標示三類可疑條目：譯文與原文相同、譯文殘留假名、標籤與原文不一致

### 1-7. 人工複查時的重點欄位

以上流程涵蓋自動化的部分。要人工複查、或處理 1-4 的盲點 ①（官方新增整張表）時，
這些是最常有可翻內容的欄位：

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

**禁翻的三個欄位清單以 `AGENTS.md` 為唯一來源**（欄位層級，不是整張表；
同表的 `m_character_action_skills/description` 是要翻的，理由見 1-4）。
補完後要驗證那三個欄位仍為空。

實務上會咬人的兩點：

- 走 1-6 的 `merge_translated.py` 會自動擋掉那三個欄位，但**手動編輯
  `static/zh_Hant.json` 時沒有任何保護**——曾經就這樣誤翻進 13 條技能名。
- 二つ名（帶 `[LvN]` 的稱號）同樣維持原文，且**不可加進 ui_texts**
  ——會害二つ名畫面顯示中文。

---

## 3. 跑工具

### 順序（照這個跑，別跳）

```
1. extract_masterdata_missing.py   找出缺漏          ← 第 1 節
2. （翻 待翻譯.json）                                 ← 第 2 節
3. merge_translated.py             合併回 static     ← 第 1-6 節
4. build_novels_all.py             重建分包          ← 劇情有變動才要
5. build_combo_keys.py             生成組合 key
6. update_manifest.py              更新 hash         ← 絕對不能漏
7. 驗證與提交                                        ← 第 4 節
8. verify_cdn.py --purge           驗 CDN            ← push 之後，第 4 節
```

第 5、6、8 步最常被漏，而且**三個都不會有錯誤訊息**：

- 漏第 5 步 → 組合式畫面顯示日文
- 漏第 6 步 → 整包翻譯玩家都拿不到
- 漏第 8 步 → 你以為推上去了，玩家還在拿幾個 commit 前的檔案（見陷阱七）

### 劇情有變動 → 重建分包

```bash
python tools/build_novels_all.py
```

`novels/` 和 `novels_untranslated_only/` 是**來源**，`novels_*_all/` 是**產物**。
永遠改來源再重建，不要直接改分包（下次重建會被覆蓋）。

### 補完 masterdata → 生成組合 key

```bash
# 指到你這次用的 masterdata（跟第 1 節的 --master 給一樣的值即可）
python tools/build_combo_keys.py --master "<Masterdata>"

# 只檢查不寫檔（有缺口 exit 1，可掛 CI）
python tools/build_combo_keys.py --master "<Masterdata>" --check
```

`--master` 的路徑規則同第 1-2 節（含 `data/` 那層或 `data/` 本身都可以）。
也可改設環境變數 `DOTABYSS_MASTERDATA`，優先序為
`--master` > 環境變數 > 程式內預設值（預設值只是後備，換一台電腦必定失效，
請一律明確給 `--master`）。

這支工具管五族「組合式再查詢 key」——遊戲會先翻片段、組成整句、再查一次，所以字典必須預存完整組合句。詳見工具內註解。

### 更新 manifest（**絕對不能漏**）

```bash
python tools/update_manifest.py
```

或手動重算：改過的檔案各自的 md5 + 頂層 `hash`。

> **hash 對不上 = 玩家永遠拿到舊版**，因為 mod 靠 hash 判斷要不要重抓。

### push 之後：驗 CDN（**也絕對不能漏**）

```bash
python tools/verify_cdn.py --purge
```

`update_manifest.py` 只保證 **repo 內部**一致；玩家拿到的是 **jsDelivr**，
它對分支 ref 有最長 12 小時的快取。manifest 全綠、`git push` 成功，玩家照樣可能
拿到幾個 commit 前的檔案。詳見陷阱七。

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

**push 之後**再確認這兩項（前七項全過也不代表玩家拿得到）：

```
□ python tools/verify_cdn.py --purge 通過
□ 實機重開一次，看 BepInEx/LogOutput.log 沒有 Remote fetch failed
```

⚠️ **不要用 `git add -A`**——上層有未追蹤的 `.zip` 和 TEST 資料夾。逐檔 `git add`。

---

## 5. 踩過的坑（大致按嚴重度排序；編號是歷史標籤，不是順位）

### 陷阱一：CRLF 讓 manifest hash 全錯 🩸

repo 的 `.gitattributes` 設定 `*.json text eol=lf`，git 存的 blob 是 **LF**，CDN 服務的也是 LF。但 Windows 工作區的檔案常是 **CRLF**。

若拿工作區檔案算 md5 → 算出 CRLF 的值 → 與 LF blob 對不上 → **玩家載不進翻譯**。

```python
# 正確：算 hash 前先正規化
md5 = hashlib.md5(open(p,'rb').read().replace(b'\r\n', b'\n')).hexdigest()

# 驗證要用 blob，不是工作區檔
git show :path/to/file.json | md5
```

### 陷阱七：jsDelivr 餵舊檔，而 static 沒有驗證所以完全無聲 🩸

**repo 全綠 ≠ 玩家拿到。** 中間還有一層 CDN：

```
AbyssMod.cfg 的 CDN 直接填 cdn.jsdelivr.net/gh/...
  （raw.githubusercontent.com 那行是被註解掉的預設值，AbyssCdnRouter.dll 沒有參與）
  → jsDelivr 對「分支 ref」有快取（s-maxage=43200，最長 12 小時）
```

所以 `git push` 完、`update_manifest.py` 全對，玩家還是可能拿到**幾個 commit 前**的檔案。
兩種後果嚴重度差很多：

| 檔案 | 執行期有無 md5 驗證 | 陳舊時的下場 |
|---|---|---|
| `names`/`ui_texts`/`add-on`/`other` | **有** | 驗證失敗→退回本機舊快取，log 有 `Remote fetch failed` |
| `static` | **沒有** | **靜默**注入舊 bundle，log 只印 `Injected N m_* tables` |

`static` 那條是真正的殺手：畫面一片日文，卻沒有任何錯誤訊息。實際發生過一次
（推上去 26 分鐘後實機仍是日文，庫裡譯文與 manifest 都是對的）。
怎麼從 log 判讀玩家實際拿到哪一版，見第 6 節。

**處理順序**：

1. `python tools/verify_cdn.py --purge` —— 驗 raw 與 jsDelivr，順手清快取。
2. 清完還是舊的 → 那是 jsDelivr 自己那層「分支→commit」解析快取，**purge 清不到**
   （實測回 `finished`、`x-cache: MISS`，內容照樣舊）。最長 12 小時自己過期。
3. 要立刻生效 → 把 `AbyssMod.cfg` 的 CDN **釘在 commit SHA**，SHA 網址不吃分支快取。
   工具會直接印出可貼的網址。⚠️ 臨時手段，下次改版必須改回分支形式，
   忘記改回去就會**永遠**停在那個 commit（而且一樣沒有錯誤訊息）。

⚠️ **CDN 還沒追上時，不要為了補救再推一版資料。** manifest 一改，玩家可能拿到
「新 manifest ＋ 舊資料檔」或反過來「舊 manifest ＋ 新資料檔」——後者更糟：
mod 會拿舊 hash 去驗新檔案，於是**每個檔都驗證失敗**，全部退回舊快取。
先等 CDN 一致，再推下一版。

### 陷阱二：key 差一個字元，永遠命不中

差一個字元就完全失效，而且**在 repo 端完全看不出來**（key/value/JSON 都正常），
只有拿 dump 或官方原文逐字元比對才抓得到。踩過的四種差異：

| 庫裡的 key | 遊戲實際查的 | 差異 |
|---|---|---|
| `このままお話しを続けても…` | `このままお話を続けても…` | 多一個「し」 |
| `雪明り` | `月明り` | 雪/月 |
| `問題が……。` | `問題が……` | 多一個句號 |
| `討伐成功です！⏎やりましたね！` | `討伐成功です！\nやりましたね！` | 真換行 vs **字面** `\n` |

最後一項特別注意：**dump 的 JSON 值裡看到 `\\n`，那是字面的兩個字元（`0x5c 0x6e`），
不是換行**。比對時印字元碼確認，別憑外觀判斷。

**根治法**：拿得到官方原文就做全量 key diff，一次抓出所有錯字。

### 陷阱三：只寫 static 不夠 🔁

**已經踩了三次**（活動橫幅、災厄戰結算台名、關卡列表劇情標題）。

masterdata 有的資料放 `static` 是對的，但**同一個名稱若也會被 UI 元件當字串畫出來**，
那個畫面走 runtime fallback（ui_texts），static 注入對它無效 → 只寫 static 就顯示日文。

**判準**：這個名字會不會出現在 **關卡/劇情列表、播放確認框、活動橫幅、服裝/道具選擇框**？
會 → static 和 ui_texts 都要寫（譯文相同）；只在詳情面板顯示 → 可只放 static。
省事作法是**整張表鏡射進 ui_texts**，別等玩家逐條回報。

### 陷阱四：改譯名要連改組合 key

某名詞若已被用來預生成組合 key，改譯名時必須同步改所有含它的組合 key，
否則遊戲用新譯名組出的 key 會對不上。改名詞前先 grep 它在不在組合 key 裡。

### 陷阱五：全域替換會誤傷

修正譯名時**不要無條件全域替換**，要用「key 含該日文詞」當條件。
`ヒマリ` 誤譯「向日葵」要改成「葵」，但「如**向日葵**般燦爛的笑容」原文是
`ひまわり`（真的花），不能動。同理 `兇`（兇猛/元兇）不能因為要統一「凶化災厄」就全掃。

### 陷阱六：酒館色標靠對照表，不是 `<color>` 標籤

酒館提案描述的紫/綠字，是遊戲拿 `m_tavern_text_color`（詞→顏色對照表）比對描述文字
**自動上色**。所以描述譯文**不該自己加 `<color>`**，但**色標表的譯文必須與描述譯文
逐字相同**，否則對不上就不上色（靜默失效）。改酒館用詞時兩邊都要改。

> 這跟**紋章色標**相反——紋章的 `<color=#FF5050>紋章：情熱</color>` 是譯者刻意加的，
> 詳見 `AGENTS.md`。

---

## 6. 玩家回報「某處沒翻」的排查順序

**第 0 步永遠是：拿原文去庫裡搜一遍。** 這一步決定接下來走哪條路，兩條路完全不同：

- **庫裡沒有** → 是漏翻，往下走第 1～3 步（補字典）
- **庫裡有卻顯示日文** → 是**沒生效**，跳到第 4 步（查投遞管線）。
  這時候再怎麼看譯文都沒用，字是對的。

1. **查 dump** —— 有的話用它的精確位元組當 key（最可靠）
2. **dump 沒有 → 查 masterdata** —— 找出它屬於哪張表哪個欄位
3. **兩處都查無 → 是客戶端寫死的 UI 字串** —— 照截圖逐字轉錄，補進 `ui_texts`，請玩家實機確認
4. **庫裡明明有譯文卻顯示日文** → 別憑猜，**先讀實機的兩個檔**，它們會直接說出答案：

   | 檔案 | 看什麼 |
   |---|---|
   | `BepInEx/LogOutput.log` | `Remote fetch failed` / `Loaded stale cache` / `Translation loaded [X]. Total: N`（條數比 repo 少＝拿到舊檔）/ `Injected N m_* tables` |
   | `BepInEx/plugins/AbyssMod/dump/*_raw.json` | 遊戲實際查了哪個字串卻查不到（含**組合後**與**數值代入後**的形式） |

   再依序懷疑：

   - CDN 餵舊檔（陷阱七）—— `python tools/verify_cdn.py --purge` 一次驗完，**最常見**
   - key 差字元（陷阱二）
   - 只寫了 static（陷阱三）
   - manifest hash 沒更新（陷阱一）
   - 本地快取還沒更新（重開遊戲；mod 每次啟動都會重新比 hash）

---

## 7. 譯文風格與術語

全部在 **`translation_rules.md`**：台灣用語、標點、角色語氣、禁翻欄位，
以及「遊戲術語對照」表（厄災→災厄、会心→暴擊、マナ→魔力、浸食率→侵蝕率…）。

那張表原本這裡也放一份，兩邊會各自漂移，已整併過去。本檔只留流程與踩坑。

---

## 8. 給接手者的幾句話

- **先搞清楚自己在做哪條產線**（見開頭「兩條產線」）。劇情文本走 `It will be used to extract plot text/tools/`，UI／系統文字走本 repo 根的 `tools/`。兩條都做完才算一次完整更新。
- **這個專案最大的風險不是翻錯，是「翻了但沒生效」**——key 差一字、manifest 沒更新、寫錯檔案，都會讓翻譯靜默失效。第 4 節的驗證清單請每次都跑。
- **玩家截圖是最好的 QA**。庫裡看起來正常的東西，實機可能完全沒生效。
- **不確定就別猜**：dump 和 masterdata 是兩個 ground truth，查得到就別憑截圖轉錄。
- 歷次踩坑的細節都寫在 git commit message 裡，遇到怪問題可以 `git log --grep` 搜搜看。
