#!/usr/bin/env python3
"""推電腦版翻譯一條龍：重建劇情包 → 更新 manifest → 只暫存資料資料夾 → 比對暫存區 md5 → commit / push → CDN。

以前每次手動串六個指令，最容易漏的是 update_manifest 和「拿暫存區 blob 比 md5」。

  python tools/publish.py                                   # 只做到暫存 + 驗證，印出會提交什麼
  python tools/publish.py -m "2026-11-21 masterdata 95" --push   # 驗證過才 commit、push、verify_cdn --purge

只暫存下列資料夾（絕不 git add -A）；劇情來源有改才重建 novels_*_all。
提交訊息原樣使用；要加 trailer 用 --trailer（可重複）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = ["static", "ui_texts", "names", "add-on", "other", "novels", "novels_untranslated_only",
             "manifest"]
NOVEL_SOURCES = ("novels/", "novels_untranslated_only/")


def git(*args, check=True, capture=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=capture)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} 失敗：{r.stderr.decode('utf-8', 'replace')}")
    return r.stdout


def changed(paths):
    """回傳相對 git 最上層的路徑（-z：不加引號、不跳脫中文）。"""
    out = git("status", "--porcelain", "-z", "-uall", "--", *paths).decode("utf-8")
    entries = out.split("\0")
    files, i = [], 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if not e:
            continue
        if e[0] in "RC":
            i += 1          # rename/copy：下一個欄位是舊路徑
        files.append(e[3:])
    return files


def run(script):
    print(f"\n── {script}")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / script)], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"{script} 失敗（exit {r.returncode}）")


def manifest_paths(m):
    for k, v in m.items():
        if k == "hash":
            continue
        if isinstance(v, dict):
            folder = {"add_on": "add-on", "other": "other"}[k]
            for sub, h in v.items():
                yield f"{folder}/{sub}/zh_Hant.json", h
        else:
            yield f"{k}/zh_Hant.json", v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message")
    ap.add_argument("--trailer", action="append", default=[])
    ap.add_argument("--push", action="store_true", help="驗證通過後 commit + push + verify_cdn --purge")
    a = ap.parse_args()
    if a.push and not a.message:
        ap.error("--push 需要 -m 提交訊息（格式：YYYY-MM-DD masterdata NN）")

    pending = changed(DATA_DIRS)
    if not pending:
        print("資料資料夾沒有任何變動，不用推。")
        return 0
    prefix = git("rev-parse", "--show-prefix").decode().strip()
    if any(p[len(prefix):].startswith(NOVEL_SOURCES) for p in pending):
        run("build_novels_all.py")
    run("update_manifest.py")

    files = changed(DATA_DIRS + [d.name for d in ROOT.glob("novels_*_all")])
    git("add", "--", *(f":(top){f}" for f in files))

    # 暫存區 blob 才是玩家會下載的內容（Windows 工作區是 CRLF，不能拿工作區比）
    manifest = json.loads(git("show", ":./manifest/zh_Hant.json"))
    bad = []
    for path, h in manifest_paths(manifest):
        blob = subprocess.run(["git", "show", f":./{path}"], cwd=ROOT, capture_output=True)
        if blob.returncode != 0:
            continue   # 空的 other/* 之類不在 git 裡
        if hashlib.md5(blob.stdout).hexdigest() != h:
            bad.append(path)
    print(f"\n暫存 {len(files)} 個檔案：")
    for f in files[:30]:
        print("  " + f)
    if len(files) > 30:
        print(f"  …另有 {len(files) - 30} 個")
    if bad:
        print("\n✗ 暫存區內容與 manifest md5 不符：\n  " + "\n  ".join(bad))
        return 1
    print("✓ 暫存區 md5 與 manifest 全部一致")

    if not a.push:
        print("\n（沒加 --push，只做到暫存。確認無誤後加 -m \"...\" --push）")
        return 0
    msg = a.message + ("\n\n" + "\n".join(a.trailer) if a.trailer else "")
    git("commit", "-q", "-m", msg)
    git("push", "-q")
    print("\n已推送：" + git("log", "--oneline", "-1").decode().strip())
    print("\n── verify_cdn.py --purge（還有 ✗ 就 1～2 小時後再跑，全部 ✓ 才算完成）")
    subprocess.run([sys.executable, str(ROOT / "tools" / "verify_cdn.py"), "--purge"], cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
