#!/usr/bin/env python3
"""把各來源的 <id>/zh_Hant.json 依前綴合併成 novels_<prefix>_all/zh_Hant.json。

來源見 SOURCE_DIRS：novels/（已上線）＋ novels_untranslated_only/（尚未上線）。
兩者合進同一批分包，未上線內容一旦上線就自動有翻譯，mod 端不需任何改動。

目的：讓漢化插件在啟動時「一次」抓整包劇情文本，取代開劇情才逐檔抓 raw，
藉此消除 raw.githubusercontent 的 429 限流（中間方案，不需版本更新器）。

依 novelId 前綴（evs / hmn / hmr / mas / men）分成數包，避免最大的 hmr（400+ 檔）
擠成單一大檔，也讓各類別能獨立更新。只處理繁中 zh_Hant。

輸出：
  novels_<prefix>_all/zh_Hant.json  —— { novelId: { 原文: 譯文, ... }, ... } 緊湊 JSON
並把每包的 MD5 寫進 manifest/zh_Hant.json 的 "novels_<prefix>_all" 欄位，
供插件端做快取比對、命中就不重抓。

用法：在 client-version 資料夾根目錄執行 `python3 tools/build_novels_all.py`
（GitHub Actions 也可直接呼叫，把產出的 novels_*_all/ 一起 commit 或打進 release）。
"""
import hashlib
import json
import os
import sys
from collections import defaultdict

LANG = "zh_Hant"

# 腳本位於 <root>/tools/，資料根目錄是上一層
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "manifest", LANG + ".json")

# 來源資料夾（依序掃描，後者不覆蓋前者已有的 novelId）
#   novels/                   —— 已上線的劇情
#   novels_untranslated_only/ —— 官方尚未上線的劇情，先譯好放著；
#                                合進同樣的 novels_<prefix>_all 分包，
#                                內容一上線就自動有翻譯，不必再改 mod。
#                                未上線的 novelId 遊戲不會查詢，放著無害。
SOURCE_DIRS = ["novels", "novels_untranslated_only"]


def collect_by_prefix() -> dict[str, dict[str, dict]]:
    """掃 SOURCE_DIRS，依前綴分組。回傳 { prefix: { novelId: {原文:譯文} } }。"""
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    seen: dict[str, str] = {}  # novelId -> 來自哪個來源，用來偵測重複
    for src in SOURCE_DIRS:
        src_dir = os.path.join(ROOT, src)
        if not os.path.isdir(src_dir):
            print(f"  [warn] 來源資料夾不存在，略過：{src}", file=sys.stderr)
            continue
        count = 0
        for novel_id in sorted(os.listdir(src_dir)):
            if novel_id.startswith("."):
                continue  # 跳過 .git / .agents 等隱藏目錄
            novel_path = os.path.join(src_dir, novel_id)
            if not os.path.isdir(novel_path):
                continue  # 跳過 translation_rules.md 之類的雜項檔
            if "_" not in novel_id:
                print(f"  [warn] 略過無前綴的 id：{novel_id}", file=sys.stderr)
                continue
            if novel_id in seen:
                # 同一個 novelId 出現在兩個來源：以先掃到的（已上線）為準
                print(
                    f"  [warn] {novel_id} 同時存在於 {seen[novel_id]} 與 {src}，"
                    f"採用 {seen[novel_id]} 的版本",
                    file=sys.stderr,
                )
                continue
            lang_file = os.path.join(novel_path, LANG + ".json")
            if not os.path.isfile(lang_file):
                continue  # 沒有繁中就跳過
            try:
                with open(lang_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"  [warn] 跳過壞檔 {lang_file}: {e}", file=sys.stderr)
                continue
            if not isinstance(data, dict) or not data:
                continue
            prefix = novel_id.split("_", 1)[0]
            groups[prefix][novel_id] = data
            seen[novel_id] = src
            count += 1
        print(f"  來源 {src}/: {count} 篇")
    return groups


def write_bundle(prefix: str, bundle: dict[str, dict]) -> tuple[str, int, float]:
    """寫出 novels_<prefix>_all/zh_Hant.json。回傳 (md5, 條目數, 大小MB)。"""
    out_dir = os.path.join(ROOT, f"novels_{prefix}_all")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, LANG + ".json")
    # 緊湊、不轉義 CJK —— 與插件 SaveToFile(WriteIndented=false, UnsafeRelaxedJsonEscaping) 一致
    text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    raw = text.encode("utf-8")
    with open(out_path, "wb") as f:
        f.write(raw)
    entry_count = sum(len(v) for v in bundle.values())
    return hashlib.md5(raw).hexdigest(), entry_count, len(raw) / 1_048_576


def main() -> int:
    if not any(os.path.isdir(os.path.join(ROOT, s)) for s in SOURCE_DIRS):
        print(f"找不到任何來源資料夾：{SOURCE_DIRS}", file=sys.stderr)
        return 1

    groups = collect_by_prefix()
    if not groups:
        print("沒有可合併的繁中劇本檔", file=sys.stderr)
        return 1

    # 讀既有 manifest（存在才更新）
    manifest = None
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)

    for prefix in sorted(groups):
        bundle = groups[prefix]
        md5, entry_count, size_mb = write_bundle(prefix, bundle)
        key = f"novels_{prefix}_all"
        if manifest is not None:
            manifest[key] = md5
        print(
            f"{key}/{LANG}.json: {len(bundle)} 劇本 / {entry_count} 條 / "
            f"{size_mb:.2f} MB / md5={md5[:12]}…"
        )

    if manifest is not None:
        # 頂層 hash ＝「拿掉 hash 欄位後的最小化 JSON」的 md5。
        # 各包 md5 一改，這個總 hash 就得跟著重算，否則插件端比對會對不上。
        manifest.pop("hash", None)
        minified = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
        manifest["hash"] = hashlib.md5(minified.encode("utf-8")).hexdigest()
        # 一律 LF —— .gitattributes 對 *.json 設了 eol=lf
        with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(
            f"已更新 manifest：{os.path.relpath(MANIFEST_PATH, ROOT)}"
            f"（總 hash={manifest['hash'][:12]}…）"
        )
    else:
        print("（無 manifest/zh_Hant.json，插件端將不做 hash 比對）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
