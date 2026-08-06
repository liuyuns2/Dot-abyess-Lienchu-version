import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import UnityPy


SCRIPT_ID_RE = re.compile(r"hmr_\d+", re.IGNORECASE)
CHARA_RE = re.compile(r"chara_(\d+)", re.IGNORECASE)


def safe_name(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value)


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    rows = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = row.get("primary_key") or ""
            if key:
                rows[key] = row
    return rows


def extract_byte_arrays(value: Any) -> list[bytes]:
    found: list[bytes] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "data" and isinstance(child, list) and child:
                if all(isinstance(item, int) and 0 <= item <= 255 for item in child[:32]):
                    blob = bytes(child)
                    if blob.startswith(b"@UTF") or b"CRI" in blob[:256] or len(blob) > 1024:
                        found.append(blob)
            found.extend(extract_byte_arrays(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(extract_byte_arrays(child))
    return found


def metadata_from_name(bundle_name: str, manifest_row: dict[str, str] | None = None) -> tuple[str, str]:
    script_id = ""
    chara_id = ""
    if manifest_row:
        script_id = manifest_row.get("script_id") or ""
        chara_id = manifest_row.get("chara_id") or ""
    if not script_id:
        match = SCRIPT_ID_RE.search(bundle_name)
        script_id = match.group(0) if match else Path(bundle_name).stem
    if not chara_id:
        match = CHARA_RE.search(bundle_name)
        chara_id = match.group(1) if match else "_unknown_chara"
    return chara_id, script_id


def extract_bundle(bundle_path: Path, output_root: Path, manifest_row: dict[str, str] | None) -> list[Path]:
    env = UnityPy.load(str(bundle_path))
    chara_id, script_id = metadata_from_name(bundle_path.name, manifest_row)
    output_dir = output_root / safe_name(chara_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    seen: set[bytes] = set()
    for obj in env.objects:
        type_value = getattr(obj.type, "value", obj.type)
        if type_value != 114:
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        for index, blob in enumerate(extract_byte_arrays(tree), 1):
            if blob in seen:
                continue
            seen.add(blob)
            suffix = "" if len(seen) == 1 else f"_{index:02d}"
            out_path = output_dir / f"{safe_name(script_id)}{suffix}.acb"
            out_path.write_bytes(blob)
            outputs.append(out_path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract r18 novel voice ACB files from UnityFS bundles.")
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    downloads = Path(args.downloads)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(Path(args.manifest))

    bundles = sorted(downloads.glob("*.bundle"))
    exported = []
    failed = []
    empty = []
    for index, bundle in enumerate(bundles, 1):
        try:
            outputs = extract_bundle(bundle, output, manifest.get(bundle.name))
            if outputs:
                exported.extend(outputs)
            else:
                empty.append(bundle.name)
        except Exception as exc:
            failed.append({"bundle": bundle.name, "error": str(exc)})
        if index % 50 == 0 or index == len(bundles):
            print(f"progress {index}/{len(bundles)} exported={len(exported)} empty={len(empty)} failed={len(failed)}")

    summary = {
        "bundles": len(bundles),
        "exported_acb": len(exported),
        "empty_bundles": len(empty),
        "failed_bundles": len(failed),
        "output": str(output),
    }
    (output / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if empty:
        (output / "_empty_bundles.txt").write_text("\n".join(empty) + "\n", encoding="utf-8")
    if failed:
        (output / "_failed_bundles.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
