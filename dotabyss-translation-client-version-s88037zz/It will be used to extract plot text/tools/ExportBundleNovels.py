import argparse
import csv
import json
import re
import shutil
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

import UnityPy


NOVEL_TABLES = [
    "m_novel_prologues",
    "m_novel_others",
    "m_novel_mains",
    "m_novel_homes",
    "m_novel_events",
    "m_novel_characters",
    "m_novel_character_skins",
]

TEXT_COMMANDS = {
    "message",
    "dotmessage",
    "l2dmessage",
    "messagetextcenter",
    "messagetextunder",
}

SCRIPT_ID_RE = re.compile(r"(?:mas|hmn|hmr|men|evs)_\d+", re.IGNORECASE)
SCRIPT_ID_FULL_RE = re.compile(r"^(?:mas|hmn|hmr|men|evs)_\d+$", re.IGNORECASE)
SUPPORTED_LANGUAGE_FILES = ("zh_Hant.json", "zh_Hans.json")


def default_output_base() -> Path:
    return Path("E:/") / "\u96e2\u7dda\u677f" / "output"


def collect_script_ids(masterdata_path: Path) -> list[str]:
    with masterdata_path.open("r", encoding="utf-8") as f:
        masterdata = json.load(f)

    seen = set()
    script_ids: list[str] = []
    for table_name in NOVEL_TABLES:
        for row in masterdata.get(table_name, []) or []:
            if not isinstance(row, dict):
                continue
            script_id = str(row.get("script_id") or "").strip()
            if script_id and script_id not in seen:
                seen.add(script_id)
                script_ids.append(script_id)
    return script_ids


def load_assets(assets_path: Path) -> list[dict[str, Any]]:
    with assets_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("assets") or []


