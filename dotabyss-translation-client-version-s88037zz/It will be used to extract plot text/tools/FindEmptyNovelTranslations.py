import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


def load_json(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def preview(text: str, limit: int = 90) -> str:
    text = text.replace("\r", "").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 1] + "..."


def find_empty_entries(novels_dir: Path, languages: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for script_dir in sorted(path for path in novels_dir.iterdir() if path.is_dir()):
        for language in languages:
            json_path = script_dir / language
            if not json_path.exists():
                continue
            data = load_json(json_path)
            for index, (key, value) in enumerate(data.items(), start=1):
                if value == "":
                    rows.append(
                        {
                            "script_id": script_dir.name,
                            "language": language,
                            "entry_index": str(index),
                            "source_text": key,
                            "file": str(json_path),
                        }
                    )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["script_id", "language", "entry_index", "source_text", "file"],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_file: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_file[(row["script_id"], row["language"], row["file"])].append(row)

    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Empty Novel Translations\n\n")
        f.write(f"Total empty entries: {len(rows)}\n\n")
        if not rows:
            f.write("No empty translations found.\n")
            return

        for (script_id, language, file_path), file_rows in sorted(by_file.items()):
            f.write(f"## {script_id} / {language}\n\n")
            f.write(f"File: `{file_path}`\n\n")
            for row in file_rows:
                f.write(f"- #{row['entry_index']}: {preview(row['source_text'])}\n")
            f.write("\n")


def write_html(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("<!doctype html>\n")
        f.write('<html lang="zh-Hant">\n')
        f.write("<head>\n")
        f.write('<meta charset="utf-8">\n')
        f.write("<title>Empty Novel Translations</title>\n")
        f.write(
            "<style>"
            "body{font-family:Segoe UI,Noto Sans TC,sans-serif;margin:24px;line-height:1.5}"
            "table{border-collapse:collapse;width:100%;font-size:14px}"
            "th,td{border:1px solid #ddd;padding:8px;vertical-align:top}"
            "th{background:#f4f4f4;text-align:left;position:sticky;top:0}"
            "code{white-space:pre-wrap;word-break:break-word}"
            ".count{font-weight:700;color:#b00020}"
            "</style>\n"
        )
        f.write("</head>\n<body>\n")
        f.write("<h1>Empty Novel Translations</h1>\n")
        f.write(f'<p>Total empty entries: <span class="count">{len(rows)}</span></p>\n')
        if rows:
            f.write("<table>\n")
            f.write(
                "<thead><tr>"
                "<th>Script</th><th>Lang</th><th>#</th><th>Source Text</th><th>File</th>"
                "</tr></thead>\n<tbody>\n"
            )
            for row in rows:
                f.write("<tr>")
                f.write(f"<td>{html.escape(row['script_id'])}</td>")
                f.write(f"<td>{html.escape(row['language'])}</td>")
                f.write(f"<td>{html.escape(row['entry_index'])}</td>")
                f.write(f"<td><code>{html.escape(row['source_text'])}</code></td>")
                f.write(f"<td><code>{html.escape(row['file'])}</code></td>")
                f.write("</tr>\n")
            f.write("</tbody>\n</table>\n")
        else:
            f.write("<p>No empty translations found.</p>\n")
        f.write("</body>\n</html>\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find empty translation values in dotabyss novels JSON files."
    )
    parser.add_argument("--novels", default=r"E:\離線板\output\bundle_novels_merged")
    parser.add_argument("--output", default=r"E:\離線板\output\empty_translations")
    parser.add_argument(
        "--lang",
        action="append",
        default=[],
        help="Language JSON file to scan, for example zh_Hant.json. Can be passed multiple times.",
    )
    args = parser.parse_args()

    novels_dir = Path(args.novels)
    output_dir = Path(args.output)
    languages = args.lang or ["zh_Hant.json", "zh_Hans.json"]

    rows = find_empty_entries(novels_dir, languages)
    write_csv(output_dir / "empty_translations.csv", rows)
    write_markdown(output_dir / "empty_translations.md", rows)
    write_html(output_dir / "empty_translations.html", rows)

    counts_by_language: dict[str, int] = defaultdict(int)
    counts_by_script: dict[str, int] = defaultdict(int)
    for row in rows:
        counts_by_language[row["language"]] += 1
        counts_by_script[row["script_id"]] += 1

    print(f"Scanned: {novels_dir}")
    print(f"Empty entries: {len(rows)}")
    for language, count in sorted(counts_by_language.items()):
        print(f"{language}: {count}")
    print(f"Scripts with empty entries: {len(counts_by_script)}")
    print(f"CSV: {output_dir / 'empty_translations.csv'}")
    print(f"Markdown: {output_dir / 'empty_translations.md'}")
    print(f"HTML: {output_dir / 'empty_translations.html'}")


if __name__ == "__main__":
    main()
