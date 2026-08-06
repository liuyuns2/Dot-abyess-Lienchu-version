import argparse
import csv
import re
import shutil
from pathlib import Path


INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(value: str, limit: int = 160) -> str:
    value = INVALID_NAME_CHARS.sub("_", value.strip())
    value = value.rstrip(". ")
    return (value[:limit] or "asset")


def asset_id_from_key(primary_key: str) -> str:
    name = primary_key.rsplit("/", 1)[-1]
    name = re.sub(r"\.bundle$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_[0-9a-f]{32}$", "", name, flags=re.IGNORECASE)
    return safe_name(name, 120)


def category_for(row: dict[str, str]) -> str | None:
    text = ((row.get("primary_key") or "") + " " + (row.get("internal_id") or "")).lower()
    if "charastand" in text:
        return "character_stands"
    if "enemy_stand" in text or "enemy/stand" in text:
        return "enemy_stands"
    if "characutin" in text or "chara_cutin" in text:
        return "chara_cutin"
    if "story_s" in text:
        return "story_thumbnails"
    return None


def choose_pngs(bundle_dir: Path) -> list[Path]:
    texture_pngs = sorted((bundle_dir / "Texture2D").glob("*.png"))
    sprite_pngs = sorted((bundle_dir / "Sprite").glob("*.png"))
    if texture_pngs:
        return texture_pngs
    return sprite_pngs


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize extracted stand-like PNG assets.")
    parser.add_argument("--image-csv", required=True)
    parser.add_argument("--extracted", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    image_csv = Path(args.image_csv)
    extracted = Path(args.extracted)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    missing = 0

    with image_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            category = category_for(row)
            if not category:
                continue
            primary_key = row.get("primary_key") or ""
            if not primary_key.endswith(".bundle"):
                continue

            bundle_dir = extracted / primary_key
            if not bundle_dir.exists():
                missing += 1
                continue

            asset_id = asset_id_from_key(primary_key)
            pngs = choose_pngs(bundle_dir)
            if not pngs:
                continue

            target_dir = output / category / asset_id
            target_dir.mkdir(parents=True, exist_ok=True)
            for png in pngs:
                target = target_dir / safe_name(png.name, 180)
                shutil.copy2(png, target)
                index_rows.append(
                    {
                        "category": category,
                        "asset_id": asset_id,
                        "file": str(target),
                        "source_png": str(png),
                        "primary_key": primary_key,
                        "internal_id": row.get("internal_id") or "",
                        "bundle_size": row.get("bundle_size") or "",
                        "hash": row.get("hash") or "",
                    }
                )
                counts[category] = counts.get(category, 0) + 1

    index_path = output / "index.csv"
    fields = [
        "category",
        "asset_id",
        "file",
        "source_png",
        "primary_key",
        "internal_id",
        "bundle_size",
        "hash",
    ]
    with index_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(index_rows)

    readme = output / "README.md"
    lines = [
        "# Stand Images",
        "",
        "This folder collects stand-like PNG assets from the Windows 1916 catalog extraction.",
        "",
        "## Counts",
    ]
    for category, count in sorted(counts.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            f"- missing bundle folders: {missing}",
            "",
            "## Notes",
            "- `character_stands`: pre-registration/gacha character stand images.",
            "- `enemy_stands`: enemy stand images.",
            "- `chara_cutin`: character cut-in images, not always full-body stands.",
            "- `story_thumbnails`: HMR story thumbnail images, useful for story browsing but not true full-body stands.",
            "- `index.csv` maps each copied PNG back to its source bundle.",
        ]
    )
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Output: {output}")
    print(f"Copied PNGs: {len(index_rows)}")
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")
    print(f"Missing bundle folders: {missing}")
    print(f"Index: {index_path}")


if __name__ == "__main__":
    main()
