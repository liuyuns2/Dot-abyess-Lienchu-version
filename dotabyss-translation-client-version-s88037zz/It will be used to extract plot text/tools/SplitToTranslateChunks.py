import argparse
import csv
import math
from pathlib import Path


def write_chunk(path: Path, rows: list[dict[str, str]], start_index: int, total: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# To Translate Chunk {path.stem.rsplit('_', 1)[-1]}\n\n")
        f.write("請將以下日文手遊劇情文本翻譯成自然流暢的繁體中文（台灣用語）。\n\n")
        f.write("規則：\n")
        f.write("- 保留 `<br>`、`<user>`、HTML tag、標點、語氣和特殊符號。\n")
        f.write("- 請用相同編號回覆。\n")
        f.write("- 不要改日文原文。\n\n")
        f.write(f"Entries: {len(rows)} / Total: {total}\n\n")
        for offset, row in enumerate(rows):
            index = start_index + offset
            f.write(f"## {index}. {row['script_id']} / {row['language']} / #{row['entry_index']}\n\n")
            f.write(f"File: `{row['file']}`\n\n")
            f.write("```ja\n")
            f.write(row["source_text"])
            f.write("\n```\n\n")
            f.write("翻譯：\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split empty translation CSV into smaller markdown chunks.")
    parser.add_argument("--csv", default=r"E:\離線板\output\empty_translations\empty_translations.csv")
    parser.add_argument("--output", default=r"E:\離線板\output\to_translate\chunks")
    parser.add_argument("--chunk-size", type=int, default=100)
    args = parser.parse_args()

    with Path(args.csv).open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    output_dir = Path(args.output)
    for chunk_number, start in enumerate(range(0, len(rows), args.chunk_size), start=1):
        chunk = rows[start : start + args.chunk_size]
        write_chunk(output_dir / f"to_translate_{chunk_number:03d}.md", chunk, start + 1, len(rows))

    print(f"Entries: {len(rows)}")
    print(f"Chunks: {math.ceil(len(rows) / args.chunk_size) if rows else 0}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
