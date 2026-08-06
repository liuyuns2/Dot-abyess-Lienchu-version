import argparse
import json
from pathlib import Path


def load_object(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", required=True)
    parser.add_argument("--additions", required=True)
    args = parser.parse_args()

    names_path = Path(args.names)
    names = load_object(names_path)
    additions = load_object(Path(args.additions))

    added = 0
    unchanged = 0
    for key, value in additions.items():
        if key in names:
            if names[key] != value:
                raise ValueError(
                    f"Refusing to overwrite {key!r}: "
                    f"{names[key]!r} != {value!r}"
                )
            unchanged += 1
            continue
        names[key] = value
        added += 1

    if added:
        with names_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(names, handle, ensure_ascii=False, indent=4)
            handle.write("\n")

    print(f"added={added}")
    print(f"unchanged={unchanged}")


if __name__ == "__main__":
    main()
