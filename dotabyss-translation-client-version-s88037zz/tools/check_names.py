#!/usr/bin/env python3
"""檢查 names/zh_Hant.json 的正式譯名在全庫（含劇情）是否被一致使用。

用法（在 client-version 資料夾根目錄執行）：
    python tools/check_names.py                    # 全掃，有短缺就 exit 1
    python tools/check_names.py --name ソフィア     # 只看單一日文詞
    python tools/check_names.py --min 2            # 只列短缺 >=2 次的譯名（過濾零星個案）
    python tools/check_names.py --examples 5       # 每個譯名列幾個例子
    python tools/check_names.py --repo <路徑>       # 指定 client-version 資料夾

掃描：static / ui_texts / names / add-on / other / novels / novels_untranslated_only

## 原理

日文 key 裡某個譯名出現 N 次，中文 value 裡對應的正式譯名就該出現 N 次。
少了就代表：要嘛用了別的譯法（`索菲亞` 寫成 `蘇菲亞`），要嘛整個省略掉。

    JP 出現 2 次 / ZH 出現 2 次  → 通過
    JP 出現 2 次 / ZH 出現 1 次  → 短缺 1
    JP 出現 1 次 / ZH 出現 0 次  → 短缺 1

中文比日文多不算問題——日文常省略主詞，中文得補回來。

## 唯一的防呆：片假名邊界

`シュリ` 會被 `アシュリー` 包含，不擋的話光這一個就灌進 215 筆假數字。
所以比對到的位置，前後不能還是片假名或長音符。
另外 `モンスター` 與 `モンスターたち` 都在表裡，同一處只認最長的那個。

## 短缺不等於錯

大量短缺是正當翻譯——日文寫名字、中文改用代名詞：

    JP  ヒマリの武器の威力ならば１発で仕留められるはずだ。
    ZH  以你武器的威力，一發就能幹掉它。

所以這是**人工複查清單**，不是硬性關卡。判讀方式：
短缺集中在少數幾條 → 多半是譯名寫錯；短缺遍布大量條目 → 多半是代名詞替換。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

KATAKANA = re.compile(r"[ァ-ヴーｱ-ﾝ]")


def looks_like_repo(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "names", "zh_Hant.json")) and            os.path.isdir(os.path.join(path, "novels"))


def find_repo(explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    # 本腳本位於 <client-version>/tools/，repo 根固定是上一層
    # （與 update_manifest.py / verify_cdn.py 的 parents[1] 一致）
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if looks_like_repo(root):
        return root
    # 後備：腳本被搬到別處時，從所在位置往下找
    here = os.path.dirname(os.path.abspath(__file__))
    for base, _dirs, _files in os.walk(here):
        if looks_like_repo(base):
            return base
    sys.exit("找不到 client-version 資料夾（要有 names/zh_Hant.json 與 novels/），請用 --repo 指定。")


def load_corpus(repo: str) -> list[tuple[str, str, str]]:
    """回傳 [(來源標籤, 日文 key, 中文 value), ...]"""
    out: list[tuple[str, str, str]] = []

    def add(tag, d):
        for k, v in d.items():
            if isinstance(v, str) and v:
                out.append((tag, k, v))

    p = os.path.join(repo, "static", "zh_Hant.json")
    if os.path.isfile(p):
        for table, fields in json.load(open(p, encoding="utf-8")).items():
            if isinstance(fields, dict):
                for field, kv in fields.items():
                    if isinstance(kv, dict):
                        add(f"static:{table}/{field}", kv)

    for rel, tag in (("ui_texts", "ui_texts"), ("names", "names")):
        p = os.path.join(repo, rel, "zh_Hant.json")
        if os.path.isfile(p):
            add(tag, json.load(open(p, encoding="utf-8")))

    for parent in ("add-on", "other"):
        base = os.path.join(repo, parent)
        if os.path.isdir(base):
            for sub in sorted(os.listdir(base)):
                p = os.path.join(base, sub, "zh_Hant.json")
                if os.path.isfile(p):
                    add(f"{parent}/{sub}", json.load(open(p, encoding="utf-8")))

    for src in ("novels", "novels_untranslated_only"):
        base = os.path.join(repo, src)
        if os.path.isdir(base):
            for folder in sorted(os.listdir(base)):
                p = os.path.join(base, folder, "zh_Hant.json")
                if os.path.isfile(p):
                    add(f"{src}/{folder}", json.load(open(p, encoding="utf-8")))

    return out


def count_standalone(text: str, needle: str) -> int:
    """needle 在 text 裡出現幾次，但前後是片假名的不算（シュリ ⊄ アシュリー）。"""
    n = start = 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return n
        before = text[i - 1] if i > 0 else " "
        after = text[i + len(needle)] if i + len(needle) < len(text) else " "
        if not KATAKANA.match(before) and not KATAKANA.match(after):
            n += 1
        start = i + len(needle)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo")
    ap.add_argument("--name", help="只檢查這一個日文詞")
    ap.add_argument("--min", type=int, default=1, help="只列短缺次數 >= 此值的譯名")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    repo = find_repo(args.repo)
    names = json.load(open(os.path.join(repo, "names", "zh_Hant.json"), encoding="utf-8"))
    corpus = load_corpus(repo)
    print(f"repo   : {repo}")
    print(f"譯名表 : {len(names)} 條")
    print(f"語料   : {len(corpus)} 條\n")

    targets = {k: v for k, v in names.items() if v and k != v and len(k) >= 2}
    if args.name:
        targets = {k: v for k, v in targets.items() if k == args.name}
        if not targets:
            print(f"譯名表裡沒有「{args.name}」（或它被排除：中日同形／太短）")
            return 2
    # 最長優先：モンスターたち 命中後就不再算 モンスター
    order = sorted(targets, key=len, reverse=True)

    jp_total: dict[str, int] = defaultdict(int)
    zh_total: dict[str, int] = defaultdict(int)
    short_hits: dict[str, int] = defaultdict(int)      # 有短缺的條目數
    short_amount: dict[str, int] = defaultdict(int)    # 短缺總次數
    examples: dict[str, list] = defaultdict(list)

    for tag, jp_key, zh_val in corpus:
        claimed: list[str] = []
        for jp in order:
            n_jp = count_standalone(jp_key, jp)
            if not n_jp:
                continue
            if any(jp in c for c in claimed):   # 已被更長的詞涵蓋
                continue
            claimed.append(jp)
            n_zh = zh_val.count(targets[jp])
            jp_total[jp] += n_jp
            zh_total[jp] += min(n_zh, n_jp)
            if n_zh < n_jp:
                short_hits[jp] += 1
                short_amount[jp] += n_jp - n_zh
                if len(examples[jp]) < args.examples:
                    examples[jp].append((tag, jp_key, zh_val, n_jp, n_zh))

    listed = [jp for jp in short_amount if short_amount[jp] >= args.min]
    listed.sort(key=lambda j: -short_amount[j])

    print("=" * 74)
    print(f"■ 譯名短缺：{len(short_amount)} 個譯名（列出短缺 >= {args.min} 次的 {len(listed)} 個）")
    print(f"  總計 日文出現 {sum(jp_total.values())} 次，中文對上 {sum(zh_total.values())} 次，"
          f"短缺 {sum(short_amount.values())} 次")
    print("=" * 74)
    if not listed:
        print("（無）")
    for jp in listed:
        rate = short_amount[jp] / jp_total[jp]
        print(f"\n{jp} → 「{targets[jp]}」")
        print(f"   日文 {jp_total[jp]} 次 / 中文對上 {zh_total[jp]} 次 / "
              f"短缺 {short_amount[jp]} 次（{rate:.0%}），涉及 {short_hits[jp]} 個條目")
        for tag, k, v, n_jp, n_zh in examples[jp]:
            print(f"   [{tag}]  JP×{n_jp} ZH×{n_zh}")
            print(f"     JP {k[:78]}")
            print(f"     ZH {v[:78]}")

    return 1 if short_amount else 0


if __name__ == "__main__":
    sys.exit(main())
