import argparse
import csv
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import UnityPy


INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(value: object, fallback: str = "asset") -> str:
    text = str(value or "").strip() or fallback
    text = INVALID_NAME_CHARS.sub("_", text)
    text = text.rstrip(". ")
    return text[:180] or fallback


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


class State:
    def __init__(self, total: int, status_path: Path) -> None:
        self.total = total
        self.status_path = status_path
        self.lock = threading.Lock()
        self.done = 0
        self.skipped = 0
        self.failed = 0
        self.objects = 0
        self.start = time.time()

    def update(self, *, done: int = 0, skipped: int = 0, failed: int = 0, objects: int = 0) -> None:
        with self.lock:
            self.done += done
            self.skipped += skipped
            self.failed += failed
            self.objects += objects
            self.write_locked()

    def write_locked(self) -> None:
        elapsed = max(time.time() - self.start, 0.001)
        data = {
            "total": self.total,
            "done": self.done,
            "skipped": self.skipped,
            "failed": self.failed,
            "remaining": self.total - self.done - self.failed,
            "objects_extracted_or_indexed": self.objects,
            "elapsed_seconds": round(elapsed, 1),
            "bundles_per_second": round((self.done + self.failed) / elapsed, 3),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = row.get("primary_key") or ""
            if key:
                result[key] = row
    return result


def export_object(obj: Any, bundle_out: Path, type_name: str, index: int) -> dict[str, Any]:
    data = obj.read()
    name = safe_name(getattr(data, "name", "") or getattr(data, "m_Name", ""), f"{type_name}_{index:05d}")
    base = bundle_out / type_name / f"{index:05d}_{name}"
    record = {
        "path_id": getattr(obj, "path_id", None),
        "type": type_name,
        "name": name,
        "exported": [],
    }

    try:
        if type_name == "TextAsset":
            script = getattr(data, "m_Script", b"")
            if isinstance(script, (bytes, bytearray)):
                try:
                    text = bytes(script).decode("utf-8-sig")
                    write_text(base.with_suffix(".txt"), text)
                    record["exported"].append(str(base.with_suffix(".txt")))
                except UnicodeDecodeError:
                    write_bytes(base.with_suffix(".bytes"), bytes(script))
                    record["exported"].append(str(base.with_suffix(".bytes")))
            else:
                write_text(base.with_suffix(".txt"), str(script).lstrip("\ufeff"))
                record["exported"].append(str(base.with_suffix(".txt")))
        elif type_name in {"Texture2D", "Sprite"}:
            image = data.image
            out = base.with_suffix(".png")
            out.parent.mkdir(parents=True, exist_ok=True)
            image.save(out)
            record["exported"].append(str(out))
        elif type_name == "AudioClip":
            samples = getattr(data, "samples", {}) or {}
            if samples:
                for sample_name, sample_data in samples.items():
                    out = bundle_out / type_name / f"{index:05d}_{safe_name(sample_name, name)}"
                    write_bytes(out, sample_data)
                    record["exported"].append(str(out))
            else:
                record["note"] = "AudioClip has no exported samples"
        elif hasattr(data, "read_typetree"):
            tree = data.read_typetree()
            out = base.with_suffix(".json")
            write_json(out, tree)
            record["exported"].append(str(out))
        else:
            record["note"] = "No supported exporter"
    except Exception as exc:
        record["error"] = str(exc)

    return record


def unpack_bundle(bundle_path: Path, output_dir: Path, overwrite: bool) -> tuple[str, int, str]:
    bundle_name = bundle_path.name
    bundle_out = output_dir / safe_name(bundle_name)
    done_marker = bundle_out / ".unpacked.json"
    if done_marker.exists() and not overwrite:
        try:
            info = json.loads(done_marker.read_text(encoding="utf-8"))
            return ("skipped", int(info.get("object_count", 0)), bundle_name)
        except Exception:
            return ("skipped", 0, bundle_name)

    bundle_out.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(bundle_path))
    records: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}
    for index, obj in enumerate(env.objects):
        type_name = getattr(obj.type, "name", str(obj.type))
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
        records.append(export_object(obj, bundle_out, safe_name(type_name), index))

    marker = {
        "bundle": bundle_name,
        "object_count": len(records),
        "type_counts": type_counts,
        "unpacked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(bundle_out / "_objects.json", records)
    write_json(done_marker, marker)
    return ("done", len(records), bundle_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unpack downloaded Unity catalog bundles.")
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    downloads = Path(args.downloads)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir.parent / "unpack_status.json"
    failed_path = output_dir.parent / "unpack_failed.txt"

    manifest = read_manifest(Path(args.manifest))
    bundle_paths = [
        downloads / row["primary_key"]
        for row in manifest.values()
        if (downloads / row["primary_key"]).exists()
    ]
    # Include normalized CRI/media names that may have been shortened by the downloader.
    seen = {path.name for path in bundle_paths}
    for path in downloads.iterdir():
        if path.is_file() and not path.name.endswith(".part") and path.name not in seen:
            bundle_paths.append(path)
            seen.add(path.name)

    state = State(len(bundle_paths), status_path)
    state.write_locked()
    failed: list[str] = []
    print(f"Bundles to unpack: {len(bundle_paths)}")
    print(f"Output: {output_dir}")
    print(f"Status: {status_path}")

    last_print = time.time()
    with ThreadPoolExecutor(max_workers=max(args.threads, 1)) as executor:
        futures = {executor.submit(unpack_bundle, path, output_dir, args.overwrite): path for path in bundle_paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                status, objects, name = future.result()
                if status == "skipped":
                    state.update(done=1, skipped=1, objects=objects)
                else:
                    state.update(done=1, objects=objects)
            except Exception as exc:
                failed.append(f"{path.name}\t{exc}")
                state.update(failed=1)

            now = time.time()
            if now - last_print >= 10:
                with state.lock:
                    print(
                        f"progress {state.done + state.failed}/{state.total} "
                        f"done={state.done} failed={state.failed} objects={state.objects}"
                    )
                failed_path.write_text("\n".join(failed) + ("\n" if failed else ""), encoding="utf-8")
                last_print = now

    failed_path.write_text("\n".join(failed) + ("\n" if failed else ""), encoding="utf-8")
    print(f"Finished. done={state.done} failed={state.failed} skipped={state.skipped}")


if __name__ == "__main__":
    main()
