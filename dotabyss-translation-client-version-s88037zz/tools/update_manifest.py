#!/usr/bin/env python3
"""Refresh non-novel translation hashes in manifest/zh_Hant.json.

This script updates:
- names
- ui_texts
- static
- add_on.*
- other.*
- manifest hash

Novel bundle hashes are owned by tools/build_novels_all.py.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


LANG = "zh_Hant"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest" / f"{LANG}.json"


def md5_file(path: Path) -> str:
    # git 以 LF 存放 blob（見 .gitattributes: *.json text eol=lf），raw.githubusercontent
    # 服務的也是 LF。若直接對工作區位元組做雜湊，Windows 上的 CRLF 檔會算出與玩家
    # 實際下載內容不符的 hash，導致 names/static 靜默載不進去。故一律正規化成 LF 再算。
    return hashlib.md5(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def compact_manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "hash"}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def zh_hant_file(directory: Path) -> Path | None:
    path = directory / f"{LANG}.json"
    return path if path.is_file() else None


def collect_nested_hashes(parent: Path) -> dict[str, str]:
    if not parent.is_dir():
        return {}

    hashes: dict[str, str] = {}
    for child in sorted(parent.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        lang_file = zh_hant_file(child)
        if lang_file is not None:
            hashes[child.name] = md5_file(lang_file)
    return hashes


def main() -> int:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"Manifest root must be an object: {MANIFEST_PATH}")

    top_level = {
        "names": ROOT / "names" / f"{LANG}.json",
        "ui_texts": ROOT / "ui_texts" / f"{LANG}.json",
        "static": ROOT / "static" / f"{LANG}.json",
    }
    for key, path in top_level.items():
        if path.is_file():
            manifest[key] = md5_file(path)

    manifest["add_on"] = collect_nested_hashes(ROOT / "add-on")
    manifest["other"] = collect_nested_hashes(ROOT / "other")
    manifest["hash"] = compact_manifest_hash(manifest)

    with MANIFEST_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=2))
        f.write("\n")

    print(f"Updated {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"manifest.hash={manifest['hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
