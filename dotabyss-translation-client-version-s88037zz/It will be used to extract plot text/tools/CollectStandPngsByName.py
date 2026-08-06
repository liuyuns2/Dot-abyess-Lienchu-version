import argparse
import csv
import re
import shutil
from pathlib import Path


RULES = [
    ("novel_chara_stands", re.compile(r"NovelCharaStand(\d+[GX]?)", re.IGNORECASE)),
    ("pre_gacha_character_stands", re.compile(r"PreGacha_CharaStand_S_(\d+[GX]?)", re.IGNORECASE)),
    ("enemy_stands", re.compile(r"Enemy_Stand_(\d+)", re.IGNORECASE)),
    ("chara_cutin", re.compile(r"CharaCutin(\d+[GX]?)", re.IGNORECASE)),
    ("story_thumbnails", re.compile(r"Story_S_(hmr_\d+)", re.IGNORECASE)),
]


INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(value: str, limit: int = 120) -> str:
    return INVALID_NAME_CHARS.sub("_", value).rstrip(". ")[:limit] or "asset"


def classify(path: Path) -> tuple[str, str] | None:
    for category, pattern in RULES:
        match = pattern.search(path.name)
        if match:
            return category, safe_name(match.group(1))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect stand-like PNGs by extracted file name.")
    parser.add_argument("--extracted", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    extracted = Path(args.extracted)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    seen_targets: set[Path] = set()
    per_asset_counts: dict[tuple[str, str], int] = {}

    for png in extracted.rglob("*.png"):
        classified = classify(png)
        if not classified:
            continue
        category, asset_id = classified
        bundle_name = png.parents[1].name if png.parent.name in {"Texture2D", "Sprite"} else png.parent.name
        target_dir = output / category / asset_id
        target_dir.mkdir(parents=True, exist_ok=True)
        key = (category, asset_id)
        per_asset_counts[key] = per_asset_counts.get(key, 0) + 1
        source_kind = png.parent.name if png.parent.name in {"Texture2D", "Sprite"} else "Image"
        target = target_dir / f"{asset_id}_{per_asset_counts[key]:03d}_{source_kind}.png"
        if target in seen_targets:
            continue
        shutil.copy2(png, target)
        seen_targets.add(target)
        rows.append(
            {
                "category": category,
                "asset_id": asset_id,
                "file": str(target),
                "source_png": str(png),
                "bundle_folder": bundle_name,
            }
        )
        counts[category] = counts.get(category, 0) + 1

    index_path = output / "filename_scan_index.csv"
    with index_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["category", "asset_id", "file", "source_png", "bundle_folder"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    lines = ["# Stand PNG Filename Scan", "", "## Counts"]
    for category, count in sorted(counts.items()):
        lines.append(f"- {category}: {count}")
    lines.append("")
    lines.append(f"Total: {len(rows)}")
    (output / "filename_scan_README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Output: {output}")
    print(f"Copied PNGs: {len(rows)}")
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")
    print(f"Index: {index_path}")


if __name__ == "__main__":
    main()
