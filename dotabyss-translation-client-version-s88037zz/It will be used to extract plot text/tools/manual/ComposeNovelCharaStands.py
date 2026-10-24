import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
import UnityPy
from UnityPy.enums import ClassIDType


CHARASTAND_RE = re.compile(r"charastand([0-9a-z]+)", re.IGNORECASE)


def path_id(ref: Any) -> Optional[int]:
    if hasattr(ref, "m_PathID"):
        return ref.m_PathID
    if isinstance(ref, dict):
        return ref.get("m_PathID")
    return None


def collect_rect_layout(env) -> Dict[str, Dict[str, Any]]:
    objects_by_id = {obj.path_id: obj for obj in env.objects}
    go_names: Dict[int, str] = {}

    for obj in env.objects:
        if obj.type != ClassIDType.GameObject:
            continue
        try:
            go = obj.read()
            go_names[obj.path_id] = getattr(go, "m_Name", "")
        except Exception:
            pass

    layout: Dict[str, Dict[str, Any]] = {}
    for obj in env.objects:
        type_id = obj.type.value if hasattr(obj.type, "value") else obj.type
        if obj.type != ClassIDType.RectTransform and type_id != 224:
            continue

        try:
            rt = obj.read()
            go_id = path_id(getattr(rt, "m_GameObject", None))
            go_name = go_names.get(go_id or 0, "")
            if not go_name:
                continue

            parent_name = ""
            father_id = path_id(getattr(rt, "m_Father", None))
            if father_id and father_id in objects_by_id:
                father_rt = objects_by_id[father_id].read()
                father_go_id = path_id(getattr(father_rt, "m_GameObject", None))
                parent_name = go_names.get(father_go_id or 0, "")

            anchored = getattr(rt, "m_AnchoredPosition", None)
            size = getattr(rt, "m_SizeDelta", None)
            layout[go_name] = {
                "ax": getattr(anchored, "x", 0) if anchored else 0,
                "ay": getattr(anchored, "y", 0) if anchored else 0,
                "sw": getattr(size, "x", 0) if size else 0,
                "sh": getattr(size, "y", 0) if size else 0,
                "parent": parent_name,
            }
        except Exception:
            pass

    return layout


def extract_face_layout(env) -> Optional[Dict[str, float]]:
    layout = collect_rect_layout(env)
    face = layout.get("FaceContent")
    body = layout.get("Body")
    if not face or not body or face.get("parent") != "Body":
        return None

    return {
        "face_anchor_x": face["ax"],
        "face_anchor_y": face["ay"],
        "face_w": face["sw"],
        "face_h": face["sh"],
        "body_w": body["sw"],
        "body_h": body["sh"],
    }


def sprite_data(sprite) -> Optional[Dict[str, Any]]:
    name = getattr(sprite, "m_Name", "unknown")
    if name == "_stand1" or not hasattr(sprite, "image") or sprite.image is None:
        return None

    rect = getattr(sprite, "m_Rect", None)
    rect_w = int(getattr(rect, "width", 0)) if rect else 0
    rect_h = int(getattr(rect, "height", 0)) if rect else 0
    tro_x = 0.0
    tro_y = 0.0
    rd = getattr(sprite, "m_RD", None)
    offset = getattr(rd, "textureRectOffset", None) if rd else None
    if offset:
        tro_x = getattr(offset, "x", 0.0)
        tro_y = getattr(offset, "y", 0.0)

    return {
        "name": name,
        "img": sprite.image.convert("RGBA"),
        "img_w": sprite.image.size[0],
        "img_h": sprite.image.size[1],
        "rect_w": rect_w,
        "rect_h": rect_h,
        "tro_x": tro_x,
        "tro_y": tro_y,
    }


def prepare_layer(data: Dict[str, Any], target_w: int, target_h: int) -> Image.Image:
    rect_w = data["rect_w"] if data["rect_w"] > 0 else data["img_w"]
    rect_h = data["rect_h"] if data["rect_h"] > 0 else data["img_h"]
    full = Image.new("RGBA", (rect_w, rect_h), (0, 0, 0, 0))

    paste_x = max(0, int(round(data["tro_x"])))
    paste_y = rect_h - int(round(data["tro_y"])) - data["img_h"]
    paste_y = max(0, paste_y)
    full.alpha_composite(data["img"], dest=(paste_x, paste_y))

    if target_w > 0 and target_h > 0 and full.size != (target_w, target_h):
        return full.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return full


