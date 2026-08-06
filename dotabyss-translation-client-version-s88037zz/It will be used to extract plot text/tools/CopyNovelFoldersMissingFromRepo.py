import argparse
import json
import re
import shutil
from pathlib import Path


SCRIPT_ID_RE = re.compile(r"^(?:mas|hmn|hmr|men|evs)_\d+$", re.IGNORECASE)


def script_folders(path: Path) -> dict[str, Path]:
    if not path.exists():
        raise SystemExit(f"Directory does not exist: {path}")
    result: dict[str, Path] = {}
    for child in path.iterdir():
        if child.is_dir() and SCRIPT_ID_RE.match(child.name):
            result[child.name] = child
    return result


def clear_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def write_index(
    output: Path,
    missing: list[str],
    source_count: int,
    excluded_count: int,
    both_count: int,
    exclude_dirs: list[str],
) -> None:
    with (output / "index.md").open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Missing Novel Folders\n\n")
        f.write(f"Source folders: {source_count}\n")
        f.write(f"Excluded folders: {excluded_count}\n")
        f.write(f"Already excluded: {both_count}\n")
        f.write(f"Missing after exclude: {len(missing)}\n\n")
        f.write("Exclude dirs:\n")
        for exclude_dir in exclude_dirs:
            f.write(f"- {exclude_dir}\n")
        f.write("\n")
        for script_id in missing:
            f.write(f"- {script_id}\n")

    with (output / "index.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "source_folders": source_count,
                "excluded_folders": excluded_count,
                "already_excluded": both_count,
                "missing_after_exclude": len(missing),
                "exclude_dirs": exclude_dirs,
                "scripts": missing,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy source novel folders whose script ids do not exist in repo.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--repo", required=True, help="Primary repo novels directory to exclude.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional directory whose script folders should be excluded.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = script_folders(Path(args.source))
    exclude_paths = [Path(args.repo), *(Path(path) for path in args.exclude)]
    excluded: dict[str, Path] = {}
    for path in exclude_paths:
        excluded.update(script_folders(path))
    output = Path(args.output)

    missing = sorted(set(source) - set(excluded))
    both = sorted(set(source) & set(excluded))

    clear_output(output)
    for script_id in missing:
        shutil.copytree(source[script_id], output / script_id)

    write_index(output, missing, len(source), len(excluded), len(both), [str(path) for path in exclude_paths])

    print(f"Source folders: {len(source)}")
    print(f"Excluded folders: {len(excluded)}")
    print(f"Already excluded: {len(both)}")
    print(f"Missing after exclude copied: {len(missing)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
