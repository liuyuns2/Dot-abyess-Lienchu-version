#!/usr/bin/env bash
# 輪詢官方 /version，直到資產版本變動或逾時。改版當天掛著跑。
#
#   ./wait_for_update.sh                 # 預設每 4 分鐘一次，最多等 2.5 小時
#   INTERVAL=600 DEADLINE_MIN=300 ./wait_for_update.sh
#   PYTHON=/path/to/python ./wait_for_update.sh
#
# exit 0 = 偵測到更新   2 = 逾時仍無更新   3 = 探測連續失敗
#
# 需要 requests / msgpack / pycryptodome / rich（與本工具鏈其他腳本相同的環境）。
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    if [ -x "$HERE/.venv/Scripts/python.exe" ]; then PYTHON="$HERE/.venv/Scripts/python.exe"
    elif [ -x "$HERE/.venv/bin/python" ];      then PYTHON="$HERE/.venv/bin/python"
    else PYTHON="python"; fi
fi

INTERVAL="${INTERVAL:-240}"
DEADLINE=$(( $(date +%s) + ${DEADLINE_MIN:-150} * 60 ))
FAILS=0

echo "[watch] python   : $PYTHON"
echo "[watch] 間隔     : ${INTERVAL}s"
"$PYTHON" "$HERE/check_update.py" || true      # 第一次順便建立基準

while :; do
    OUT=$("$PYTHON" "$HERE/check_update.py" --peek 2>&1)
    echo "----- $(date '+%H:%M:%S') -----"
    echo "$OUT"

    if echo "$OUT" | grep -q "\[CHANGED\]"; then
        echo "[watch] >>> 偵測到更新，結束輪詢"
        exit 0
    fi
    if echo "$OUT" | grep -qE "official_error|dmm_error"; then
        FAILS=$((FAILS + 1))
        [ "$FAILS" -ge 6 ] && { echo "[watch] 連續 6 次探測失敗"; exit 3; }
    else
        FAILS=0
    fi
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "[watch] >>> 逾時，官方資產版本始終沒有變動"
        exit 2
    fi
    sleep "$INTERVAL"
done
