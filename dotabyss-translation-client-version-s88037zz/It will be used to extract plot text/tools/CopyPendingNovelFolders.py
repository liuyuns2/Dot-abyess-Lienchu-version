import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path


def copy_pending_folders(csv_path: Path, novels_dir: Path, output_dir: Path) -> Counter[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    counts = Counter(row["script_id"] for row in rows)
    if output_dir.exists():
        for child in output_dir.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except PermissionError:
                print(f"Skipping locked path: {child}")
    output_dir.mkdir(parents=True, exist_ok=True)

    for script_id in sorted(counts):
        src = novels_dir / script_id
        dst = output_dir / script_id
        if not src.exists():
            continue
        shutil.copytree(src, dst, dirs_exist_ok=True)

    return counts


def write_index(path: Path, counts: Counter[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Pending Novel Folders\n\n")
        f.write(f"Folders: {len(counts)}\n")
        f.write(f"Empty entries: {sum(counts.values())}\n\n")
        f.write("| Script ID | Empty Entries |\n")
        f.write("|---|---:|\n")
        for script_id, count in sorted(counts.items()):
            f.write(f"| {script_id} | {count} |\n")


def write_json_index(path: Path, counts: Counter[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "folders": len(counts),
        "empty_entries": sum(counts.values()),
        "scripts": [{"script_id": script_id, "empty_entries": count} for script_id, count in sorted(counts.items())],
    }
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy novel folders that contain empty translations.")
    parser.add_argument("--csv", default=r"E:\離線板\output\empty_translations\empty_translations.csv")
    parser.add_argument("--novels", default=r"E:\離線板\output\bundle_novels_merged")
    parser.add_argument("--output", default=r"E:\離線板\output\pending_novels")
    args = parser.parse_args()

    output_dir = Path(args.output)
    counts = copy_pending_folders(Path(args.csv), Path(args.novels), output_dir)
    write_index(output_dir / "index.md", counts)
    write_json_index(output_dir / "index.json", counts)

    print(f"Copied folders: {len(counts)}")
    print(f"Empty entries: {sum(counts.values())}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
