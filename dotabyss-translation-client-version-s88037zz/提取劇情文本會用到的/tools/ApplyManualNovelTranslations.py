import argparse
import json
from collections import OrderedDict
from pathlib import Path


def load_ordered(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def write_ordered(path: Path, data) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--translations", required=True)
    args = parser.parse_args()

    payload = load_ordered(Path(args.translations))
    changed_files = 0
    changed_entries = 0
    for file_path, translations in payload.items():
        path = Path(file_path)
        data = load_ordered(path)
        file_changed = 0
        for key, value in translations.items():
            if key not in data:
                raise SystemExit(f"Missing key in {path}: {key}")
            if data[key] != value:
                data[key] = value
                file_changed += 1
        if file_changed:
            write_ordered(path, data)
            changed_files += 1
            changed_entries += file_changed

    print(f"changed_files={changed_files}")
    print(f"changed_entries={changed_entries}")


if __name__ == "__main__":
    main()
