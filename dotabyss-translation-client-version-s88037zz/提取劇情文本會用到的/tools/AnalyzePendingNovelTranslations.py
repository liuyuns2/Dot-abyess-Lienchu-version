import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--novels", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lang", default="zh_Hant.json")
    args = parser.parse_args()

    root = Path(args.novels)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    total_entries = 0
    total_empty = 0
    for path in sorted(root.glob(f"*/{args.lang}")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = len(data)
        empty = sum(1 for value in data.values() if value in ("", None))
        total_entries += entries
        total_empty += empty
        rows.append(
            {
                "script_id": path.parent.name,
                "entries": entries,
                "empty": empty,
                "path": str(path),
            }
        )

    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["script_id", "entries", "empty", "path"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"folders={len(rows)}")
    print(f"entries={total_entries}")
    print(f"empty={total_empty}")
    print(f"output={output}")
    for row in rows:
        print(f"{row['script_id']}\t{row['entries']}\t{row['empty']}")


if __name__ == "__main__":
    main()