def face_slot(face: Dict[str, float], canvas_w: int, canvas_h: int) -> Tuple[int, int, int, int]:
    scale_x = canvas_w / face["body_w"] if face["body_w"] > 0 else 1.0
    scale_y = canvas_h / face["body_h"] if face["body_h"] > 0 else 1.0
    slot_w = int(round(face["face_w"] * scale_x))
    slot_h = int(round(face["face_h"] * scale_y))
    center_x = canvas_w / 2 + face["face_anchor_x"] * scale_x
    center_y = canvas_h / 2 - face["face_anchor_y"] * scale_y
    left = int(round(center_x - slot_w / 2))
    top = int(round(center_y - slot_h / 2))
    return left, top, slot_w, slot_h


def bundle_stand_id(bundle_path: Path) -> str:
    match = CHARASTAND_RE.search(bundle_path.name)
    if match:
        return match.group(1).upper()
    return bundle_path.stem


def compose_bundle(bundle_path: Path, output_root: Path, expressions: Optional[set[str]]) -> int:
    env = UnityPy.load(str(bundle_path))
    face = extract_face_layout(env)
    all_sprites = {}

    for obj in env.objects:
        if obj.type != ClassIDType.Sprite:
            continue
        try:
            all_sprites[obj.path_id] = obj.read()
        except Exception:
            pass

    sprite_map: Dict[str, Dict[str, Any]] = {}
    for obj in env.objects:
        if obj.type != ClassIDType.SpriteAtlas:
            continue
        atlas = obj.read()
        for ref in getattr(atlas, "m_PackedSprites", []):
            sprite = all_sprites.get(getattr(ref, "m_PathID", 0))
            if sprite is None:
                resolved = ref.resolve()
                sprite = resolved.read() if resolved else None
            if sprite is None:
                continue
            data = sprite_data(sprite)
            if data:
                sprite_map[data["name"]] = data

    body = None
    for data in sprite_map.values():
        if "body" in data["name"].lower():
            if body is None or data["img_w"] * data["img_h"] > body["img_w"] * body["img_h"]:
                body = data

    if body is None:
        return 0

    body_img = body["img"]
    canvas_w, canvas_h = body_img.size
    if face:
        paste_x, paste_y, target_w, target_h = face_slot(face, canvas_w, canvas_h)
    else:
        paste_x, paste_y = 0, 0
        target_w, target_h = canvas_w, canvas_h

    out_dir = output_root / bundle_stand_id(bundle_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    exported = 0
    for name, data in sorted(sprite_map.items()):
        if data is body:
            continue
        if expressions and name.lower() not in expressions:
            continue

        layer = prepare_layer(data, target_w, target_h)
        canvas = body_img.copy()
        safe_x = max(0, min(paste_x, canvas_w - layer.size[0]))
        safe_y = max(0, min(paste_y, canvas_h - layer.size[1]))
        canvas.alpha_composite(layer, dest=(safe_x, safe_y))
        canvas.save(out_dir / f"{bundle_stand_id(bundle_path)}_{name}.png")
        exported += 1

    if exported == 0:
        body_img.save(out_dir / f"{bundle_stand_id(bundle_path)}_BodyOnly.png")
        exported = 1

    return exported


def find_bundles(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    bundles = []
    for path in input_path.rglob("*"):
        if path.is_file() and "charastand" in path.name.lower():
            try:
                with path.open("rb") as f:
                    if f.read(7) == b"UnityFS":
                        bundles.append(path)
            except Exception:
                pass
    return sorted(bundles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose DotAbyss novel chara stand atlas sprites into viewable PNGs.")
    parser.add_argument("--input", required=True, help="Bundle file or directory containing charastand bundles.")
    parser.add_argument("--output", required=True, help="Output directory for composed PNGs.")
    parser.add_argument(
        "--expressions",
        default="Normal",
        help="Comma-separated expression names to export, or 'all'. Default: Normal",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    expressions = None
    if args.expressions.strip().lower() != "all":
        expressions = {name.strip().lower() for name in args.expressions.split(",") if name.strip()}

    bundles = find_bundles(input_path)
    print(f"Found charastand bundles: {len(bundles)}")

    total = 0
    failed = 0
    for index, bundle in enumerate(bundles, 1):
        try:
            exported = compose_bundle(bundle, output_root, expressions)
            total += exported
            if exported:
                print(f"[{index}/{len(bundles)}] {bundle_stand_id(bundle)} exported {exported}")
        except Exception as exc:
            failed += 1
            print(f"[{index}/{len(bundles)}] FAILED {bundle.name}: {exc}")

    print(f"Done. Exported PNGs: {total}, failed bundles: {failed}")


if __name__ == "__main__":
    main()
