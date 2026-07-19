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

## ⚠️ 已知無法自動化的一族（勿手癢加進 RULES）

`「{技能名}」の最大Lvが{0}に上昇！` 這族目前庫裡有 141 條、但**全是死 key**：
它們用中文技能名組成，然而技能名依「維持原文」政策已從 static 整表移除
（m_character_abilities / m_character_action_skills / m_gacha_group_movies），
遊戲實際組出來的是**日文原名**，對不上。要修得先從 dump/masterdata 取回
日文技能名清單，repo 內沒有來源，故不放進 RULES。詳見記憶
term-standard-and-consistency / skill-names-keep-original。
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

# 各檔案的縮排（沿用現況，避免整檔 diff）
INDENT = {STATIC_PATH: 2, UI_PATH: 4}


RULES = [
    {
        "name": "劇情播放確認框",
        # 填充物來源：static 的 (table, field)，取其「日文 -> 中文」的中文側
        "source": ("m_novel_characters", "title"),
        "key_tmpl": "「{}」<br>を再生します。よろしいですか？",
        "value_tmpl": "「{}」<br>即將播放。確定嗎？",
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


def main():
    check_only = "--check" in sys.argv

    static = load(STATIC_PATH)
    ui = load(UI_PATH)

    missing_total = 0
    added_total = 0

    for rule in RULES:
        table, field = rule["source"]
        pairs = static.get(table, {}).get(field)
        if not pairs:
            print(f"  [warn] 找不到來源表 {table}/{field}，略過「{rule['name']}」", file=sys.stderr)
            continue

        # 只取「有中文譯文」的條目；譯文等於原文＝刻意維持原文（如二つ名），不生成
        fillers = [zh for ja, zh in pairs.items() if zh and zh != ja]

        for target_name in TARGETS:
            target = get_target_dict(target_name, static, ui)
            missing = [
                z for z in fillers if rule["key_tmpl"].format(z) not in target
            ]
            missing_total += len(missing)
            if missing and not check_only:
                for z in missing:
                    target[rule["key_tmpl"].format(z)] = rule["value_tmpl"].format(z)
                added_total += len(missing)
            status = "缺" if check_only else "補上"
            print(
                f"{rule['name']} → {target_name}: 來源 {len(fillers)} 條，"
                f"{status} {len(missing)} 條"
            )
            for z in missing[:10]:
                print(f"    - {z}")
            if len(missing) > 10:
                print(f"    …另外 {len(missing) - 10} 條")

    if check_only:
        if missing_total:
            print(f"\n共缺 {missing_total} 條組合 key。跑一次不帶 --check 即可補齊。")
            return 1
        print("\n組合 key 齊全，無缺口。")
        return 0

    if not added_total:
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

    print(f"\n共補 {added_total} 條，已更新 static / ui_texts / manifest。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
