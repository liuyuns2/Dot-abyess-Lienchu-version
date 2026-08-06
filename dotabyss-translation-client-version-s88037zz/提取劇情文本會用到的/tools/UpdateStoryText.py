import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from DotAbyss import AbyssDownloader


STORY_TABLES = {
    "m_chapters",
    "m_chapter_areas",
    "m_chapter_characters",
    "m_chapter_quests",
    "m_chapter_quest_sequences",
    "m_event_hunt_novel_restricts",
    "m_event_story_novels",
    "m_event_story_quests",
    "m_event_story_rewards",
    "m_event_story_stages",
    "m_event_training_novels",
    "m_novel_character_skins",
    "m_novel_characters",
    "m_novel_event_rewards",
    "m_novel_events",
    "m_novel_homes",
    "m_novel_main_chapters",
    "m_novel_mains",
    "m_novel_others",
    "m_novel_prologues",
    "m_texts",
}


def default_output_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "output"


def download_master_data(output_dir: Path) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    old_cwd = Path.cwd()
    os.chdir(output_dir)
    try:
        downloader = AbyssDownloader()
        info = downloader.get_version_info()
        if not info:
            raise RuntimeError("Failed to fetch version info.")

        versions = info.get("versions", {})
        downloader.master_ver = downloader._pick_version(
            versions,
            "resource",
            default="4",
        )

        if not downloader.handle_master_data():
            raise RuntimeError("Failed to download or parse MasterData.")

        return {
            "master_version": downloader.master_ver,
            "versions": versions,
        }
    finally:
        os.chdir(old_cwd)


def extract_story_text(output_dir: Path, metadata: Dict[str, Any]) -> Path:
    master_path = output_dir / "MasterData.json"
    if not master_path.exists():
        raise FileNotFoundError(f"Missing MasterData.json: {master_path}")

    with master_path.open("r", encoding="utf-8") as f:
        master_data = json.load(f)

    tables = {
        table_name: master_data.get(table_name, [])
        for table_name in sorted(STORY_TABLES)
        if table_name in master_data
    }

    export_data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(master_path),
        "metadata": metadata,
        "tables": tables,
    }

    out_path = output_dir / "StoryText.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update DotAbyss MasterData and extract story-related tables."
    )
    parser.add_argument(
        "--output",
        default=str(default_output_dir()),
        help="Output directory. Defaults to the sibling output directory.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Only extract StoryText.json from an existing MasterData.json.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    metadata: Dict[str, Any] = {}

    if not args.skip_download:
        metadata = download_master_data(output_dir)

    out_path = extract_story_text(output_dir, metadata)
    print(f"Story text exported: {out_path}")


if __name__ == "__main__":
    main()
