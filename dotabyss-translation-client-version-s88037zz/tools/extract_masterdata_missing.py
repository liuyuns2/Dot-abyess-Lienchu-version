from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSLATION_GLOBS = (
    "static/zh_Hant.json",
    "ui_texts/zh_Hant.json",
    "names/zh_Hant.json",
    "add-on/**/zh_Hant.json",
    "other/**/zh_Hant.json",
)

# NG 詞庫是給敏感詞過濾用的，翻了會直接壞掉，整張表永久排除。
DEFAULT_EXCLUDED_TABLES = {
    "m_ng_words",
}

# 政策禁翻的是「欄位」不是「整張表」。原本這裡排除 m_character_abilities /
# m_character_action_skills 兩張整表，結果連 description 一起被吞掉——
# 主動技能說明從此再也沒被抽出過，新角色上線就是一片日文（2026-08 實際踩到）。
DEFAULT_EXCLUDED_FIELDS = {
    ("m_character_abilities", "name"),
    ("m_character_action_skills", "name"),
    ("m_gacha_group_movies", "skill_name"),
}


HAS_JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龥]")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def translation_files(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in TRANSLATION_GLOBS:
        paths.update(root.glob(pattern))
    return sorted(paths)


def collect_coverage(
    root: Path,
) -> tuple[set[tuple[str, str, str]], set[tuple[str, str]], dict[str, str], list[Path]]:
    """掃現有翻譯檔，回傳 (精確鍵, 已知欄位, 全庫已譯原文→譯文, 掃到的檔案)。

    兩種結構都要吃：
      - `static` 是 表 → 欄位 → {原文: 譯文}
      - `ui_texts` / `names` 是扁平的 {原文: 譯文}
    扁平檔以前整個被 `isinstance(fields, dict)` 擋掉，等於完全沒納入覆蓋判斷；
    只翻在 ui_texts 的字串會被誤判成「沒翻過」。

    值為空字串的條目不算已譯——它是待翻譯的佔位，不是覆蓋。
    """
    exact: set[tuple[str, str, str]] = set()
    known_fields: set[tuple[str, str]] = set()
    global_keys: dict[str, str] = {}
    files = translation_files(root)
    for path in files:
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        for table, fields in data.items():
            if not isinstance(fields, dict):
                # 扁平檔：table 其實是原文、fields 是譯文
                if isinstance(fields, str) and fields:
                    global_keys.setdefault(str(table), fields)
                continue
            for field, entries in fields.items():
                if not isinstance(entries, dict):
                    continue
                known_fields.add((str(table), str(field)))
                for source, translated in entries.items():
                    if isinstance(source, str) and translated:
                        exact.add((str(table), str(field), source))
                        global_keys.setdefault(source, translated)
    return exact, known_fields, global_keys, files


def resolve_masterdata(raw: Path) -> Path:
    """把 --master 正規化成「真正放 m_*.json 的那一層」。

    本工具歷來要求指到「含 data/ 的上一層」，而 tools/build_combo_keys.py 的
    masterdata 路徑歷來直接指到 data/。兩邊約定相反、指錯又都不會中止，
    是實際踩過的坑：指錯這裡會掃出 0 筆，然後給你一份「沒有缺漏」的空報告。

    改為兩種寫法都接受：若 <raw>/data 底下有 m_*.json 就用它，否則用 <raw> 本身。
    """
    raw = raw.expanduser().resolve()
    nested = raw / "data"
    if any(nested.glob("m_*.json")):
        return nested
    return raw


