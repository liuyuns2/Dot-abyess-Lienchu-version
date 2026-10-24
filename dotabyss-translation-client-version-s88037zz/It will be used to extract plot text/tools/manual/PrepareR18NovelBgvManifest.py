import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


REMOTE_TOKEN = "{Absf.Asset.AddressableAssets.AddressablesProfileDefine.RemoteLoadPath}"
SCRIPT_ID_RE = re.compile(r"hmr_\d+_bgv", re.IGNORECASE)
CHARA_RE = re.compile(r"chara_(\d+)", re.IGNORECASE)


def text(value: Any) -> str:
    return "" if value is None else str(value)


def is_r18_novel_bgv(primary_key: str) -> bool:
    lowered = primary_key.lower().replace("\\", "/")
    return (
        lowered.endswith(".bundle")
        and "r18-only" in lowered
        and "workunit_novel_r18_backgroundvoice" in lowered
        and "_bgv.acb_" in lowered
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a manifest for DotAbyss r18 novel BGV ACB bundles.")
    parser.add_argument("--assets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.assets).read_text(encoding="utf-8"))
    rows = []
    seen = set()
    for asset in data.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        primary_key = text(asset.get("primary_key"))
        internal_id = text(asset.get("internal_id"))
        if not is_r18_novel_bgv(primary_key):
            continue
        if REMOTE_TOKEN not in internal_id:
            continue
        if primary_key in seen:
            continue
        seen.add(primary_key)

        script_ids = SCRIPT_ID_RE.findall(primary_key)
        chara = CHARA_RE.search(primary_key)
        rows.append(
            {
                "primary_key": primary_key,
                "internal_id": internal_id,
                "bundle_size": text(asset.get("bundle_size")),
                "hash": text(asset.get("hash")),
                "crc": text(asset.get("crc")),
                "script_id": script_ids[-1] if script_ids else "",
                "chara_id": chara.group(1) if chara else "",
            }
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["primary_key", "internal_id", "bundle_size", "hash", "crc", "script_id", "chara_id"]
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_size = sum(int(row["bundle_size"] or 0) for row in rows)
    print(f"R18 novel BGV ACB bundles: {len(rows)}")
    print(f"Total bytes: {total_size}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
