import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable

import UnityPy


SCRIPT_ID_RE = re.compile(r"(?:mas|hmn|hmr|men|evs)_\d+", re.IGNORECASE)
TEXT_COMMANDS = {
    "message",
    "dotmessage",
    "l2dmessage",
    "messagetextcenter",
    "messagetextunder",
}


def is_text_novel_bundle(primary_key: str) -> bool:
    lowered = primary_key.lower()
    return primary_key.endswith(".bundle") and ".txt_" in lowered and (
        "_novel_" in lowered or "r18-only_novel" in lowered
    )


def load_assets(path: Path) -> list[dict[str, Any]]:
    return (json.loads(path.read_text(encoding="utf-8")).get("assets") or [])


def normalize_filename(primary_key: str) -> str:
    return primary_key


def build_bundle_rows(assets: Iterable[dict[str, Any]], downloads: Path) -> list[dict[str, Any]]:
    rows = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        primary_key = str(asset.get("primary_key") or "")
        if not is_text_novel_bundle(primary_key):
            continue
        script_ids = SCRIPT_ID_RE.findall(primary_key)
        if not script_ids:
            continue
        file_path = downloads / normalize_filename(primary_key)
        rows.append(
            {
                "script_id": script_ids[-1],
                "primary_key": primary_key,
                "file_path": file_path,
                "is_r18": "r18" in primary_key.lower(),
                "bundle_size": asset.get("bundle_size") or 0,
            }
        )
    return rows


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


def extract_message(parts: list[str]) -> str:
    if not parts:
        return ""
    command = parts[0].strip().lower()
    if command not in TEXT_COMMANDS:
        return ""
    index = 2 if len(parts) > 2 else 1
    return parts[index] if len(parts) > index else ""


def extract_entries(script_text: str) -> OrderedDict[str, str]:
    entries: OrderedDict[str, str] = OrderedDict()
    for raw_line in script_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith(":"):
            continue
        text = extract_message(split_command(raw_line.rstrip("\r\n")))
        if text and text not in entries:
            entries[text] = ""
    return entries


def safe_stem(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", Path(name).stem)[:180]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all catalog novel TextAsset bundles, including r18-only bundles.")
    parser.add_argument("--assets", required=True)
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--value-mode", choices=("empty", "source"), default="empty")
    parser.add_argument("--write-raw", action="store_true")
    args = parser.parse_args()

    assets_path = Path(args.assets)
    downloads = Path(args.downloads)
    output = Path(args.output)
    novels_dir = output / "novels_all"
    raw_dir = output / "novel_text_raw"

    bundle_rows = build_bundle_rows(load_assets(assets_path), downloads)
    by_script: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing = []
    for row in bundle_rows:
        if row["file_path"].exists():
            by_script[row["script_id"]].append(row)
        else:
            missing.append(row)

    exported_scripts = 0
    exported_entries = 0
    exported_bundles = 0
    failed: list[dict[str, str]] = []
    manifest_rows: list[dict[str, Any]] = []

    for script_id, rows in sorted(by_script.items()):
        entries: OrderedDict[str, str] = OrderedDict()
        script_raw_dir = raw_dir / script_id

        for row in rows:
            try:
                texts = read_text_assets(row["file_path"])
            except Exception as exc:
                failed.append({"primary_key": row["primary_key"], "error": str(exc)})
                continue

            exported_bundles += 1
            bundle_entries = OrderedDict()
            for index, text in enumerate(texts, 1):
                if args.write_raw:
                    raw_path = script_raw_dir / f"{safe_stem(row['primary_key'])}_{index:02d}.txt"
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_text(text, encoding="utf-8", newline="\n")
                bundle_entries.update(extract_entries(text))

            before = len(entries)
            entries.update(bundle_entries)
            manifest_rows.append(
                {
                    "script_id": script_id,
                    "primary_key": row["primary_key"],
                    "is_r18": row["is_r18"],
                    "text_assets": len(texts),
                    "entries": len(bundle_entries),
                    "new_entries_after_merge": len(entries) - before,
                }
            )

        if not entries:
            continue

        value = (lambda key: key) if args.value_mode == "source" else (lambda key: "")
        write_json(novels_dir / script_id / "zh_Hant.json", OrderedDict((key, value(key)) for key in entries))
        exported_scripts += 1
        exported_entries += len(entries)

    write_json(output / "novel_export_manifest.json", manifest_rows)
    write_json(
        output / "novel_export_summary.json",
        {
            "catalog_text_novel_bundles": len(bundle_rows),
            "downloaded_bundles_found": sum(len(rows) for rows in by_script.values()),
            "missing_bundles": len(missing),
            "failed_bundles": len(failed),
            "exported_bundles": exported_bundles,
            "exported_scripts": exported_scripts,
            "exported_text_entries": exported_entries,
            "r18_bundles_exported": sum(1 for row in manifest_rows if row["is_r18"]),
            "output_novels": str(novels_dir),
            "output_raw": str(raw_dir) if args.write_raw else "",
        },
    )
    if missing:
        write_json(output / "novel_missing_bundles.json", missing[:1000])
    if failed:
        write_json(output / "novel_failed_bundles.json", failed)

    print(f"Catalog text novel bundles: {len(bundle_rows)}")
    print(f"Downloaded bundles found: {sum(len(rows) for rows in by_script.values())}")
    print(f"Exported bundles: {exported_bundles}")
    print(f"Exported scripts: {exported_scripts}")
    print(f"Exported entries: {exported_entries}")
    print(f"R18 bundles exported: {sum(1 for row in manifest_rows if row['is_r18'])}")
    print(f"Missing bundles: {len(missing)}")
    print(f"Failed bundles: {len(failed)}")
    print(f"Output novels: {novels_dir}")


if __name__ == "__main__":
    main()
