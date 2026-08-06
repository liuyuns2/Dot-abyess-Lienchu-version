import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    target_path = Path(args.target)
    source = load_json(source_path)
    target = load_json(target_path)

    changed = 0
    for key, value in target.items():
        if value not in ("", None):
            continue
        source_value = source.get(key)
        if source_value in ("", None):
            continue
        target[key] = source_value
        changed += 1

    if changed:
        with target_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(target, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    print(f"changed_entries={changed}")


if __name__ == "__main__":
    main()
