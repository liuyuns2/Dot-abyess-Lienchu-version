#!/usr/bin/env python3
"""預生成「組合式再查詢 key」，補上官方更新新角色/新劇情後的漏翻。

## 為什麼需要這支

AbyssMod 有些畫面不是整句查字典，而是**先翻片段、組成完整句子、再拿整句查一次**。
例如劇情播放確認框：

    遊戲原句： 「見つめ合いながら」<br>を再生します。よろしいですか？
    mod 先翻標題 → 「四目相對」
    mod 組成    → 「四目相對」<br>を再生します。よろしいですか？
    mod 再查這整句 ← 字典裡沒有的話，後半句就維持日文

所以字典必須**預先存好每個標題的完整組合句**。官方一更新、新角色帶來新劇情標題，
就會多出一批沒有組合 key 的句子，畫面上呈現「標題翻了、後半句沒翻」的半殘狀態
（2026-07-19 使用者截圖回報，當時 339 個標題有 28 個漏網）。

這支腳本以**譯名表為單一真實來源**重新生成全部組合 key，所以只要譯名表有的標題，
組合 key 一定齊。新角色上線後跑一次即可，不需要人工比對。

## 用法

    python3 tools/build_combo_keys.py            # 補齊缺的並更新 manifest
    python3 tools/build_combo_keys.py --check    # 只檢查不寫檔（有缺口時 exit 1，可用於 CI）

## 要新增一種模板時

在下面 RULES 加一筆即可。key/value 模板各留一個 {} 當填充位，
source 指向「提供填充物的譯名表」。

## 兩種填充物來源

- `static`：譯名表本身就是來源（如劇情標題，日文 -> 中文，取中文側）。
- `masterdata`：**維持原文**的名字（能力名等）不在譯名表裡，得從 masterdata 撈
  日文原名當填充物。masterdata 路徑見 MASTERDATA_DIR，不在 repo 內，
  故該族規則在找不到 masterdata 時會自動略過（只警告、不中斷）。

## ⚠️ 能力名這族為什麼填日文

技能/能力名依「維持原文」政策已從 static 整表移除
（m_character_abilities / m_character_action_skills / m_gacha_group_movies），
所以 mod 翻不到名字、組出來的是**日文原名**。組合 key 必須跟著填日文原名。

2026-07-19 稽核發現：庫裡 141 條這族組合有 131 條是政策改變前用**中文名**
組成的死 key（永遠對不上），而 masterdata 的 151 個能力只有 8 個有可用的
組合 key——還是因為漢字名中日同字而巧合對上的。故本腳本會**一併清掉死 key**
（--prune，預設開啟）。詳見記憶 term-standard-and-consistency /
skill-names-keep-original。
"""
import hashlib
import json
import os
import sys

LANG = "zh_Hant"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_PATH = os.path.join(ROOT, "static", LANG + ".json")
UI_PATH = os.path.join(ROOT, "ui_texts", LANG + ".json")
MANIFEST_PATH = os.path.join(ROOT, "manifest", LANG + ".json")

# masterdata 不在 repo 內（使用者本機另外抓的官方資料）
MASTERDATA_DIR = os.environ.get(
    "DOTABYSS_MASTERDATA", r"D:\dotabyss-translation\Masterdata-main\data"
)

# 各檔案的縮排（沿用現況，避免整檔 diff）
INDENT = {STATIC_PATH: 2, UI_PATH: 4}


RULES = [
    {
        "name": "劇情播放確認框",
        # static 來源：取譯名表 (table, field) 的「中文側」當填充物
        "source": ("static", "m_novel_characters", "title"),
        "key_tmpl": "「{}」<br>を再生します。よろしいですか？",
        "value_tmpl": "「{}」<br>即將播放。確定嗎？",
    },
    {
        "name": "能力最大Lv提升",
        # masterdata 來源：取 (檔名, 欄位) 的日文原名當填充物
        #   ——能力名維持原文，故 key 與 value 都填日文，value 保留「」把日文框住
        "source": ("masterdata", "m_character_abilities.json", "name"),
        "key_tmpl": "「{}」の最大Lvが{{0}}に上昇！",
        "value_tmpl": "「{}」的最大等級提高到{{0}}！",
        # 清掉「符合本模板、但填充物不在來源清單」的死 key
        "prune": True,
        # value 完全機械式套模板，故既有條目若寫法不同就一併校正
        #   （劇情標題那族不設此旗標——那些 value 含人工譯文，不可覆蓋）
        "canonical": True,
    },
]

# 組合 key 要寫進哪些地方（雙檔 fallback：不同畫面讀不同檔）
#   ui_texts 是扁平字典；static 放在 m_texts/ja 這張表底下
TARGETS = ["ui_texts", "static:m_texts/ja"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=INDENT[path]) + "\n"
    # 一律 LF —— .gitattributes 對 *.json 設了 eol=lf，manifest 的 md5 也是按 LF 算
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def file_md5(path):
    """檔案 md5，以 LF 內容計算（與 git 存進 blob 的內容一致）。"""
    with open(path, "rb") as f:
        return hashlib.md5(f.read().replace(b"\r\n", b"\n")).hexdigest()


