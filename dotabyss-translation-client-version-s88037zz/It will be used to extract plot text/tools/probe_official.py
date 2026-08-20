#!/usr/bin/env python3
"""官方 /version 端點：真正的「更新有沒有上」訊號。複用 tools/DotAbyss.py 的解密實作。"""
import sys, json, io, contextlib
from pathlib import Path

# DotAbyss.py 與本檔同層
sys.path.insert(0, str(Path(__file__).resolve().parent))

KEYS = ["AssetVersionWebDmmR18", "AssetVersionStandaloneDmmR18", "AssetVersionAndroidDmmR18",
        "resource", "ClientVersionWebDmmR18", "ClientVersionStandaloneDmmR18",
        "ClientVersionAndroidDmmR18"]

def fetch() -> dict:
    """回傳 {key: value}；失敗時丟例外。DotAbyss.py 會亂印，這裡把 stdout 吃掉。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import DotAbyss
        dl = None
        for name in dir(DotAbyss):
            obj = getattr(DotAbyss, name)
            if isinstance(obj, type) and hasattr(obj, "get_version_info"):
                try:
                    dl = obj(); break
                except TypeError:
                    continue
        if dl is None:
            raise RuntimeError("找不到具 get_version_info 的類別")
        info = dl.get_version_info()
    if not info:
        raise RuntimeError("get_version_info 回傳空值")
    v = info.get("versions", {})
    out = {}
    for k in KEYS:
        val = v.get(k)
        if isinstance(val, list):
            val = val[-1] if val else None
        out[k] = val
    return out

if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
