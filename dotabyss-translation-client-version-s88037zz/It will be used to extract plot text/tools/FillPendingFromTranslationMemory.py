import argparse
import json
from collections import OrderedDict
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_memory(memory: dict[str, str], path: Path) -> int:
    try:
        data = load_json(path)
    except Exception:
        return 0
    added = 0
    if not isinstance(data, dict):
        return 0
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if not value:
            continue
        if key not in memory:
            memory[key] = value
            added += 1
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill pending novel zh_Hant.json values from exact-key translation memory.")
    parser.add_argument("--pending", required=True)
    parser.add_argument("--memory-dir", action="append", default=[])
    parser.add_argument("--memory-json", action="append", default=[])
    parser.add_argument("--lang", default="zh_Hant.json")
    args = parser.parse_args()

    memory: dict[str, str] = {}
    memory_files = 0
    for json_path in args.memory_json:
        path = Path(json_path)
        if path.exists():
            add_memory(memory, path)
            memory_files += 1

    for directory in args.memory_dir:
        root = Path(directory)
        if not root.exists():
            continue
        for path in sorted(root.rglob(args.lang)):
            add_memory(memory, path)
            memory_files += 1

    pending_root = Path(args.pending)
    changed_files = 0
    filled = 0
    remaining = 0
    total = 0
    per_file = []

    for path in sorted(pending_root.glob(f"*/{args.lang}")):
        data = load_json(path)
        file_filled = 0
        file_remaining = 0
        for key, value in data.items():
            total += 1
            if value not in ("", None):
                continue
            replacement = memory.get(key)
            if replacement:
                data[key] = replacement
                filled += 1
                file_filled += 1
            else:
                remaining += 1
                file_remaining += 1
        if file_filled:
            write_json(path, data)
            changed_files += 1
        per_file.append((path.parent.name, file_filled, file_remaining))

    print(f"memory_files={memory_files}")
    print(f"memory_entries={len(memory)}")
    print(f"pending_entries={total}")
    print(f"filled={filled}")
    print(f"remaining_empty={remaining}")
    print(f"changed_files={changed_files}")
    for script_id, file_filled, file_remaining in per_file:
        if file_filled or file_remaining:
            print(f"{script_id}\tfilled={file_filled}\tremaining={file_remaining}")


if __name__ == "__main__":
    main()