def get_target_dict(name, static, ui):
    """把 TARGETS 的字串解析成可寫入的 dict。"""
    if name == "ui_texts":
        return ui
    if name.startswith("static:"):
        table, field = name.split(":", 1)[1].split("/")
        return static.setdefault(table, {}).setdefault(field, {})
    raise ValueError(f"未知的 target：{name}")


def get_fillers(rule, static):
    """依 rule["source"] 取出填充物清單。回傳 None 代表來源不可用、該規則應略過。"""
    kind = rule["source"][0]

    if kind == "static":
        _, table, field = rule["source"]
        pairs = static.get(table, {}).get(field)
        if not pairs:
            print(f"  [warn] 找不到譯名表 {table}/{field}，略過「{rule['name']}」", file=sys.stderr)
            return None
        # 只取「有中文譯文」的；譯文等於原文＝刻意維持原文（如二つ名），不生成
        return sorted({zh for ja, zh in pairs.items() if zh and zh != ja})

    if kind == "masterdata":
        _, filename, field = rule["source"]
        path = os.path.join(MASTERDATA_DIR, filename)
        if not os.path.isfile(path):
            print(
                f"  [warn] 找不到 masterdata {path}，略過「{rule['name']}」"
                f"（可用環境變數 DOTABYSS_MASTERDATA 指定目錄）",
                file=sys.stderr,
            )
            return None
        rows = load(path)
        return sorted({r[field] for r in rows if r.get(field)})

    raise ValueError(f"未知的 source 類型：{kind}")


def find_stale(rule, target, fillers):
    """找出「符合本模板、但填充物不在來源清單」的死 key。"""
    prefix, suffix = rule["key_tmpl"].split("{}", 1)
    suffix = suffix.replace("{{", "{").replace("}}", "}")
    valid = {rule["key_tmpl"].format(z) for z in fillers}
    return [
        k
        for k in target
        if k.startswith(prefix) and k.endswith(suffix) and k not in valid
    ]


def main():
    check_only = "--check" in sys.argv

    static = load(STATIC_PATH)
    ui = load(UI_PATH)

    missing_total = stale_total = 0
    added_total = pruned_total = fixed_total = 0

    for rule in RULES:
        fillers = get_fillers(rule, static)
        if fillers is None:
            continue

        for target_name in TARGETS:
            target = get_target_dict(target_name, static, ui)
            missing = [z for z in fillers if rule["key_tmpl"].format(z) not in target]
            stale = find_stale(rule, target, fillers) if rule.get("prune") else []
            # 既有但 value 寫法與模板不符者（僅限 value 純機械式的規則）
            offstyle = (
                [
                    z
                    for z in fillers
                    if rule["key_tmpl"].format(z) in target
                    and target[rule["key_tmpl"].format(z)] != rule["value_tmpl"].format(z)
                ]
                if rule.get("canonical")
                else []
            )
            missing_total += len(missing)
            stale_total += len(stale) + len(offstyle)

            if not check_only:
                for z in missing + offstyle:
                    target[rule["key_tmpl"].format(z)] = rule["value_tmpl"].format(z)
                for k in stale:
                    del target[k]
                added_total += len(missing)
                pruned_total += len(stale)
                fixed_total += len(offstyle)

            verb = "缺" if check_only else "補上"
            line = f"{rule['name']} → {target_name}: 來源 {len(fillers)} 條，{verb} {len(missing)} 條"
            if rule.get("prune"):
                line += f"，死 key {len(stale)} 條"
            if offstyle:
                line += f"，校正寫法 {len(offstyle)} 條"
            print(line)
            for z in missing[:5]:
                print(f"    + {z}")
            if len(missing) > 5:
                print(f"    …另外 {len(missing) - 5} 條")
            for k in stale[:5]:
                print(f"    - {k}")
            if len(stale) > 5:
                print(f"    …另外 {len(stale) - 5} 條死 key")

    if check_only:
        if missing_total or stale_total:
            print(f"\n共缺 {missing_total} 條、死 key {stale_total} 條。跑一次不帶 --check 即可處理。")
            return 1
        print("\n組合 key 齊全，無缺口、無死 key。")
        return 0

    if not (added_total or pruned_total or fixed_total):
        print("\n組合 key 已齊全，未變更任何檔案。")
        return 0

    save(STATIC_PATH, static)
    save(UI_PATH, ui)

    # 更新 manifest：各檔 md5 + 整體 hash（＝去掉 hash 欄位後的最小化 JSON 的 md5）
    manifest = load(MANIFEST_PATH)
    manifest["static"] = file_md5(STATIC_PATH)
    manifest["ui_texts"] = file_md5(UI_PATH)
    manifest.pop("hash", None)
    minified = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    manifest["hash"] = hashlib.md5(minified.encode("utf-8")).hexdigest()
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"\n共補 {added_total} 條、刪死 key {pruned_total} 條、校正寫法 {fixed_total} 條，"
        f"已更新 static / ui_texts / manifest。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
