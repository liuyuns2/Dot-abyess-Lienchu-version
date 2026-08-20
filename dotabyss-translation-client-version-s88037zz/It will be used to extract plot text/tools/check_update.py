#!/usr/bin/env python3
"""DotAbyss 官方更新探針。

比對兩個獨立訊號與 baseline.json，印出人可讀的結論，並更新 baseline。

  1. 官方 /version 端點（最權威）-> AssetVersionAndroidDmmR18 / resource
     資產版本變了 = 內容更新真的上線了（劇情、角色、活動）。
     resource 變了 = masterdata 換版，UI／系統文字（B 產線）有新資料。
  2. DMM freeapp API -> APK 版本（app_version_code / app_version_name）
     變了 = 客戶端改版，Android 端要「完整重打包」而不是 --reinject。
  3. DotAbyss/Masterdata mirror -> HEAD commit（第三方鏡像，會比官方晚）
     commit message 就是 resource 版號，可跟訊號 1 交叉驗證。

用法:
    python check_update.py            # 比對並更新 baseline
    python check_update.py --peek     # 只看，不寫 baseline
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "update_baseline.json"   # 見同層 .gitignore，不進版控
TZ = timezone(timedelta(hours=8))  # 台灣

DMM_API = "https://api.store.games.dmm.com/freeapp/771484"
MD_API = "https://api.github.com/repos/DotAbyss/Masterdata/commits/main"
UA = {"User-Agent": "dotabyss-update-watch"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def probe():
    out = {"checked_at": datetime.now(TZ).isoformat(timespec="seconds")}
    try:
        import probe_official
        out["official"] = probe_official.fetch()
    except Exception as exc:
        out["official_error"] = str(exc)
    try:
        a = get(DMM_API)["free_appinfo"]
        out["apk_version_code"] = a["app_version_code"]
        out["apk_version_name"] = a["app_version_name"]
        out["apk_file_size"] = a["file_size"]
        out["apk_download_url"] = a["download_url"]
    except Exception as exc:
        out["dmm_error"] = str(exc)
    try:
        c = get(MD_API)
        out["masterdata_sha"] = c["sha"]
        out["masterdata_date"] = c["commit"]["committer"]["date"]
        out["masterdata_msg"] = c["commit"]["message"].splitlines()[0]
    except Exception as exc:
        out["masterdata_error"] = str(exc)
    return out


def main():
    peek = "--peek" in sys.argv
    now = probe()
    old = json.loads(BASELINE.read_text("utf-8")) if BASELINE.is_file() else {}

    changed = []
    if old:
        o_new, o_old = now.get("official") or {}, old.get("official") or {}
        for k in ("AssetVersionAndroidDmmR18", "AssetVersionStandaloneDmmR18",
                  "AssetVersionWebDmmR18", "resource", "ClientVersionAndroidDmmR18"):
            if o_new.get(k) != o_old.get(k):
                changed.append(f"官方 {k}: {o_old.get(k)} -> {o_new.get(k)}")
        if now.get("apk_version_code") != old.get("apk_version_code"):
            changed.append(
                f"APK 版本 {old.get('apk_version_name')} (code {old.get('apk_version_code')})"
                f" -> {now.get('apk_version_name')} (code {now.get('apk_version_code')})"
            )
        if now.get("masterdata_sha") != old.get("masterdata_sha"):
            changed.append(
                f"Masterdata {str(old.get('masterdata_sha'))[:12]} -> "
                f"{str(now.get('masterdata_sha'))[:12]}"
                f"  ({now.get('masterdata_date')} / {now.get('masterdata_msg')})"
            )

    o = now.get("official") or {}
    print(f"探測時間（台灣）: {now['checked_at']}")
    print(f"  官方 Asset  : Android={o.get('AssetVersionAndroidDmmR18')}"
          f"  Standalone={o.get('AssetVersionStandaloneDmmR18')}"
          f"  Web={o.get('AssetVersionWebDmmR18')}")
    print(f"  官方 resource / client : {o.get('resource')}"
          f" / {o.get('ClientVersionAndroidDmmR18')}")
    print(f"  APK        : {now.get('apk_version_name')}  code={now.get('apk_version_code')}"
          f"  {now.get('apk_file_size')}MB")
    print(f"  Masterdata : {str(now.get('masterdata_sha'))[:12]}  {now.get('masterdata_date')}"
          f"  「{now.get('masterdata_msg')}」")
    for k in ("official_error", "dmm_error", "masterdata_error"):
        if now.get(k):
            print(f"  !! {k}: {now[k]}")

    if not old:
        print("\n[BASELINE] 沒有舊 baseline，這次只建立基準。")
    elif changed:
        print("\n[CHANGED] 有更新：")
        for line in changed:
            print("  -", line)
    else:
        print("\n[NO-CHANGE] 與上次探測完全相同。")
        print(f"  上次探測: {old.get('checked_at')}")

    if not peek:
        BASELINE.write_text(json.dumps(now, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if changed or not old else 2


if __name__ == "__main__":
    raise SystemExit(main())
