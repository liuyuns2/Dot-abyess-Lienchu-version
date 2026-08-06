import argparse
import json
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = (
    "你是一位專業的日文手遊劇情與輕小說譯者。"
    "請翻譯成流暢、自然、符合台灣用語的繁體中文。"
    "必須保留原文中的 HTML 標籤、<br>、<user>、標點節奏、語氣、顏文字與特殊符號。"
    "只輸出翻譯結果，不要加解釋，不要加引號。"
)


def load_json(path: Path) -> OrderedDict[str, str]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f, object_pairs_hook=OrderedDict)
    if not isinstance(data, dict):
        return OrderedDict()
    return OrderedDict((str(key), "" if value is None else str(value)) for key, value in data.items())


def save_json(path: Path, data: OrderedDict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    try:
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def translate_text(client: OpenAI, model: str, source_text: str, temperature: float) -> str:
    user_prompt = f"日文原文：\n{source_text}"

    if hasattr(client, "responses"):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            temperature=temperature,
        )
    else:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )

    return response_text(response)


def is_empty(value: str) -> bool:
    return value == ""


def translate_with_retries(
    client: OpenAI,
    model: str,
    source_text: str,
    temperature: float,
    retries: int,
    retry_sleep: float,
) -> str:
    for attempt in range(1, retries + 2):
        try:
            translated = translate_text(client, model, source_text, temperature)
            if translated:
                return translated
            print(f"  ! Empty AI response, attempt {attempt}")
        except Exception as exc:
            print(f"  ! AI request failed, attempt {attempt}: {exc}")

        if attempt <= retries:
            time.sleep(retry_sleep)

    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-translate empty zh_Hant novel JSON values.")
    parser.add_argument("--novels", default=r"E:\離線板\output\bundle_novels_merged")
    parser.add_argument("--lang", default="zh_Hant.json")
    parser.add_argument("--model", default=os.environ.get("OPENAI_TRANSLATE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--limit", type=int, default=0, help="Maximum empty entries to translate. 0 means no limit.")
    parser.add_argument("--dry-run", action="store_true", help="Preview empty entries without writing translations.")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--request-sleep", type=float, default=0.2)
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        raise SystemExit("OPENAI_API_KEY is not set. Set it before running this script.")

    client = OpenAI(api_key=api_key) if api_key else None
    novels_dir = Path(args.novels)
    translated_count = 0
    files_modified = 0

    print(f"Scanning: {novels_dir}")
    print(f"Language: {args.lang}")
    print(f"Model: {args.model}")
    if args.dry_run:
        print("Dry run: no files will be changed.")

    for script_dir in sorted(path for path in novels_dir.iterdir() if path.is_dir()):
        json_path = script_dir / args.lang
        if not json_path.exists():
            continue

        data = load_json(json_path)
        modified = False

        for source_text, value in data.items():
            if not is_empty(value):
                continue

            print(f"[{script_dir.name}] #{translated_count + 1}: {source_text[:80]}")
            if args.dry_run:
                translated_count += 1
            else:
                assert client is not None
                translated = translate_with_retries(
                    client,
                    args.model,
                    source_text,
                    args.temperature,
                    args.retries,
                    args.retry_sleep,
                )
                if translated:
                    data[source_text] = translated
                    modified = True
                    translated_count += 1
                    print(f"  -> {translated[:80]}")
                else:
                    print("  -> skipped: translation failed")

                time.sleep(args.request_sleep)

            if args.limit > 0 and translated_count >= args.limit:
                break

        if modified:
            save_json(json_path, data)
            files_modified += 1
            print(f"Saved: {json_path}")

        if args.limit > 0 and translated_count >= args.limit:
            break

    print(f"Translated empty entries: {translated_count}")
    print(f"Files modified: {files_modified}")


if __name__ == "__main__":
    main()