def index_text_bundles(assets: Iterable[dict[str, Any]], downloads_dir: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for asset in assets:
        primary_key = str(asset.get("primary_key") or "")
        if not primary_key.endswith(".bundle"):
            continue

        lowered = primary_key.lower()
        if ".txt_" not in lowered:
            continue
        if not any(marker in lowered for marker in ["_novel_", "r18-only_novel"]):
            continue

        bundle_path = downloads_dir / primary_key
        if not bundle_path.exists():
            continue

        script_candidates = SCRIPT_ID_RE.findall(primary_key)
        if not script_candidates:
            continue
        result.setdefault(script_candidates[-1], bundle_path)
    return result


def read_text_assets(bundle_path: Path) -> list[str]:
    env = UnityPy.load(str(bundle_path))
    texts: list[str] = []
    for obj in env.objects:
        if getattr(obj.type, "name", "") != "TextAsset":
            continue
        data = obj.read()
        script = getattr(data, "m_Script", "")
        if isinstance(script, (bytes, bytearray)):
            texts.append(script.decode("utf-8-sig", "ignore"))
        else:
            texts.append(str(script).lstrip("\ufeff"))
    return texts


def split_command(line: str) -> list[str]:
    try:
        return next(csv.reader([line]))
    except Exception:
        return line.split(",")


def extract_message_from_parts(parts: list[str]) -> str:
    if not parts:
        return ""

    command = parts[0].strip().lower()
    if command not in TEXT_COMMANDS:
        return ""

    index = 2 if len(parts) > 2 else 1
    if len(parts) <= index:
        return ""
    return parts[index]


def extract_entries(script_text: str) -> OrderedDict[str, str]:
    entries: OrderedDict[str, str] = OrderedDict()
    for raw_line in script_text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("//") or stripped_line.startswith(":"):
            continue
        text = extract_message_from_parts(split_command(line))
        if text and text not in entries:
            entries[text] = ""
    return entries


def load_existing_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def write_json(
    path: Path,
    entries: OrderedDict[str, str],
    value_mode: str,
    existing_values: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_values = existing_values or {}
    output = OrderedDict()
    for key, value in entries.items():
        if key in existing_values:
            output[key] = existing_values[key]
        else:
            output[key] = key if value_mode == "source" else value

    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")


def remove_unselected_languages(folder: Path, selected_languages: set[str]) -> None:
    for language in SUPPORTED_LANGUAGE_FILES:
        if language in selected_languages:
            continue
        path = folder / language
        if path.exists():
            path.unlink()


def remove_unselected_languages_from_root(output_root: Path, selected_languages: set[str]) -> None:
    if not output_root.exists():
        return

    for language in SUPPORTED_LANGUAGE_FILES:
        if language in selected_languages:
            continue
        for path in output_root.glob(f"*/{language}"):
            path.unlink()


def prune_output_folders(output_root: Path, selected_script_ids: set[str]) -> None:
    if not output_root.exists():
        return

    for folder in output_root.iterdir():
        if not folder.is_dir() or not SCRIPT_ID_FULL_RE.match(folder.name):
            continue
        if folder.name not in selected_script_ids:
            shutil.rmtree(folder)


def parse_args() -> argparse.Namespace:
    default_base = default_output_base()
    parser = argparse.ArgumentParser(
        description="Extract DotAbyss novel TextAsset bundles to novels translation JSON format."
    )
    parser.add_argument("--masterdata", default=str(default_base / "MasterData.json"))
    parser.add_argument("--assets", default=str(default_base / "assets.json"))
    parser.add_argument("--downloads", default=str(default_base / "downloads"))
    parser.add_argument("--output", default=str(default_base / "bundle_novels"))
    parser.add_argument(
        "--merge-existing",
        default="",
        help="Existing novels folder. Matching keys keep their current translations; new keys use value-mode.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--script-id",
        action="append",
        default=[],
        help="Export only the specified script id. Can be passed multiple times.",
    )
    parser.add_argument("--value-mode", choices=("empty", "source"), default="empty")
    parser.add_argument(
        "--include-bundle-only",
        action="store_true",
        help="Also export novel text bundles that exist in catalog but are not listed as MasterData entry scripts.",
    )
    parser.add_argument(
        "--prune-output",
        action="store_true",
        help="Remove old script folders from the output directory when they are not part of this export.",
    )
    parser.add_argument(
        "--lang",
        action="append",
        choices=SUPPORTED_LANGUAGE_FILES,
        default=[],
        help="Language JSON file to export. Defaults to both zh_Hant.json and zh_Hans.json. Can be passed multiple times.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    master_script_ids = args.script_id or collect_script_ids(Path(args.masterdata))
    if args.limit > 0:
        master_script_ids = master_script_ids[: args.limit]

    bundle_index = index_text_bundles(load_assets(Path(args.assets)), Path(args.downloads))
    script_ids = list(master_script_ids)
    if args.include_bundle_only and not args.script_id:
        seen = set(script_ids)
        for script_id in sorted(bundle_index):
            if script_id not in seen:
                seen.add(script_id)
                script_ids.append(script_id)

    output_root = Path(args.output)
    languages = args.lang or list(SUPPORTED_LANGUAGE_FILES)
    selected_languages = set(languages)
    existing_root = Path(args.merge_existing) if args.merge_existing else None
    if args.prune_output:
        prune_output_folders(output_root, set(script_ids))
    remove_unselected_languages_from_root(output_root, selected_languages)

    exported_scripts = 0
    exported_entries = 0
    missing_scripts: list[str] = []

    for script_id in script_ids:
        bundle_path = bundle_index.get(script_id)
        if not bundle_path:
            missing_scripts.append(script_id)
            continue

        entries: OrderedDict[str, str] = OrderedDict()
        for text_asset in read_text_assets(bundle_path):
            entries.update(extract_entries(text_asset))

        if not entries:
            missing_scripts.append(script_id)
            continue

        folder = output_root / script_id
        remove_unselected_languages(folder, selected_languages)
        for language in languages:
            existing_values = load_existing_values(existing_root / script_id / language) if existing_root else {}
            write_json(folder / language, entries, args.value_mode, existing_values)

        exported_scripts += 1
        exported_entries += len(entries)

    print(f"Script ids from MasterData: {len(master_script_ids)}")
    print(f"Script ids selected: {len(script_ids)}")
    print(f"Text bundles indexed: {len(bundle_index)}")
    print(f"Exported scripts: {exported_scripts}")
    print(f"Exported text entries: {exported_entries}")
    print(f"Missing/empty scripts: {len(missing_scripts)}")
    print(f"Languages: {', '.join(languages)}")
    if missing_scripts:
        print("Missing sample:", ", ".join(missing_scripts[:20]))
    print(f"Output: {output_root}")


if __name__ == "__main__":
    main()
