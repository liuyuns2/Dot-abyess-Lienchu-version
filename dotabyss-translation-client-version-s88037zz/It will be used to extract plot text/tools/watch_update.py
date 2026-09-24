#!/usr/bin/env python3
"""DotAbyss 更新通知：每小時問一次，有變化就跳通知。

為什麼需要這支：check_update.py 是「我現在想到就問一次」，
wait_for_update.sh 是「改版當天掛著跑」——但沒人知道哪天是改版日，
所以兩支都要人先想到才會動。2026-09-24 檢查時 baseline 還停在 resource 67，
官方已經走到 70；翻譯本身沒漏（commit bd86428d 當天就補完了），
但那代表這套探針在「有沒有新東西」這個問題上已經三天答不出來。
這支只解決這一件事：不必想到，也不會漏掉。

刻意不做高頻輪詢
----------------
偵測快 1 小時沒有價值。收到通知之後的流程（拉 masterdata、抽缺漏、
照 translation_rules.md 逐條翻、rebuild、update_manifest、push、verify_cdn --purge，
必要時整包重打 APK）本來就要數小時，而且翻譯這段依規矩不能自動化
（CLAUDE.md：沒有前例的名字是「要問」，不是「可翻」）。
所以每小時一次就夠，換來的是一週 168 次請求而不是 10,080 次。

成本（2026-09-24 實測）
----------------------
    官方 /version   1,136 B，Cache-Control: no-cache，沒有 ETag -> 無法條件請求，
                    但一次才 1 KB。台灣直連即可，不需要日本 VPN、不需要簽章。
                    每小時一次 = 27 KB/天。開一次遊戲的流量是這個的好幾百倍。
    DMM freeapp     4,518 B，Cache-Control: no-store -> 同樣只能硬打。
                    只決定「Android 要整包重打還是 --reinject」。
    GitHub mirror   有 ETag。帶 token 時 304 完全不計入 rate limit
                    （實測 X-RateLimit-Used 停在 4 不動，上限 5000/hr）；
                    不帶 token 的 304 會被計入，而上限只有 60/hr。
                    mirror 自己是每小時 cron（近 50 筆 commit 裡 43 筆落在
                    UTC 分鐘 02-03），所以它最慢比官方晚 1 小時，只能拿來交叉驗證。

一小時三個訊號加起來約 6 KB，一天 140 KB。這跟攻擊差了七、八個數量級，
但仍然比「想到才跑」可靠。

用法
----
    python watch_update.py              # 檢查一次就結束。exit 0=有更新 2=沒有 3=探測失敗
    python watch_update.py --plan       # 只印成本估算，完全不連線
    python watch_update.py --ack        # 我處理完了，停止提醒
    python watch_update.py --task       # 印出註冊 Windows 工作排程器的指令（不會自己執行）
    python watch_update.py --watch      # 不想用排程器的話，常駐每小時一次

通知不會漏掉
------------
氣泡只跳 30 秒，眼花就錯過了，所以偵測到更新後會把它記成一筆「未處理」，
之後每小時再叫一次，並印出已經擱了幾小時，直到你明確確認：

    python watch_update.py --ack        # 處理完了，別再叫

也就是說漏看一次不會有事，最多一小時後又會跳。
要更保險就設 DOTABYSS_WATCH_WEBHOOK（Discord webhook 網址），
通知會同時推到手機，那個是留在通知列不會自己消失的。

這支完全不會叫醒 Claude，也不花任何 LLM token——它是純 Python，
由工作排程器執行，跑幾秒就結束。
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_update as cu  # noqa: E402  共用 URL 與 baseline 路徑，避免兩份真相

# 排程器把輸出導進記錄檔時，Windows 預設的 cp950 會把中文寫成亂碼
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DETECTED = HERE / "update_detected.json"
ETAG_FILE = HERE / "update_etag.txt"
INTERVAL = 3600
WATCHED = ("AssetVersionAndroidDmmR18", "AssetVersionStandaloneDmmR18",
           "AssetVersionWebDmmR18", "resource", "ClientVersionAndroidDmmR18")


def say(msg):
    print(f"[{datetime.now(cu.TZ):%m-%d %H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------ 三個訊號

def probe_official():
    import probe_official as po
    return po.fetch()


def probe_dmm():
    a = cu.get(cu.DMM_API)["free_appinfo"]
    return {"apk_version_code": a["app_version_code"],
            "apk_version_name": a["app_version_name"],
            "apk_file_size": a["file_size"],
            "apk_download_url": a["download_url"]}


def github_token():
    """有 token 的話 304 不計入 rate limit，所以值得去撈一個。"""
    tk = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tk:
        return tk
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True,
                           text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def probe_masterdata(token):
    """回傳 dict；GitHub 答 304（內容沒變）時回傳 None。ETag 存檔，跨次有效。"""
    headers = dict(cu.UA)
    headers["Accept"] = "application/vnd.github+json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    old_etag = ETAG_FILE.read_text("utf-8").strip() if ETAG_FILE.is_file() else ""
    if old_etag:
        headers["If-None-Match"] = old_etag
    req = urllib.request.Request(cu.MD_API, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.headers.get("ETag"):
                ETAG_FILE.write_text(r.headers["ETag"], encoding="utf-8")
            c = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None
        raise
    return {"masterdata_sha": c["sha"],
            "masterdata_date": c["commit"]["committer"]["date"],
            "masterdata_msg": c["commit"]["message"].splitlines()[0]}


# ------------------------------------------------------------------ 比對與通知

def diff(fresh, old):
    out = []
    o_new, o_old = fresh.get("official") or {}, old.get("official") or {}
    for k in WATCHED:
        if k in o_new and o_new.get(k) != o_old.get(k):
            out.append(f"官方 {k}: {o_old.get(k)} -> {o_new.get(k)}")
    if "apk_version_code" in fresh and fresh["apk_version_code"] != old.get("apk_version_code"):
        out.append(f"APK {old.get('apk_version_name')} (code {old.get('apk_version_code')})"
                   f" -> {fresh['apk_version_name']} (code {fresh['apk_version_code']})"
                   "   ← 客戶端改版，Android 要完整重打包，不能只 --reinject")
    if "masterdata_sha" in fresh and fresh["masterdata_sha"] != old.get("masterdata_sha"):
        out.append(f"Masterdata {str(old.get('masterdata_sha'))[:12]} -> "
                   f"{fresh['masterdata_sha'][:12]}  「{fresh.get('masterdata_msg')}」")
    return out


def toast(title, body):
    """非阻塞的 Windows 氣泡通知。失敗就算了，不影響主流程。"""
    safe = body.replace("'", "").replace("`", "")[:180]
    ps = ("Add-Type -AssemblyName System.Windows.Forms;"
          "$n=New-Object System.Windows.Forms.NotifyIcon;"
          "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
          f"$n.ShowBalloonTip(30000,'{title}','{safe}','Info');"
          "Start-Sleep -Seconds 30;$n.Dispose()")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                          "-Command", ps],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notify_webhook(text):
    url = os.environ.get("DOTABYSS_WATCH_WEBHOOK")
    if not url:
        return
    try:
        req = urllib.request.Request(
            url, data=json.dumps({"content": text}).encode("utf-8"),
            headers={"Content-Type": "application/json", **cu.UA})
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as exc:
        say(f"!! webhook 送不出去: {exc}")


def announce(changes, state):
    print("\a", end="")
    say("=" * 60)
    say(">>> 偵測到官方更新")
    for line in changes:
        say("    " + line)
    say("    處理完請跑：python watch_update.py --ack")
    say("=" * 60)
    DETECTED.write_text(json.dumps(
        {"detected_at": datetime.now(cu.TZ).isoformat(timespec="seconds"),
         "acknowledged": False, "changes": changes, "state": state},
        ensure_ascii=False, indent=2), encoding="utf-8")
    toast("DotAbyss 更新了", changes[0])
    notify_webhook("**DotAbyss 更新了**\n```\n" + "\n".join(changes) + "\n```")


def outstanding():
    """還沒被確認的更新。氣泡只跳 30 秒，所以沒 --ack 之前每小時都要再叫一次。"""
    if not DETECTED.is_file():
        return None
    try:
        d = json.loads(DETECTED.read_text("utf-8"))
    except Exception:
        return None
    return None if d.get("acknowledged") else d


def remind(d):
    hours = (datetime.now(cu.TZ)
             - datetime.fromisoformat(d["detected_at"])).total_seconds() / 3600
    print("\a", end="")
    say(f">>> 還有沒處理的更新（{d['detected_at'][5:16]} 偵測到，擱了 {hours:.0f} 小時）")
    for line in d["changes"]:
        say("    " + line)
    say("    處理完請跑：python watch_update.py --ack")
    toast(f"DotAbyss 更新還沒處理（{hours:.0f} 小時）", d["changes"][0])
    notify_webhook(f"**DotAbyss 更新還沒處理（{hours:.0f} 小時）**\n```\n"
                   + "\n".join(d["changes"]) + "\n```")


def acknowledge():
    d = outstanding()
    if not d:
        say("目前沒有待處理的更新。")
        return 2
    d["acknowledged"] = True
    d["acknowledged_at"] = datetime.now(cu.TZ).isoformat(timespec="seconds")
    DETECTED.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    say(f"已確認 {d['detected_at'][5:16]} 那筆更新，不會再提醒。")
    return 0


# ------------------------------------------------------------------ 主流程

def check(token):
    """跑一輪。回傳 (變動清單, 是否探測失敗)。"""
    state = json.loads(cu.BASELINE.read_text("utf-8")) if cu.BASELINE.is_file() else {}
    fresh, errors = {}, []

    try:
        fresh["official"] = probe_official()
    except Exception as exc:
        errors.append(f"official: {exc}")
    try:
        fresh.update(probe_dmm())
    except Exception as exc:
        errors.append(f"dmm: {exc}")
    try:
        md = probe_masterdata(token)
        if md:
            fresh.update(md)
    except Exception as exc:
        errors.append(f"masterdata: {exc}")

    for e in errors:
        say(f"!! {e}")
    if not fresh:
        return [], True

    changes = diff(fresh, state) if state else []
    merged = {**state, **fresh,
              "checked_at": datetime.now(cu.TZ).isoformat(timespec="seconds")}
    cu.BASELINE.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    if not state:
        o = merged.get("official") or {}
        say(f"沒有舊 baseline，建立基準：asset={o.get('AssetVersionAndroidDmmR18')} "
            f"resource={o.get('resource')}")
    elif changes:
        announce(changes, merged)
    else:
        o = merged.get("official") or {}
        say(f"無變化  asset={o.get('AssetVersionAndroidDmmR18')} "
            f"resource={o.get('resource')}  apk={merged.get('apk_version_name')}")
        pending = outstanding()
        if pending:
            remind(pending)
    return changes, False


def plan():
    per_day = 24
    print("每小時檢查一次，每次三個請求：")
    print("  官方 /version  1,136 B   （沒有 ETag，只能硬打）")
    print("  DMM freeapp    4,518 B   （no-store，只能硬打）")
    print("  GitHub commits   ~0 B    （帶 token 的 304，不計入 rate limit）")
    print(f"\n一天 {per_day} 輪 = {per_day * 3} 個請求、約 {per_day * 5654 / 1024:.0f} KB")
    print(f"一週 {per_day * 7 * 3} 個請求、約 {per_day * 7 * 5654 / 1024 / 1024:.2f} MB")
    print("\n對照：固定 1 分鐘輪詢官方端點是一週 10,080 次。")
    print("      實際 DDoS 是每秒十萬次以上——差了七到八個數量級。")
    print("      開一次遊戲的資產下載就遠超過這裡一整個月的量。")
    print("\nLLM token 花費：0。這支是純 Python，不經過 Claude。")


def task_cmd():
    py = sys.executable
    script = str(Path(__file__).resolve())
    print("用系統管理員身分開 PowerShell，貼這一段（每小時跑一次，不需要視窗）：\n")
    print(f'$a = New-ScheduledTaskAction -Execute "{py}" -Argument \'"{script}"\' '
          f'-WorkingDirectory "{HERE}"')
    print("$t = New-ScheduledTaskTrigger -Once -At (Get-Date) "
          "-RepetitionInterval (New-TimeSpan -Hours 1)")
    print("$s = New-ScheduledTaskSettingsSet -StartWhenAvailable "
          "-DontStopIfGoingOnBatteries -AllowStartIfOnBatteries")
    print('Register-ScheduledTask -TaskName "DotAbyss 更新通知" '
          '-Action $a -Trigger $t -Settings $s -Description '
          '"每小時檢查官方資產版本／APK 版本／Masterdata，有變化跳通知"')
    print('\n不要了就：Unregister-ScheduledTask -TaskName "DotAbyss 更新通知" -Confirm:$false')


def main():
    if "--plan" in sys.argv:
        plan()
        return 0
    if "--task" in sys.argv:
        task_cmd()
        return 0
    if "--ack" in sys.argv:
        return acknowledge()

    token = github_token()
    if not token:
        say("沒有 GitHub token，Masterdata 的 304 會被計入 60/hr 的額度（仍然夠用）。")

    if "--watch" not in sys.argv:
        changes, failed = check(token)
        return 3 if failed else (0 if changes else 2)

    say(f"常駐模式，每 {INTERVAL // 60} 分鐘一次。Ctrl-C 結束。")
    while True:
        check(token)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say("收到 Ctrl-C，結束。")
