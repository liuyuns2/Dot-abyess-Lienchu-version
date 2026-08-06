import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def safe_group_name(script_id: str, language: str) -> str:
    lang_part = language.replace(".", "")
    name = f"{script_id}-{lang_part}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def write_group(path: Path, rows: list[dict[str, str]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    md_path = path / "to_translate.md"
    txt_path = path / "to_translate.txt"

    script_id = rows[0]["script_id"]
    language = rows[0]["language"]

    with md_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# To Translate: {script_id} / {language}\n\n")
        f.write("請將以下日文手遊劇情文本翻譯成自然流暢的繁體中文（台灣用語）。\n\n")
        f.write("規則：\n")
        f.write("- 保留 `<br>`、`<user>`、HTML tag、標點、語氣和特殊符號。\n")
        f.write("- 請用相同編號回覆。\n")
        f.write("- 不要改日文原文。\n\n")
        f.write(f"Entries: {len(rows)}\n\n")
        for index, row in enumerate(rows, start=1):
            f.write(f"## {index}. #{row['entry_index']}\n\n")
            f.write(f"File: `{row['file']}`\n\n")
            f.write("```ja\n")
            f.write(row["source_text"])
            f.write("\n```\n\n")
            f.write("翻譯：\n\n")

    with txt_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"To Translate: {script_id} / {language}\n")
        f.write(f"Entries: {len(rows)}\n\n")
        for index, row in enumerate(rows, start=1):
            f.write(f"[{index}] #{row['entry_index']}\n")
            f.write(f"File: {row['file']}\n")
            f.write(row["source_text"])
            f.write("\n\nTranslation:\n\n")


def write_index(output_dir: Path, groups: dict[tuple[str, str], list[dict[str, str]]]) -> None:
    index_path = output_dir / "index.md"
    with index_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# To Translate Groups\n\n")
        f.write(f"Groups: {len(groups)}\n")
        f.write(f"Entries: {sum(len(rows) for rows in groups.values())}\n\n")
        f.write("| Script | Language | Entries | Folder |\n")
        f.write("|---|---:|---:|---|\n")
        for (script_id, language), rows in sorted(groups.items()):
            folder = safe_group_name(script_id, language)
            f.write(f"| {script_id} | {language} | {len(rows)} | `{folder}` |\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Group empty translation CSV by script id and language.")
    parser.add_argument("--csv", default=r"E:\離線板\output\empty_translations\empty_translations.csv")
    parser.add_argument("--output", default=r"E:\離線板\output\to_translate\by_script")
    args = parser.parse_args()

    with Path(args.csv).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["script_id"], row["language"])].append(row)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    for (script_id, language), group_rows in groups.items():
        write_group(output_dir / safe_group_name(script_id, language), group_rows)
    write_index(output_dir, groups)

    print(f"Entries: {len(rows)}")
    print(f"Groups: {len(groups)}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
