import argparse
import csv
from pathlib import Path
from typing import Any

from json_stream import iter_json_array


REMOTE_TOKEN = "{Absf.Asset.AddressableAssets.AddressablesProfileDefine.RemoteLoadPath}"


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def is_text_novel_bundle(primary_key: str) -> bool:
    lowered = primary_key.lower()
    return primary_key.endswith(".bundle") and ".txt_" in lowered and (
        "_novel_" in lowered or "r18-only_novel" in lowered
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a download manifest containing only novel text bundles.")
    parser.add_argument("--assets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    assets_path = Path(args.assets)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # assets.json 是 ~390MB／12 萬筆，這裡只挑得出幾百筆劇情 bundle。
    # 原本 read_text() + json.loads() 會先有一份 390MB 字串再疊一份解析後的物件，
    # 是整條產線最吃 RAM 的地方之一；改成逐筆串流。
    rows = []
    for asset in iter_json_array(assets_path, "assets"):
        if not isinstance(asset, dict):
            continue
        primary_key = as_text(asset.get("primary_key"))
        internal_id = as_text(asset.get("internal_id"))
        if not is_text_novel_bundle(primary_key):
            continue
        if REMOTE_TOKEN not in internal_id:
            continue
        rows.append(
            {
                "primary_key": primary_key,
                "internal_id": internal_id,
                "bundle_size": as_text(asset.get("bundle_size")),
                "hash": as_text(asset.get("hash")),
                "crc": as_text(asset.get("crc")),
            }
        )

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["primary_key", "internal_id", "bundle_size", "hash", "crc"],
        )
        writer.writeheader()
        writer.writerows(rows)

    total_size = sum(int(row["bundle_size"] or 0) for row in rows)
    print(f"Text novel bundles: {len(rows)}")
    print(f"Total bytes: {total_size}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
