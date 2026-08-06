import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(key): "" if value is None else str(value) for key, value in data.items()}


def find_empty_entries(novels_dir: Path, language: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for script_dir in sorted(path for path in novels_dir.iterdir() if path.is_dir()):
        json_path = script_dir / language
        if not json_path.exists():
            continue
        data = load_json(json_path)
        for index, (source_text, translated_text) in enumerate(data.items(), start=1):
            if translated_text == "":
                rows.append(
                    {
                        "script_id": script_dir.name,
                        "language": language,
                        "entry_index": str(index),
                        "source_text": source_text,
                        "file": str(json_path),
                    }
                )
    return rows


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# To Translate\n\n")
        f.write("請把以下日文手遊劇情文本翻譯成自然流暢的繁體中文（台灣用語）。\n\n")
        f.write("規則：\n")
        f.write("- 保留 `<br>`、`<user>`、HTML tag、標點、語氣和特殊符號。\n")
        f.write("- 每一條請用相同編號回覆。\n")
        f.write("- 不要改日文原文。\n\n")
        f.write(f"Total entries: {len(rows)}\n\n")

        if not rows:
            f.write("No empty translations found.\n")
            return

        for idx, row in enumerate(rows, start=1):
            f.write(f"## {idx}. {row['script_id']} / {row['language']} / #{row['entry_index']}\n\n")
            f.write(f"File: `{row['file']}`\n\n")
            f.write("```ja\n")
            f.write(row["source_text"])
            f.write("\n```\n\n")
            f.write("翻譯：\n\n")


def write_text(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("To Translate\n")
        f.write("=" * 12 + "\n\n")
        f.write(f"Total entries: {len(rows)}\n\n")
        for idx, row in enumerate(rows, start=1):
            f.write(f"[{idx}] {row['script_id']} / {row['language']} / #{row['entry_index']}\n")
            f.write(f"File: {row['file']}\n")
            f.write(row["source_text"])
            f.write("\n\nTranslation:\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a human/Codex translation list from empty novel values.")
    parser.add_argument("--novels", default=r"E:\離線板\output\bundle_novels_merged")
    parser.add_argument("--output", default=r"E:\離線板\output\to_translate")
    parser.add_argument("--lang", default="zh_Hant.json")
    args = parser.parse_args()

    rows = find_empty_entries(Path(args.novels), args.lang)
    output_dir = Path(args.output)
    write_markdown(output_dir / "to_translate.md", rows)
    write_text(output_dir / "to_translate.txt", rows)

    print(f"Scanned: {args.novels}")
    print(f"Language: {args.lang}")
    print(f"Entries to translate: {len(rows)}")
    print(f"Markdown: {output_dir / 'to_translate.md'}")
    print(f"Text: {output_dir / 'to_translate.txt'}")


if __name__ == "__main__":
    main()