def record_id(row: dict[str, Any], index: int) -> str:
    for key in ("id", "key", "code", "asset_id"):
        if key in row:
            return str(row[key])
    return f"row:{index}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--exclude-table",
        action="append",
        default=[],
        help="Additional Masterdata table name to omit (repeatable)",
    )
    parser.add_argument(
        "--exclude-field",
        action="append",
        default=[],
        metavar="TABLE/FIELD",
        help="Additional Masterdata table/field to omit (repeatable)",
    )
    args = parser.parse_args()

    current = args.current.resolve()
    master_data = resolve_masterdata(args.master)
    output = args.output.resolve()
    if not any(master_data.glob("m_*.json")):
        raise SystemExit(
            f"找不到 masterdata 資料表：{master_data}\n"
            f"--master 請指到 masterdata 目錄（含 data/ 的那層或 data/ 本身都可以）。"
        )
    excluded_tables = DEFAULT_EXCLUDED_TABLES | set(args.exclude_table)
    excluded_fields = set(DEFAULT_EXCLUDED_FIELDS)
    for item in args.exclude_field:
        table_name, _, field_name = item.partition("/")
        if not table_name or not field_name:
            raise SystemExit(f"--exclude-field 要寫成 TABLE/FIELD，收到：{item}")
        excluded_fields.add((table_name, field_name))
    exact, known_fields, global_keys, source_files = collect_coverage(current)

    pending: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    occurrences: list[dict[str, Any]] = []
    # 「未知欄位」＝該 (表, 欄位) 在現有翻譯裡從未出現過，所以被跳過。
    # 這是本工具的結構性盲區：官方新增整張表或啟用新欄位時它會安靜地漏掉，
    # 只在報告寫一句「沒有缺漏」。這裡把含日文又全庫沒譯過的部分留下來，
    # 讓它至少變成一份看得見的清單。
    unknown_fields: dict[tuple[str, str], set[str]] = defaultdict(set)
    # 原文已在別的表／欄位翻過，只是這個位置沒有。不需要重翻。
    same_text_other_field: dict[tuple[str, str], set[str]] = defaultdict(set)
    scanned = Counter()
    invalid: list[str] = []

    for path in sorted(master_data.glob("*.json")):
        try:
            rows = load_json(path)
        except Exception as exc:
            invalid.append(f"{path.name}: {exc}")
            continue
        if not isinstance(rows, list):
            continue
        table = path.stem
        if table in excluded_tables:
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            for field, value in row.items():
                if not isinstance(value, str) or value == "":
                    continue
                if (table, str(field)) in excluded_fields:
                    continue
                if (table, str(field)) not in known_fields:
                    if HAS_JAPANESE.search(value) and value not in global_keys:
                        unknown_fields[(table, str(field))].add(value)
                    continue
                scanned["strings"] += 1
                if (table, str(field), value) in exact:
                    scanned["exact_existing"] += 1
                    continue
                # 外掛實測是「只比對原文、不看欄位」（使用者在遊戲內以 4 筆放錯
                # 表的條目驗證過，全部照樣顯示中文）。所以同一句原文全庫只能有
                # 一種譯文；把「同文異欄位」丟進待翻譯等於邀請別人生第二種，
                # 而兩種譯文誰贏是不可預期的。改成分流：待翻譯只收全新原文。
                if value in global_keys:
                    status = "同文異欄位"
                    same_text_other_field[(table, str(field))].add(value)
                else:
                    status = "全新原文"
                    pending[table][str(field)].setdefault(value, "")
                occurrences.append({
                    "table": table,
                    "field": str(field),
                    "source": value,
                    "record": record_id(row, index),
                    "status": status,
                })
                scanned[status] += 1

    serializable = {
        table: {field: dict(sorted(entries.items())) for field, entries in sorted(fields.items())}
        for table, fields in sorted(pending.items())
    }
    unique_missing = sum(len(entries) for fields in serializable.values() for entries in fields.values())
    output.mkdir(parents=True, exist_ok=True)
    (output / "待翻譯.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "待翻譯_來源明細.json").write_text(
        json.dumps(occurrences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    unknown_serializable = {
        f"{table}/{field}": sorted(values)
        for (table, field), values in sorted(unknown_fields.items())
    }
    unknown_total = sum(len(values) for values in unknown_serializable.values())
    (output / "未知欄位_待確認.json").write_text(
        json.dumps(unknown_serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    same_text_serializable = {
        f"{table}/{field}": {source: global_keys[source] for source in sorted(values)}
        for (table, field), values in sorted(same_text_other_field.items())
    }
    same_text_total = sum(len(values) for values in same_text_serializable.values())
    (output / "同文異欄位_不需重翻.json").write_text(
        json.dumps(same_text_serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    by_table = Counter(item["table"] for item in occurrences)
    lines = [
        "# Masterdata 缺少條目比對報告",
        "",
        f"- 產生時間：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- Masterdata：`{master_data}`",
        f"- 現有版本：`{current}`",
        f"- 掃描翻譯檔：{len(source_files)} 個",
        f"- 掃描非空字串：{scanned['strings']} 筆",
        f"- 同表同欄位已存在：{scanned['exact_existing']} 筆",
        f"- 待翻譯的唯一條目（全新原文）：{unique_missing} 筆",
        f"- 缺少條目出現次數：{len(occurrences)} 次",
        f"- 其中全新原文：{scanned['全新原文']} 次",
        f"- 其中同文異欄位：{scanned['同文異欄位']} 次"
        f"（{same_text_total} 筆唯一原文，見 `同文異欄位_不需重翻.json`）",
        f"- 刻意排除資料表：{', '.join(f'`{name}`' for name in sorted(excluded_tables)) or '無'}",
        f"- 刻意排除欄位：{', '.join(f'`{t}/{f}`' for t, f in sorted(excluded_fields)) or '無'}",
        f"- 未知欄位待確認：{unknown_total} 筆（見 `未知欄位_待確認.json`）",
        "",
        "## 各資料表缺少次數",
        "",
        "| 資料表 | 次數 |",
        "|---|---:|",
    ]
    lines.extend(f"| `{table}` | {count} |" for table, count in by_table.most_common())
    if unknown_serializable:
        lines += [
            "",
            "## 未知欄位（本工具的盲區，需人工判斷）",
            "",
            "這些 `(表, 欄位)` 在現有翻譯裡從未出現過，所以不會進待翻譯。",
            "清單只收「含日文且全庫沒譯過」的字串。確認要翻的話，",
            "先在 `static/zh_Hant.json` 該表該欄位手動補一條，之後本工具就會自動追蹤。",
            "",
            "| 表/欄位 | 未譯字串 |",
            "|---|---:|",
        ]
        lines.extend(
            f"| `{key}` | {len(values)} |"
            for key, values in sorted(unknown_serializable.items(), key=lambda kv: -len(kv[1]))
        )
    if invalid:
        lines += ["", "## 無法解析的檔案", ""] + [f"- {item}" for item in invalid]
    lines += [
        "",
        "## 判定方式",
        "",
        "以 `資料表 + 欄位 + 原文` 為精確鍵，但輸出分三份：",
        "",
        "- `待翻譯.json`：全新原文，全庫沒有任何譯文 → 這份才需要翻。",
        "- `同文異欄位_不需重翻.json`：原文已在別的表／欄位翻過。外掛實測只比對原文、",
        "  不看欄位，所以同一句原文全庫只能有一種譯文；重翻會製造兩種譯文互搶，"
        "  誰贏不可預期。附上既有譯文供核對，除非確定既有譯文是錯的，否則不要動。",
        "- `未知欄位_待確認.json`：該 `(表, 欄位)` 從未在翻譯檔出現過，本工具追蹤不到。",
        "  要納入的話先在 `static/zh_Hant.json` 手動補一條，之後就會自動追蹤。",
        "",
    ]
    (output / "比對報告.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "output": str(output),
        "unique_missing": unique_missing,
        "occurrences": len(occurrences),
        "same_text_other_field": same_text_total,
        "unknown_field_strings": unknown_total,
        "invalid_files": len(invalid),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
