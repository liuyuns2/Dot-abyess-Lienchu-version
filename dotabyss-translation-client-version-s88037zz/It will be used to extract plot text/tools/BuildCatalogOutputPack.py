import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


SCRIPT_ID_RE = re.compile(r"(?:mas|hmn|hmr|men|evs)_\d+", re.IGNORECASE)


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: as_text(row.get(field)) for field in fields})


def flatten_asset(asset: dict[str, Any]) -> dict[str, Any]:
    resource_type = asset.get("resource_type") or {}
    common_info = asset.get("common_info") or {}
    primary_key = str(asset.get("primary_key") or "")
    internal_id = str(asset.get("internal_id") or "")
    script_ids = SCRIPT_ID_RE.findall(primary_key)
    script_id = script_ids[-1] if script_ids else ""

    return {
        "primary_key": primary_key,
        "internal_id": internal_id,
        "provider_id": asset.get("provider_id"),
        "resource_class": resource_type.get("class_name"),
        "resource_assembly": resource_type.get("assembly_name"),
        "bundle_name": asset.get("bundle_name"),
        "bundle_size": asset.get("bundle_size"),
        "crc": asset.get("crc"),
        "hash": asset.get("hash"),
        "hash_code": asset.get("hash_code"),
        "dependency_hash_code": asset.get("dependency_hash_code"),
        "dependency_key": asset.get("dependency_key"),
        "asset_load_mode": common_info.get("asset_load_mode"),
        "use_unity_web_request_for_local_bundles": common_info.get("use_unity_web_request_for_local_bundles"),
        "script_id": script_id,
        "script_prefix": script_id.split("_", 1)[0] if script_id else "",
        "is_bundle": primary_key.endswith(".bundle"),
        "is_text_novel_bundle": is_text_novel_bundle(primary_key),
        "is_r18": "r18" in primary_key.lower() or "r18" in internal_id.lower(),
        "is_novel": "novel" in primary_key.lower() or "novel" in internal_id.lower(),
    }


def is_text_novel_bundle(primary_key: str) -> bool:
    lowered = primary_key.lower()
    return primary_key.endswith(".bundle") and ".txt_" in lowered and (
        "_novel_" in lowered or "r18-only_novel" in lowered
    )


