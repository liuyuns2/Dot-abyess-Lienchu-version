"""串流讀取大 JSON 檔裡的某一個陣列，不把整份檔案載進記憶體。

為什麼要有這個檔：產線的 `assets.json` 是 ~390MB（12 萬筆 location），
`json.load()` 展開後光物件本身就要好幾倍的 RAM，2026-09-21 的更新就是在這一步
被系統砍掉的。消費端其實只要逐筆掃過去挑出想要的那幾百筆，沒必要整份留著。

只用標準函式庫（`json.JSONDecoder.raw_decode`），不引入 ijson 之類的相依。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

_DECODER = json.JSONDecoder()
_WS = " \t\r\n"


def iter_json_array(
    path: Path, key: str, chunk_size: int = 1 << 20
) -> Iterator[Any]:
    """逐筆吐出 `path` 裡 `"<key>": [ ... ]` 這個陣列的元素。

    只認最外層物件底下的該鍵；找不到就當作空陣列。
    緩衝區只留「還沒解析完的那一段」，所以記憶體用量取決於單一元素大小，
    與整份檔案多大無關。
    """
    opener = re.compile(r'"%s"\s*:\s*\[' % re.escape(key))
    with path.open("r", encoding="utf-8") as f:
        buffer = ""
        # 1. 先找到陣列的開頭 '['
        while True:
            match = opener.search(buffer)
            if match:
                buffer = buffer[match.end() :]
                break
            chunk = f.read(chunk_size)
            if not chunk:
                return  # 整份掃完都沒這個鍵
            # 鍵名可能剛好被切成兩半，保留尾巴再接下一塊
            buffer = buffer[-(len(key) + 8) :] + chunk

        # 2. 逐個元素 raw_decode
        position = 0
        while True:
            while True:
                # 跳過元素之間的空白與逗號
                while position < len(buffer) and buffer[position] in _WS + ",":
                    position += 1
                if position < len(buffer):
                    break
                chunk = f.read(chunk_size)
                if not chunk:
                    return  # 檔案在陣列結束前就斷了（截斷的 assets.json）
                buffer = buffer[position:] + chunk
                position = 0

            if buffer[position] == "]":
                return

            while True:
                try:
                    value, position = _DECODER.raw_decode(buffer, position)
                except ValueError:
                    # 分不出「元素被切斷」還是「真的壞掉」，先補資料再試；
                    # 補不到東西（EOF）才是真的壞掉。
                    chunk = f.read(chunk_size)
                    if not chunk:
                        raise ValueError(
                            f"{path} 的 \"{key}\" 陣列在檔案結束前就中斷了"
                        ) from None
                    buffer = buffer[position:] + chunk
                    position = 0
                    continue
                break

            yield value

            # 每筆都 buffer = buffer[position:] 會對整個緩衝區做一次複製，
            # 12 萬筆下來光搬字串就佔掉大半執行時間。改成讓 position 一路往前走，
            # 等已消化的部分超過一半才壓縮一次。
            if position > len(buffer) // 2:
                buffer = buffer[position:]
                position = 0
