from __future__ import annotations

import argparse
import json
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

DEFAULT_EXCLUDED_TABLES = {
    "m_character_abilities",
    "m_character_action_skills",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def translation_files(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in TRANSLATION_GLOBS:
        paths.update(root.glob(pattern))
    return sorted(paths)


def collect_coverage(root: Path) -> tuple[set[tuple[str, str, str]], set[tuple[str, str]], set[str], list[Path]]:
    exact: set[tuple[str, str, str]] = set()
    known_fields: set[tuple[str, str]] = set()
    global_keys: set[str] = set()
    files = translation_files(root)
    for path in files:
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        for table, fields in data.items():
            if not isinstance(fields, dict):
                continue
            for field, entries in fields.items():
                if not isinstance(entries, dict):
                    continue
                known_fields.add((str(table), str(field)))
                for source in entries:
                    if isinstance(source, str):
                        exact.add((str(table), str(field), source))
                        global_keys.add(source)
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
    exact, known_fields, global_keys, source_files = collect_coverage(current)

    pending: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    occurrences: list[dict[str, Any]] = []
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
                if (table, str(field)) not in known_fields:
                    continue
                scanned["strings"] += 1
                if (table, str(field), value) in exact:
                    scanned["exact_existing"] += 1
                    continue
                status = "同文異欄位" if value in global_keys else "全新原文"
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
        f"- 缺少的唯一條目：{unique_missing} 筆",
        f"- 缺少條目出現次數：{len(occurrences)} 次",
        f"- 其中全新原文：{scanned['全新原文']} 次",
        f"- 其中同文異欄位：{scanned['同文異欄位']} 次",
        f"- 刻意排除資料表：{', '.join(f'`{name}`' for name in sorted(excluded_tables)) or '無'}",
        "",
        "## 各資料表缺少次數",
        "",
        "| 資料表 | 次數 |",
        "|---|---:|",
    ]
    lines.extend(f"| `{table}` | {count} |" for table, count in by_table.most_common())
    if invalid:
        lines += ["", "## 無法解析的檔案", ""] + [f"- {item}" for item in invalid]
    lines += [
        "",
        "## 判定方式",
        "",
        "以 `資料表 + 欄位 + 原文` 為精確鍵。`同文異欄位` 表示原文已在其他位置出現，仍列入待翻譯，避免不同 UI／語境共用造成誤判。",
        "",
    ]
    (output / "比對報告.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "output": str(output),
        "unique_missing": unique_missing,
        "occurrences": len(occurrences),
        "invalid_files": len(invalid),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