def build_categories(rows: list[dict[str, Any]]) -> dict[str, Callable[[dict[str, Any]], bool]]:
    return {
        "all_bundles": lambda row: str(row["primary_key"]).endswith(".bundle"),
        "remote_or_local_manifest": lambda row: str(row["primary_key"]).endswith(".bundle"),
        "novel_related": lambda row: bool(row["is_novel"]),
        "text_novel_bundles": lambda row: bool(row["is_text_novel_bundle"]),
        "r18_related": lambda row: bool(row["is_r18"]),
        "hmr_related": lambda row: "hmr_" in str(row["primary_key"]).lower()
        or "hmr_" in str(row["internal_id"]).lower(),
        "voice_novel": lambda row: "novel_voice" in str(row["primary_key"]).lower()
        or "novel_voice" in str(row["internal_id"]).lower(),
        "sound_related": lambda row: any(
            token in str(row["primary_key"]).lower()
            for token in ("sound", ".acb_", ".awb_", "cri_")
        ),
        "live2d_related": lambda row: any(
            token in str(row["primary_key"]).lower()
            for token in ("live2d", "_l2d_", "addanimations", ".fade.", "motion")
        ),
        "image_related": lambda row: any(
            token in str(row["primary_key"]).lower()
            for token in (".png_", ".jpg_", ".jpeg_", ".texture", "icon", "image")
        ),
        "prefab_related": lambda row: ".prefab_" in str(row["primary_key"]).lower(),
        "masterdata_or_table_related": lambda row: any(
            token in str(row["primary_key"]).lower()
            for token in ("masterdata", "master-data", "table", "scenario")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an organized output pack from parsed catalog assets.json.")
    parser.add_argument("--assets", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    assets_path = Path(args.assets)
    output_dir = Path(args.output)
    categories_dir = output_dir / "categories"
    script_dir = output_dir / "script_ids"
    grouped_dir = output_dir / "grouped"
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(assets_path.read_text(encoding="utf-8"))
    assets = data.get("assets") or []
    rows = [flatten_asset(asset) for asset in assets]

    fields = [
        "primary_key",
        "internal_id",
        "provider_id",
        "resource_class",
        "bundle_name",
        "bundle_size",
        "crc",
        "hash",
        "hash_code",
        "dependency_hash_code",
        "dependency_key",
        "asset_load_mode",
        "use_unity_web_request_for_local_bundles",
        "script_id",
        "script_prefix",
        "is_bundle",
        "is_text_novel_bundle",
        "is_r18",
        "is_novel",
    ]

    write_json(output_dir / "catalog_info.json", data.get("catalog_info") or {})
    write_json(output_dir / "provider_data.json", data.get("provider_data") or {})
    write_json(output_dir / "source_statistics.json", data.get("statistics") or {})
    write_csv(output_dir / "all_assets.csv", rows, fields)

    categories = build_categories(rows)
    category_counts: dict[str, int] = {}
    for name, predicate in categories.items():
        selected = [row for row in rows if predicate(row)]
        category_counts[name] = len(selected)
        write_csv(categories_dir / f"{name}.csv", selected, fields)
        write_lines(categories_dir / f"{name}_primary_keys.txt", [row["primary_key"] for row in selected])

    text_rows = [row for row in rows if row["is_text_novel_bundle"]]
    by_script: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in text_rows:
        by_script[row["script_id"] or "_no_script_id"].append(row)

    script_ids = sorted(script_id for script_id in by_script if script_id != "_no_script_id")
    write_lines(script_dir / "text_novel_script_ids.txt", script_ids)
    for prefix in ("evs", "hmn", "hmr", "mas", "men"):
        write_lines(
            script_dir / f"{prefix}_script_ids.txt",
            [script_id for script_id in script_ids if script_id.startswith(prefix + "_")],
        )

    grouped_text = {
        script_id: [
            {
                "primary_key": row["primary_key"],
                "internal_id": row["internal_id"],
                "bundle_size": row["bundle_size"],
                "hash": row["hash"],
                "crc": row["crc"],
            }
            for row in items
        ]
        for script_id, items in sorted(by_script.items())
    }
    write_json(grouped_dir / "text_novel_bundles_by_script_id.json", grouped_text)

    provider_counts = Counter(str(row["provider_id"]) for row in rows)
    prefix_counts = Counter(row["script_prefix"] for row in text_rows if row["script_prefix"])
    summary = {
        "catalog_info": data.get("catalog_info") or {},
        "total_assets": len(rows),
        "category_counts": category_counts,
        "provider_counts": dict(provider_counts.most_common()),
        "text_novel_script_count": len(script_ids),
        "text_novel_script_prefix_counts": dict(prefix_counts),
        "output_files": {
            "all_assets_csv": str(output_dir / "all_assets.csv"),
            "categories_dir": str(categories_dir),
            "script_ids_dir": str(script_dir),
            "grouped_text_novel_by_script": str(grouped_dir / "text_novel_bundles_by_script_id.json"),
        },
    }
    write_json(output_dir / "summary.json", summary)

    md_lines = [
        "# windows_1916_catalog_1 output",
        "",
        "## Catalog",
    ]
    for key, value in (data.get("catalog_info") or {}).items():
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(["", "## Category Counts"])
    for key, value in sorted(category_counts.items()):
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(["", "## Text Novel Script Prefix Counts"])
    for key, value in sorted(prefix_counts.items()):
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(
        [
            "",
            "## Important Files",
            "- all_assets.csv",
            "- categories/text_novel_bundles.csv",
            "- categories/remote_or_local_manifest.csv",
            "- script_ids/text_novel_script_ids.txt",
            "- grouped/text_novel_bundles_by_script_id.json",
        ]
    )
    write_lines(output_dir / "README.md", md_lines)

    print(f"Output: {output_dir}")
    print(f"Total assets: {len(rows)}")
    print(f"Text novel bundles: {category_counts.get('text_novel_bundles', 0)}")
    print(f"Text novel script ids: {len(script_ids)}")


if __name__ == "__main__":
    main()
