import argparse
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any


NOVEL_TABLES = [
    "m_novel_prologues",
    "m_novel_others",
    "m_novel_mains",
    "m_novel_homes",
    "m_novel_events",
    "m_novel_characters",
    "m_novel_character_skins",
]

TEXT_FIELDS = [
    "title",
    "description",
    "category_name",
]


def add_entry(entries: OrderedDict[str, str], value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text and text != "0" and text not in entries:
        entries[text] = ""


def write_json(path: Path, entries: OrderedDict[str, str], value_mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = OrderedDict()
    for key, value in entries.items():
        output[key] = key if value_mode == "source" else value
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")


def export_masterdata(masterdata_path: Path, output_root: Path, value_mode: str) -> tuple[int, int]:
    with masterdata_path.open("r", encoding="utf-8") as f:
        masterdata = json.load(f)

    scripts: dict[str, OrderedDict[str, str]] = {}

    for table_name in NOVEL_TABLES:
        for row in masterdata.get(table_name, []) or []:
            if not isinstance(row, dict):
                continue
            script_id = row.get("script_id")
            if not script_id:
                continue

            script_id = str(script_id).strip()
            entries = scripts.setdefault(script_id, OrderedDict())
            for field in TEXT_FIELDS:
                add_entry(entries, row.get(field))

    exported_scripts = 0
    exported_entries = 0
    for script_id, entries in sorted(scripts.items()):
        if not entries:
            continue
        folder = output_root / script_id
        write_json(folder / "zh_Hant.json", entries, value_mode)
        write_json(folder / "zh_Hans.json", entries, value_mode)
        exported_scripts += 1
        exported_entries += len(entries)

    return exported_scripts, exported_entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export DotAbyss MasterData novel title/description fields to novels translation format."
    )
    parser.add_argument(
        "--masterdata",
        default=r"E:\離線板\output\MasterData.json",
        help="Path to MasterData.json.",
    )
    parser.add_argument(
        "--output",
        default=r"E:\離線板\output\masterdata_novels",
        help="Output novels directory.",
    )
    parser.add_argument(
        "--value-mode",
        choices=("empty", "source"),
        default="empty",
        help="Use empty values for translation work, or source text as values.",
    )
    args = parser.parse_args()

    exported_scripts, exported_entries = export_masterdata(
        Path(args.masterdata),
        Path(args.output),
        args.value_mode,
    )
    print(f"Exported scripts: {exported_scripts}")
    print(f"Exported text entries: {exported_entries}")
    print(f"Output: {Path(args.output)}")


if __name__ == "__main__":
    main()
