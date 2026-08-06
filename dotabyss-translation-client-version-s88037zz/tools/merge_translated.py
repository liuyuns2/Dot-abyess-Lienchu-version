#!/usr/bin/env python3
"""把翻好的 `待翻譯.json` 合併回 `static/zh_Hant.json`。

`待翻譯.json` 由 tools/extract_masterdata_missing.py 產生，結構刻意做成與
`static/zh_Hant.json` 完全一致（`{資料表: {欄位: {原文: 譯文}}}`），所以合併
就是一次深層 merge。但有三件事不能交給人記：

1. **禁翻欄位**：技能名／能力名維持原文是既定政策。
   `extract_masterdata_missing.py` 只支援資料表層級排除，擋不掉
   `m_gacha_group_movies/skill_name` 這種欄位層級的，每次都會列進待翻譯。
2. **不覆蓋既有譯文**：同一個 `表+欄位+原文` 已經有譯文時一律跳過並回報，
   避免一次批次合併默默改掉先前校對過的句子。要覆蓋得明確加 --allow-overwrite。
3. **不重排**：`static/zh_Hant.json` 的表名／欄位／原文都是插入序而非字典序，
   重排會讓 diff 從數十行變成數萬行，沒人審得動。新條目一律追加在原位置之後。

合併後**務必再跑 tools/update_manifest.py**，否則 md5 對不上，玩家拿到的
還是舊翻譯，而且不會有任何錯誤訊息。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "static" / "zh_Hant.json"

# 整張表禁翻（與 AGENTS.md 一致）
FORBIDDEN_TABLES = {
    "m_character_abilities",
    "m_character_action_skills",
}

# 單一欄位禁翻：extract_masterdata_missing.py 擋不掉這層，只能在這裡攔
FORBIDDEN_FIELDS = {
    ("m_gacha_group_movies", "skill_name"),
}

KANA_RE = re.compile(r"[぀-ゟ゠-ヿ]")
TAG_RE = re.compile(r"<[^>]+>")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=OrderedDict)


def write_json(path: Path, data: Any) -> None:
    # 與 update_manifest.py 的 hash 計算前提一致：一律 LF，結尾補換行
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def is_forbidden(table: str, field: str) -> bool:
    return table in FORBIDDEN_TABLES or (table, field) in FORBIDDEN_FIELDS


def inspect(source: str, translated: str) -> list[str]:
    """回報可疑但不阻斷的問題。"""
    notes: list[str] = []
    if translated == source:
        notes.append("譯文與原文完全相同")
    if KANA_RE.search(translated):
        notes.append("譯文殘留假名")
    if Counter(TAG_RE.findall(source)) != Counter(TAG_RE.findall(translated)):
        notes.append("標籤與原文不一致")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把填好的 待翻譯.json 合併回 static/zh_Hant.json"
    )
    parser.add_argument("--input", type=Path, required=True, help="填好的 待翻譯.json")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只印報告不寫檔（建議每次先跑一次）",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="允許覆蓋既有譯文；預設一律跳過並回報",
    )
    parser.add_argument(
        "--exclude-field",
        action="append",
        default=[],
        metavar="表/欄位",
        help="額外禁翻欄位，可重複",
    )
    args = parser.parse_args()

    for item in args.exclude_field:
        if "/" not in item:
            parser.error(f"--exclude-field 需為 表/欄位 格式：{item}")
        table, field = item.split("/", 1)
        FORBIDDEN_FIELDS.add((table, field))

    incoming = load_json(args.input)
    target = load_json(args.target)

    merged: list[tuple[str, str, str]] = []
    overwritten: list[tuple[str, str, str, str, str]] = []
    conflicts: list[tuple[str, str, str, str, str]] = []
    skipped_forbidden: list[tuple[str, str, str]] = []
    skipped_empty: list[tuple[str, str, str]] = []
    identical: list[tuple[str, str, str]] = []
    warnings: list[tuple[str, str, str, str]] = []

    for table, fields in incoming.items():
        if not isinstance(fields, dict):
            continue
        for field, entries in fields.items():
            if not isinstance(entries, dict):
                continue
            for source, translated in entries.items():
                if not isinstance(translated, str):
                    continue

                if is_forbidden(table, field):
                    skipped_forbidden.append((table, field, source))
                    continue
                if not translated.strip():
                    skipped_empty.append((table, field, source))
                    continue

                existing = target.get(table, {}).get(field, {}).get(source)
                if existing is not None:
                    if existing == translated:
                        identical.append((table, field, source))
                        continue
                    if not args.allow_overwrite:
                        conflicts.append((table, field, source, existing, translated))
                        continue
                    overwritten.append((table, field, source, existing, translated))
                else:
                    merged.append((table, field, source))

                for note in inspect(source, translated):
                    warnings.append((table, field, source, note))

                target.setdefault(table, OrderedDict()).setdefault(field, OrderedDict())[source] = translated

    def dump(title: str, rows: list, formatter, limit: int = 20) -> None:
        if not rows:
            return
        print(f"\n{title}（{len(rows)}）")
        for row in rows[:limit]:
            print(formatter(row))
        if len(rows) > limit:
            print(f"  …另有 {len(rows) - limit} 筆")

    print("=" * 60)
    print(f"來源：{args.input}")
    print(f"目標：{args.target}")
    print("=" * 60)
    print(f"新增譯文        {len(merged)}")
    print(f"已存在且相同    {len(identical)}")
    print(f"尚未填寫        {len(skipped_empty)}")
    print(f"禁翻欄位跳過    {len(skipped_forbidden)}")
    print(f"衝突未寫入      {len(conflicts)}" if not args.allow_overwrite
          else f"覆蓋既有譯文    {len(overwritten)}")

    dump("── 禁翻欄位（政策要求維持原文）", skipped_forbidden,
         lambda r: f"  {r[0]}/{r[1]}  {r[2][:40]}")
    dump("── 衝突：既有譯文不同，已跳過", conflicts,
         lambda r: f"  {r[0]}/{r[1]}\n    原文 {r[2][:50]}\n    既有 {r[3][:50]}\n    新的 {r[4][:50]}")
    dump("── 已覆蓋", overwritten,
         lambda r: f"  {r[0]}/{r[1]}\n    舊 {r[3][:50]}\n    新 {r[4][:50]}")
    dump("── 尚未填寫（留在 待翻譯.json 裡繼續翻）", skipped_empty,
         lambda r: f"  {r[0]}/{r[1]}  {r[2][:40]}")
    dump("── 可疑，請人工確認", warnings,
         lambda r: f"  [{r[3]}] {r[0]}/{r[1]}  {r[2][:40]}")

    if conflicts and not args.allow_overwrite:
        print("\n衝突條目未寫入。確認新譯文較佳後，用 --allow-overwrite 重跑。")

    if args.dry_run:
        print("\n--dry-run：未寫入任何檔案。")
        return 0

    if not merged and not overwritten:
        print("\n沒有任何條目需要寫入，目標檔未變動。")
        return 0

    write_json(args.target, target)
    print(f"\n已寫入 {args.target}")
    print("下一步：python tools/update_manifest.py（漏了的話玩家拿到的還是舊翻譯）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
