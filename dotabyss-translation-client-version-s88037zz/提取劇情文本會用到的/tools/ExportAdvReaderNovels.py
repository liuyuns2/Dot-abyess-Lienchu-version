import argparse
import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable


TEXT_COMMANDS = {
    "message",
    "l2dmessage",
    "messagetextcenter",
    "messagetextunder",
    "title",
}


def command_text(command: dict[str, Any]) -> str:
    name = str(command.get("command", "")).lower()
    args = command.get("args") or []

    if command.get("message"):
        return str(command["message"])

    if name == "l2dmessage":
        return str(args[1]) if len(args) > 1 else ""

    if name in {"message", "messagetextcenter", "messagetextunder", "title"}:
        return str(args[0]) if args else ""

    return ""


def story_scripts(story: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for script in story.get("scripts") or []:
        if isinstance(script, dict):
            yield script


def script_id(script: dict[str, Any], story_id: str) -> str:
    for key in ("id", "name"):
        value = script.get(key)
        if value:
            return str(value)
    text_path = script.get("text")
    if text_path:
        return Path(str(text_path)).stem
    return str(story_id)


def extract_script_texts(script: dict[str, Any]) -> OrderedDict[str, str]:
    entries: OrderedDict[str, str] = OrderedDict()
    for command in script.get("commands") or []:
        if not isinstance(command, dict):
            continue
        if str(command.get("command", "")).lower() not in TEXT_COMMANDS:
            continue
        text = command_text(command).strip()
        if text and text not in entries:
            entries[text] = ""
    return entries


def write_json(path: Path, data: OrderedDict[str, str], value_mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = OrderedDict()
    for key, value in data.items():
        output[key] = key if value_mode == "source" else value
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export AdvReader story text to dotabyss-translation novels format."
    )
    parser.add_argument(
        "--reader",
        default=r"E:\離線板\advreaderfinal",
        help="AdvReader root directory.",
    )
    parser.add_argument(
        "--data-root",
        default="data_r18_all",
        help="Reader data root containing index.json and stories/.",
    )
    parser.add_argument(
        "--output",
        default=r"E:\離線板\output\novels_export",
        help="Output novels directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Export only the first N stories for testing.",
    )
    parser.add_argument(
        "--value-mode",
        choices=("empty", "source"),
        default="empty",
        help="Use empty values for translation work, or source text as values.",
    )
    args = parser.parse_args()

    reader_root = Path(args.reader)
    data_root = reader_root / args.data_root
    index_path = data_root / "index.json"
    output_root = Path(args.output)

    with index_path.open("r", encoding="utf-8") as f:
        index = json.load(f)

    stories = index.get("stories") or []
    if args.limit > 0:
        stories = stories[: args.limit]

    exported_scripts = 0
    exported_entries = 0

    for story_meta in stories:
        story_id = str(story_meta.get("id") or "")
        story_path = data_root / str(story_meta.get("path") or "")
        if not story_path.exists():
            continue

        with story_path.open("r", encoding="utf-8") as f:
            story = json.load(f)

        for script in story_scripts(story):
            entries = extract_script_texts(script)
            if not entries:
                continue

            folder = output_root / script_id(script, story_id)
            write_json(folder / "zh_Hant.json", entries, args.value_mode)
            write_json(folder / "zh_Hans.json", entries, args.value_mode)
            exported_scripts += 1
            exported_entries += len(entries)

    print(f"Exported scripts: {exported_scripts}")
    print(f"Exported text entries: {exported_entries}")
    print(f"Output: {output_root}")


if __name__ == "__main__":
    main()
