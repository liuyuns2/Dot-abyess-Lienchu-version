#!/usr/bin/env python3
"""驗證「玩家實際下載到的內容」是否等於 repo 現況，必要時清 jsDelivr 快取。

## 為什麼需要這支

`update_manifest.py` 只保證 **repo 內部** 一致（manifest 的 md5 對得上檔案）。
但玩家拿到的不是 repo，是 **CDN**：

    AbyssMod.cfg 的 CDN 設 raw.githubusercontent.com
      → AbyssCdnRouter.dll 會把網址改寫成 cdn.jsdelivr.net/gh/...
        → jsDelivr 對「分支 ref」有快取（s-maxage=43200，最長 12 小時）

所以 push 完、manifest 全綠，玩家還是可能拿到**幾個 commit 前**的檔案。
兩種後果嚴重程度差很多：

| 檔案 | 執行期有無 md5 驗證 | 陳舊時的下場 |
|---|---|---|
| `names` / `ui_texts` / `add-on` / `other` | **有**（AbyssMod 比對 manifest） | 驗證失敗 → 退回本機舊快取，log 有 `Remote fetch failed` |
| `static` | **沒有**（AbyssStaticFix 抓完直接注入） | **靜默**注入舊 bundle，畫面一片日文，log 只印 `Injected N m_* tables` |

`static` 那條是真正的殺手：沒有任何錯誤訊息。

> 🩸 **2026-08-10 實際事故。** 18:43 推上【水着】ホノカ 的技能說明與角色名，
> 19:09 實機仍是日文。原因不在庫裡——查 `static/zh_Hant.json` 兩筆譯文都在。
> 是 jsDelivr 還在餵舊檔：
>   - `names` 給 609 條（新版 611），md5 對不上 → 退回舊快取 → 角色名沒翻
>   - `static` 給 128 表版本（新版 131），`m_character_action_skills/description`
>     只有 124 條 → 缺巻貝百華那幾條 → 技能說明沒翻
> 指紋：log 的 `Injected 127 m_* tables` 正好是舊版 static 的非空表數
> （現行版是 130）。當時 dump 也同步記下 `【水着】ホノカ` 與技能說明原句查無翻譯。

## 用法

    python tools/verify_cdn.py                  # 只檢查，有陳舊 exit 1
    python tools/verify_cdn.py --purge          # 檢查 → 清 jsDelivr → 重驗
    python tools/verify_cdn.py --fast           # 只驗 manifest/names/ui_texts/static
    python tools/verify_cdn.py --repo owner/name --branch main

**push 之後一定要跑一次**（見 HANDOVER.md 第 3、4 節）。

## 清了還是舊的？

jsDelivr 的 purge 只清 Fastly/Cloudflare 邊緣，**清不掉它自己那層「分支 → commit」
的解析快取**。實測 purge 回 `finished`、`x-cache: MISS`，內容照樣是舊的。
這種情況只有兩條路：

1. 等（分支 ref 最長 12 小時會自己過期）。
2. **把 CDN 釘在 commit SHA**——SHA 形式的網址不吃分支快取，實測立刻正確。
   本工具偵測到這種狀況會直接印出可貼進 `AbyssMod.cfg` 的網址。

⚠️ 釘 SHA 之後每次改版都要換，不要長期留著。
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

LANG = "zh_Hant"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest" / f"{LANG}.json"

DEFAULT_REPO = "liuyuns2/Dot-abyess-Lienchu-version"
DEFAULT_BRANCH = "main"

# 只有 static 在執行期沒有 md5 驗證，陳舊時完全無聲，故單獨標記
SILENT_ON_STALE = {"static"}

# --fast 模式驗這幾個：改版時最常動、且涵蓋「角色名 / UI / masterdata」三條路
FAST_KEYS = {"manifest", "names", "ui_texts", "static"}

TIMEOUT = 180
UA = {"User-Agent": "verify_cdn.py (+dotabyss localization)"}


def md5_bytes(raw: bytes) -> str:
    # 一律正規化成 LF 再算：.gitattributes 對 *.json 設了 eol=lf，
    # git blob 與 CDN 服務的都是 LF，工作區在 Windows 上常是 CRLF。
    return hashlib.md5(raw.replace(b"\r\n", b"\n")).hexdigest()


def compact_manifest_hash(manifest: dict) -> str:
    payload = {k: v for k, v in manifest.items() if k != "hash"}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def manifest_targets(manifest: dict) -> list[tuple[str, str, str]]:
    """列出要驗的 (顯示名, repo 相對路徑, 期望 md5)。

    manifest 自己也要驗——它若陳舊，玩家會拿舊 hash 去比對新檔案，
    結果是「每個檔都驗證失敗」，比單一檔案陳舊更慘。
    """
    targets: list[tuple[str, str, str]] = [
        ("manifest", f"manifest/{LANG}.json", md5_bytes(MANIFEST_PATH.read_bytes()))
    ]
    for key, value in manifest.items():
        if key == "hash":
            continue
        if isinstance(value, str):
            targets.append((key, f"{key}/{LANG}.json", value))
        elif isinstance(value, dict):
            # manifest 的 add_on 對應磁碟上的 add-on/
            folder = "add-on" if key == "add_on" else key
            for sub, digest in value.items():
                targets.append((f"{key}.{sub}", f"{folder}/{sub}/{LANG}.json", digest))
    return targets


def check_local(targets: list[tuple[str, str, str]]) -> list[str]:
    """先確認 repo 自己是一致的——不然驗 CDN 沒有意義。"""
    bad = []
    for name, rel, expected in targets:
        if name == "manifest":
            continue
        path = ROOT / rel
        if not path.is_file():
            bad.append(f"{name}: 檔案不存在（{rel}）")
            continue
        actual = md5_bytes(path.read_bytes())
        if actual != expected:
            bad.append(f"{name}: manifest={expected} 檔案={actual}")
    return bad


def fetch(url: str) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(), dict(resp.headers)


def purge(repo: str, branch: str, folder: str, rel: str) -> str:
    url = f"https://purge.jsdelivr.net/gh/{repo}@{branch}/{folder}/{rel}"
    try:
        body, _ = fetch(url)
        return json.loads(body.decode("utf-8", "replace")).get("status", "?")
    except Exception as exc:  # noqa: BLE001 — 清快取失敗不該中斷驗證
        return f"error: {exc}"


def probe(repo: str, branch: str, folder: str, rel: str, expected: str) -> dict:
    """抓 raw 與 jsDelivr 各一份，回報是否與期望的 md5 相符。"""
    result = {}
    sources = {
        "raw": f"https://raw.githubusercontent.com/{repo}/refs/heads/{branch}/{folder}/{rel}",
        "jsdelivr": f"https://cdn.jsdelivr.net/gh/{repo}@{branch}/{folder}/{rel}",
    }
    for label, url in sources.items():
        try:
            body, headers = fetch(url)
            result[label] = {
                "md5": md5_bytes(body),
                "ok": md5_bytes(body) == expected,
                "size": len(body),
                "age": headers.get("age") or headers.get("Age") or "-",
            }
        except Exception as exc:  # noqa: BLE001
            result[label] = {"md5": None, "ok": False, "error": str(exc)}
    return result


def parse_opt(argv: list[str], flag: str, default: str) -> str:
    for i, arg in enumerate(argv):
        if arg == flag:
            if i + 1 >= len(argv):
                print(f"{flag} 後面要接值", file=sys.stderr)
                raise SystemExit(2)
            return argv[i + 1]
        if arg.startswith(flag + "="):
            return arg.split("=", 1)[1]
    return default


def head_sha(repo: str, branch: str) -> str | None:
    try:
        body, _ = fetch(f"https://api.github.com/repos/{repo}/commits/{branch}")
        return json.loads(body.decode("utf-8"))["sha"]
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    argv = sys.argv[1:]
    do_purge = "--purge" in argv
    fast = "--fast" in argv
    repo = parse_opt(argv, "--repo", DEFAULT_REPO)
    branch = parse_opt(argv, "--branch", DEFAULT_BRANCH)
    folder = parse_opt(argv, "--dir", ROOT.name)

    if not MANIFEST_PATH.is_file():
        print(f"找不到 manifest：{MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    targets = manifest_targets(manifest)
    if fast:
        targets = [t for t in targets if t[0] in FAST_KEYS]

    print(f"repo: {repo}@{branch}  資料夾: {folder}")
    print(f"驗 {len(targets)} 個檔案（--fast 只驗 4 個）\n")

    # 0. manifest 頂層 hash 自我一致
    want = compact_manifest_hash(manifest)
    if manifest.get("hash") != want:
        print(f"✗ manifest.hash 與內容不符：檔內={manifest.get('hash')} 應為={want}")
        print("  → 先跑 python tools/update_manifest.py")
        return 1

    # 1. repo 自己要先一致（CRLF 陷阱在這裡就會現形）
    local_bad = check_local(targets)
    if local_bad:
        print("✗ repo 內部就不一致，先修這個再談 CDN：")
        for line in local_bad:
            print("   ", line)
        print("  → python tools/update_manifest.py")
        return 1
    print("✓ repo 內部一致（manifest md5 == 檔案內容，已正規化 LF）\n")

    # 2. 驗 CDN
    stale_js: list[tuple[str, str, str]] = []
    rows = []
    for name, rel, expected in targets:
        res = probe(repo, branch, folder, rel, expected)
        rows.append((name, rel, expected, res))
        if not res["jsdelivr"]["ok"]:
            stale_js.append((name, rel, expected))

    def show(rows_):
        for name, rel, expected, res in rows_:
            mark = {k: ("✓" if v["ok"] else "✗") for k, v in res.items()}
            note = " ⚠ 執行期無驗證，陳舊時完全無聲" if name in SILENT_ON_STALE and not res["jsdelivr"]["ok"] else ""
            print(f"  raw {mark['raw']}  jsDelivr {mark['jsdelivr']}  {name:24} {rel}{note}")
            for label in ("raw", "jsdelivr"):
                info = res[label]
                if not info["ok"]:
                    if info.get("error"):
                        print(f"        {label}: 取不到 —— {info['error']}")
                    else:
                        print(
                            f"        {label}: md5={info['md5']} 應為={expected}"
                            f" size={info['size']} age={info['age']}"
                        )

    show(rows)

    raw_bad = [r for r in rows if not r[3]["raw"]["ok"]]
    if raw_bad:
        print("\n✗ raw.githubusercontent 就已經不對——表示東西沒推上去（或推到別的分支）。")
        print("  → git status / git log origin/%s -1，確認 commit 真的 push 了。" % branch)
        return 1

    if not stale_js:
        print("\n✓ raw 與 jsDelivr 都等於 repo 現況，玩家重開遊戲就會拿到正確翻譯。")
        return 0

    print(f"\n✗ jsDelivr 有 {len(stale_js)} 個檔案陳舊。")
    if not do_purge:
        print("  → 加 --purge 清快取後重驗。")
        return 1

    print("\n清 jsDelivr 快取：")
    for name, rel, _ in stale_js:
        print(f"  {purge(repo, branch, folder, rel):10} {name}")

    print("\n重驗：")
    rows2 = []
    for name, rel, expected in stale_js:
        res = probe(repo, branch, folder, rel, expected)
        rows2.append((name, rel, expected, res))
    show(rows2)

    still = [r for r in rows2 if not r[3]["jsdelivr"]["ok"]]
    if not still:
        print("\n✓ 清完已一致。")
        return 0

    # purge 清不掉 jsDelivr 自己那層「分支 → commit」解析快取
    print(f"\n✗ 清完仍有 {len(still)} 個陳舊：{'、'.join(r[0] for r in still)}")
    print("  這是 jsDelivr 的分支 ref 解析快取，purge 清不到，最長 12 小時自己過期。")
    sha = head_sha(repo, branch)
    if sha:
        print("\n  要立刻生效就把 CDN 釘在 commit SHA（SHA 網址不吃分支快取）。")
        print("  AbyssMod.cfg → [Translation] CDN =")
        print(f"    https://cdn.jsdelivr.net/gh/{repo}@{sha}/{folder}")
        print("  ⚠️ 這是臨時手段，下次改版記得改回分支形式。")
    print("\n  另外注意：static 陳舊不會有任何錯誤訊息，別以為沒 log 就是好了。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
