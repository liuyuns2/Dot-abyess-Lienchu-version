import argparse
import csv
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


REMOTE_TOKEN = "{Absf.Asset.AddressableAssets.AddressablesProfileDefine.RemoteLoadPath}"
HEADERS = {
    "User-Agent": "UnityPlayer/6000.0.43f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
    "X-Unity-Version": "6000.0.43f1",
}


class DownloadState:
    def __init__(self, total: int, total_bytes: int, status_path: Path):
        self.total = total
        self.total_bytes = total_bytes
        self.status_path = status_path
        self.lock = threading.Lock()
        self.done = 0
        self.skipped = 0
        self.failed = 0
        self.downloaded_bytes = 0
        self.start_time = time.time()

    def add(self, *, done: int = 0, skipped: int = 0, failed: int = 0, bytes_done: int = 0) -> None:
        with self.lock:
            self.done += done
            self.skipped += skipped
            self.failed += failed
            self.downloaded_bytes += bytes_done
            self.write_status_locked()

    def write_status_locked(self) -> None:
        elapsed = max(time.time() - self.start_time, 0.001)
        data = {
            "total": self.total,
            "done": self.done,
            "skipped": self.skipped,
            "failed": self.failed,
            "remaining": self.total - self.done - self.failed,
            "total_bytes": self.total_bytes,
            "downloaded_or_verified_bytes": self.downloaded_bytes,
            "elapsed_seconds": round(elapsed, 1),
            "items_per_second": round((self.done + self.failed) / elapsed, 3),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_filename(primary_key: str) -> str:
    file_name = primary_key
    for ext in (".usm", ".awb"):
        if ext in file_name:
            return file_name.split(ext)[0] + ext
    return file_name


def read_manifest(path: Path, base_url: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            internal_id = row.get("internal_id") or ""
            if REMOTE_TOKEN not in internal_id:
                continue
            primary_key = row.get("primary_key") or ""
            size = int(row.get("bundle_size") or 0)
            relative_path = internal_id.replace(REMOTE_TOKEN, "").replace("\\", "/")
            url = base_url.rstrip("/") + "/" + relative_path.lstrip("/")
            rows.append(
                {
                    "primary_key": primary_key,
                    "file_name": normalize_filename(primary_key),
                    "url": url,
                    "size": size,
                    "hash": row.get("hash") or "",
                    "crc": row.get("crc") or "",
                }
            )
    return rows


def download_one(item: dict[str, object], output_dir: Path, retries: int) -> tuple[str, str, int]:
    file_name = str(item["file_name"])
    url = str(item["url"])
    expected_size = int(item["size"] or 0)
    dest = output_dir / file_name
    part = output_dir / (file_name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and (expected_size <= 0 or dest.stat().st_size == expected_size):
        return ("skipped", file_name, expected_size)
    if dest.exists() and expected_size > 0 and dest.stat().st_size != expected_size:
        dest.unlink()

    for attempt in range(retries):
        try:
            headers = dict(HEADERS)
            mode = "wb"
            existing = part.stat().st_size if part.exists() else 0
            if existing > 0 and expected_size > 0 and existing < expected_size:
                headers["Range"] = f"bytes={existing}-"
                mode = "ab"
            elif existing >= expected_size > 0:
                part.replace(dest)
                return ("done", file_name, expected_size)

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as response:
                if response.status == 200 and mode == "ab":
                    mode = "wb"
                with part.open(mode + "") as f:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)

            if expected_size > 0 and part.stat().st_size != expected_size:
                raise RuntimeError(f"size mismatch {part.stat().st_size} != {expected_size}")
            part.replace(dest)
            return ("done", file_name, expected_size)
        except Exception as exc:
            if attempt == retries - 1:
                return ("failed", f"{file_name}\t{exc}", 0)
            time.sleep(1 + attempt)

    return ("failed", file_name, 0)


def write_failed(path: Path, failed_rows: list[str]) -> None:
    path.write_text("\n".join(failed_rows) + ("\n" if failed_rows else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download bundles listed in a parsed catalog manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--retries", type=int, default=5)
    args = parser.parse_args()

    manifest = Path(args.manifest)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir.parent / "download_status.json"
    failed_path = output_dir.parent / "download_failed.txt"

    items = read_manifest(manifest, args.base_url)
    total_bytes = sum(int(item["size"] or 0) for item in items)
    state = DownloadState(len(items), total_bytes, status_path)
    failed_rows: list[str] = []
    state.write_status_locked()

    print(f"Download items: {len(items)}")
    print(f"Total bytes: {total_bytes}")
    print(f"Output: {output_dir}")
    print(f"Status: {status_path}")

    last_print = time.time()
    with ThreadPoolExecutor(max_workers=max(args.threads, 1)) as executor:
        futures = [executor.submit(download_one, item, output_dir, args.retries) for item in items]
        for future in as_completed(futures):
            status, name, bytes_done = future.result()
            if status == "skipped":
                state.add(done=1, skipped=1, bytes_done=bytes_done)
            elif status == "done":
                state.add(done=1, bytes_done=bytes_done)
            else:
                failed_rows.append(name)
                state.add(failed=1)

            now = time.time()
            if now - last_print >= 10:
                with state.lock:
                    print(
                        f"progress {state.done + state.failed}/{state.total} "
                        f"done={state.done} failed={state.failed}"
                    )
                write_failed(failed_path, failed_rows)
                last_print = now

    write_failed(failed_path, failed_rows)
    print(f"Finished. done={state.done} failed={state.failed} skipped={state.skipped}")


if __name__ == "__main__":
    main()
