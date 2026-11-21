#!/usr/bin/env python3
"""照前例預填 待翻譯.json：只差數字或人名的句子，直接套用既有譯文。

改版時大量新字串只是舊句換了數字（能力等級、任務目標）或換了角色名。
這支把原文的數字換成 #、已知人名換成 §，跟 repo 裡所有既有 key 比對；
命中且譯文裡找得到對應的舊數字／舊人名，才代換成新的，否則留空給人翻。

  python tools/prefill_from_precedent.py --input <missing>/待翻譯.json --output <暫存>/prefill.json
  python tools/prefill_from_precedent.py ... --name アンリ=安莉 --name レイヴン=雷文   # 新角色名（先問過）

輸出格式與 待翻譯.json 相同，填過的帶值、沒把握的留空；只寫 --output，不動 repo。
接著照常 merge_translated.py --dry-run 看「可疑」清單。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["static/zh_Hant.json", "names/**/zh_Hant.json", "ui_texts/zh_Hant.json",
           "add-on/**/zh_Hant.json", "other/**/zh_Hant.json"]
NUM = re.compile(r"\d+(?:\.\d+)?")
KATA = re.compile(r"[ァ-ヴー・]{2,}")


def load_known() -> dict[str, str]:
    kv: dict[str, str] = {}

    def walk(o):
        for k, v in o.items():
            if isinstance(v, str):
                if v and k not in kv:
                    kv[k] = v
            elif isinstance(v, dict):
                walk(v)

    for pat in SOURCES:
        for p in sorted(glob.glob(str(ROOT / pat), recursive=True)):
            walk(json.loads(Path(p).read_text(encoding="utf-8-sig")))
    return kv


def substitute(old_tokens, new_tokens, value, table):
    """把 value 裡的舊 token 依序換成新的；舊 token 在 value 找不到就放棄。"""
    out, pos = [], 0
    for a, b in zip(old_tokens, new_tokens):
        ta, tb = table(a), table(b)
        i = value.find(ta, pos)
        if i < 0:
            return None
        out.append(value[pos:i] + tb)
        pos = i + len(ta)
    return "".join(out) + value[pos:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--name", action="append", default=[], metavar="日文=中文",
                    help="補充人名對照（names/ 還沒有的新角色）")
    a = ap.parse_args()

    kv = load_known()
    names = {k: v for k, v in kv.items() if KATA.fullmatch(k)}
    for item in a.name:
        k, v = item.split("=", 1)
        names[k] = v
    name_re = re.compile("|".join(sorted(map(re.escape, names), key=len, reverse=True))) if names else None

    def norm(s):
        if name_re:
            s = name_re.sub("§", s)
        return NUM.sub("#", s)

    idx: dict[str, str] = {}
    for k in kv:
        idx.setdefault(norm(k), k)

    data = json.loads(a.input.read_text(encoding="utf-8-sig"))
    filled = total = 0
    for fields in data.values():
        for entries in fields.values():
            for k, v in entries.items():
                if v:
                    continue
                total += 1
                ok = idx.get(norm(k))
                if ok is None:
                    continue
                r = kv[ok]
                if name_re:
                    on, nn = name_re.findall(ok), name_re.findall(k)
                    if on != nn:
                        r = substitute(on, nn, r, lambda x: names[x])
                        if r is None:
                            continue
                od, nd = NUM.findall(ok), NUM.findall(k)
                if od != nd:
                    if NUM.findall(r) != od:   # 譯文數字順序與原文不同，不猜
                        continue
                    r = substitute(od, nd, r, lambda x: x)
                if r is None or k.count("\n") != r.count("\n"):
                    continue
                entries[k] = r
                filled += 1

    a.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"照前例填了 {filled} / {total}，其餘留空 → {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
