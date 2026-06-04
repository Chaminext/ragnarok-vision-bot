"""
Gera dataset YOLO sintetico usando spritesheets do Divine Pride.

Uso recomendado para pay_dun04:
  1. Capture fundos no mapa: python ro_bot.py --dataset
  2. Gere dataset sintetico:
     python ro_synthetic_dataset.py --profile data/payon_dun04_mobs.json --out datasets/payon_dun04_synth --per-class 120 --negatives 60
  3. Treine:
     python ro_yolo_train.py --data datasets/payon_dun04_synth/dataset.yaml --output models/payon_dun04_yolo.pt

O script nao precisa de rotulagem manual. As caixas sao calculadas pela posicao
onde o sprite foi colado no fundo.
"""

import argparse
import glob
import json
import os
import random
import shutil
import sys
from urllib.request import Request, urlopen

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


DEFAULT_PROFILE = os.path.join("data", "payon_dun04_mobs.json")
DEFAULT_BACKGROUNDS = os.path.join("datasets", "ro_mob", "images", "raw")
DEFAULT_OUT = os.path.join("datasets", "payon_dun04_synth")
SPRITE_DIR = os.path.join("assets", "divine_sprites")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def clean_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def load_profile(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sprite_url(mob):
    if mob.get("spritesheet_url"):
        return mob["spritesheet_url"]
    divine_id = mob.get("divine_pride_id")
    if not divine_id:
        return ""
    return f"https://static.divine-pride.net/images/spritesheets/npc/{divine_id}.png"


def download(url, path, force=False):
    if os.path.exists(path) and not force:
        return True
    ensure_dir(os.path.dirname(path))
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 ro-synthetic-dataset"})
    try:
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:
        print(f"[WARN] Falha ao baixar {url}: {exc}")
        return False
    with open(path, "wb") as f:
        f.write(data)
    return True


def list_images(path):
    exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(path, ext)))
    return sorted(files)


def load_backgrounds(path):
    files = list_images(path)
    backgrounds = []
    for file in files:
        img = cv2.imread(file, cv2.IMREAD_COLOR)
        if img is not None and img.size:
            backgrounds.append((file, img))
    return backgrounds


def make_blank_background(width=1280, height=960):
    bg = np.zeros((height, width, 3), dtype=np.uint8)
    bg[:] = (36, 36, 36)
    rng = random.Random(1234)
    for _ in range(10):
        x1 = rng.randint(0, width - 120)
        y1 = rng.randint(0, height - 120)
        x2 = min(width, x1 + rng.randint(40, 220))
        y2 = min(height, y1 + rng.randint(35, 190))
        bg[y1:y2, x1:x2] = (0, 0, 0)
    return [("blank", bg)]


def read_sprite_sheet(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        alpha = np.full(img.shape, 255, dtype=np.uint8)
        return np.dstack([bgr, alpha])
    if img.shape[2] == 3:
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)
        return np.dstack([img, alpha])
    return img


def extract_sprite_frames(sheet):
    alpha = sheet[:, :, 3]
    mask = (alpha > 8).astype(np.uint8)
    if int(mask.sum()) == 0:
        return []

    joined = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    frames = []
    h, w = alpha.shape[:2]
    for idx in range(1, n):
        x, y, bw, bh, area = stats[idx]
        if area < 80 or bw < 8 or bh < 8:
            continue
        if bw > w * 0.65 or bh > h * 0.65:
            continue
        pad = 3
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + bw + pad)
        y1 = min(h, y + bh + pad)
        crop = sheet[y0:y1, x0:x1].copy()
        if int((crop[:, :, 3] > 8).sum()) < 50:
            continue
        frames.append(trim_alpha(crop))

    frames.sort(key=lambda im: im.shape[0] * im.shape[1], reverse=True)
    return frames[:80]


def trim_alpha(img):
    alpha = img[:, :, 3]
    ys, xs = np.where(alpha > 8)
    if len(xs) == 0 or len(ys) == 0:
        return img
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    return img[y0:y1, x0:x1].copy()


def recolor_sprite(sprite):
    out = sprite.copy()
    bgr = out[:, :, :3].astype(np.float32)
    alpha = out[:, :, 3]
    brightness = random.uniform(0.82, 1.18)
    contrast = random.uniform(0.88, 1.12)
    bgr = (bgr - 127.5) * contrast + 127.5
    bgr *= brightness
    if random.random() < 0.35:
        tint = np.array([random.uniform(0.92, 1.08),
                         random.uniform(0.92, 1.08),
                         random.uniform(0.92, 1.08)], dtype=np.float32)
        bgr *= tint
    out[:, :, :3] = np.clip(bgr, 0, 255).astype(np.uint8)
    out[:, :, 3] = alpha
    return out


def augment_sprite(sprite):
    out = sprite
    if random.random() < 0.5:
        out = cv2.flip(out, 1)
    scale = random.uniform(0.78, 1.28)
    h, w = out.shape[:2]
    nw = max(6, int(w * scale))
    nh = max(6, int(h * scale))
    out = cv2.resize(out, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    return recolor_sprite(out)


def alpha_blend(bg, sprite, x, y):
    h, w = sprite.shape[:2]
    bh, bw = bg.shape[:2]
    if x < 0 or y < 0 or x + w > bw or y + h > bh:
        return None
    roi = bg[y:y+h, x:x+w].astype(np.float32)
    rgb = sprite[:, :, :3].astype(np.float32)
    alpha = (sprite[:, :, 3:4].astype(np.float32) / 255.0)
    blended = rgb * alpha + roi * (1.0 - alpha)
    bg[y:y+h, x:x+w] = blended.astype(np.uint8)
    ys, xs = np.where(sprite[:, :, 3] > 8)
    if len(xs) == 0:
        return None
    return x + xs.min(), y + ys.min(), x + xs.max() + 1, y + ys.max() + 1


def yolo_line(class_id, box, width, height):
    x1, y1, x2, y2 = box
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    cx = x1 + bw / 2
    cy = y1 + bh / 2
    return f"{class_id} {cx/width:.6f} {cy/height:.6f} {bw/width:.6f} {bh/height:.6f}"


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return inter / float(area_a + area_b - inter)


def pick_position(bg, sprite, existing):
    bh, bw = bg.shape[:2]
    sh, sw = sprite.shape[:2]
    x_min, x_max = int(bw * 0.08), int(bw * 0.70)
    y_min, y_max = int(bh * 0.12), int(bh * 0.82)
    x_max = max(x_min + 1, min(x_max, bw - sw - 1))
    y_max = max(y_min + 1, min(y_max, bh - sh - 1))
    if x_max <= x_min or y_max <= y_min:
        return None

    for _ in range(40):
        x = random.randint(x_min, x_max)
        y = random.randint(y_min, y_max)
        candidate = (x, y, x + sw, y + sh)
        if all(iou(candidate, prev) < 0.12 for prev in existing):
            return x, y
    return None


def split_for(index, val_ratio):
    return "val" if random.random() < val_ratio else "train"


def write_dataset_yaml(out_dir, mobs):
    path = os.path.join(out_dir, "dataset.yaml")
    lines = [
        f"path: {out_dir.replace(os.sep, '/')}",
        "train: images/train",
        "val: images/val",
        "",
        "names:",
    ]
    for mob in sorted(mobs, key=lambda m: m["class_id"]):
        lines.append(f"  {mob['class_id']}: {mob['class_name']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def load_all_sprites(mobs, force_download=False):
    sprites = {}
    for mob in mobs:
        url = sprite_url(mob)
        if not url:
            print(f"[WARN] Sem spritesheet_url/divine_pride_id: {mob['class_name']}")
            continue
        divine_id = mob.get("divine_pride_id") or mob["class_name"]
        local = os.path.join(SPRITE_DIR, f"{mob['class_name']}_{divine_id}.png")
        if not download(url, local, force=force_download):
            continue
        sheet = read_sprite_sheet(local)
        if sheet is None:
            print(f"[WARN] Nao abriu spritesheet: {local}")
            continue
        frames = extract_sprite_frames(sheet)
        if not frames:
            print(f"[WARN] Nenhum frame extraido: {mob['class_name']}")
            continue
        sprites[mob["class_id"]] = frames
        print(f"[SPRITE] {mob['class_name']}: {len(frames)} frame(s)")
    return sprites


def create_dirs(out_dir, clean=True):
    if clean:
        clean_dir(out_dir)
    for split in ("train", "val"):
        ensure_dir(os.path.join(out_dir, "images", split))
        ensure_dir(os.path.join(out_dir, "labels", split))


def generate(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    profile = load_profile(args.profile)
    mobs = [m for m in profile.get("mobs", []) if m.get("enabled", True)]
    mobs = sorted(mobs, key=lambda m: m["class_id"])
    backgrounds = load_backgrounds(args.backgrounds)
    if not backgrounds:
        print("[WARN] Nenhum fundo real encontrado. Usando fundos genericos; qualidade sera menor.")
        backgrounds = make_blank_background()

    sprites = load_all_sprites(mobs, force_download=args.force_download)
    ready_mobs = [m for m in mobs if m["class_id"] in sprites]
    if not ready_mobs:
        print("[ERRO] Nenhum sprite pronto para gerar dataset.")
        return 1

    create_dirs(args.out, clean=not args.no_clean)
    yaml_path = write_dataset_yaml(args.out, mobs)

    total = 0
    for mob in ready_mobs:
        for i in range(args.per_class):
            bg_name, bg = random.choice(backgrounds)
            canvas = bg.copy()
            labels = []
            placed = []

            primary = augment_sprite(random.choice(sprites[mob["class_id"]]))
            pos = pick_position(canvas, primary, placed)
            if pos is None:
                continue
            box = alpha_blend(canvas, primary, *pos)
            if box is None:
                continue
            labels.append(yolo_line(mob["class_id"], box, canvas.shape[1], canvas.shape[0]))
            placed.append(box)

            distractors = random.randint(0, args.max_distractors)
            for _ in range(distractors):
                other = random.choice(ready_mobs)
                sprite = augment_sprite(random.choice(sprites[other["class_id"]]))
                pos = pick_position(canvas, sprite, placed)
                if pos is None:
                    continue
                box = alpha_blend(canvas, sprite, *pos)
                if box is None:
                    continue
                labels.append(yolo_line(other["class_id"], box, canvas.shape[1], canvas.shape[0]))
                placed.append(box)

            split = split_for(total, args.val_ratio)
            name = f"syn_{profile.get('profile', 'profile')}_{mob['class_name']}_{i:04d}.png"
            image_path = os.path.join(args.out, "images", split, name)
            label_path = os.path.join(args.out, "labels", split, os.path.splitext(name)[0] + ".txt")
            cv2.imwrite(image_path, canvas)
            with open(label_path, "w", encoding="utf-8") as f:
                f.write("\n".join(labels) + "\n")
            total += 1

    for i in range(args.negatives):
        _, bg = random.choice(backgrounds)
        canvas = bg.copy()
        split = split_for(total, args.val_ratio)
        name = f"syn_{profile.get('profile', 'profile')}_negative_{i:04d}.png"
        image_path = os.path.join(args.out, "images", split, name)
        label_path = os.path.join(args.out, "labels", split, os.path.splitext(name)[0] + ".txt")
        cv2.imwrite(image_path, canvas)
        open(label_path, "w", encoding="utf-8").close()
        total += 1

    print()
    print(f"Dataset sintetico salvo em: {args.out}")
    print(f"YAML: {yaml_path}")
    print(f"Imagens geradas: {total}")
    print("Classes com sprite:", ", ".join(m["class_name"] for m in ready_mobs))
    skipped = [m["class_name"] for m in mobs if m["class_id"] not in sprites]
    if skipped:
        print("Classes sem sprite:", ", ".join(skipped))
    return 0


def main():
    if cv2 is None or np is None:
        print("OpenCV/Numpy nao estao instalados neste Python.")
        print("Instale com: python -m pip install opencv-python numpy")
        return 1

    ap = argparse.ArgumentParser(description="Gerar dataset sintetico YOLO com sprites do Divine Pride")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--backgrounds", default=DEFAULT_BACKGROUNDS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--per-class", type=int, default=120)
    ap.add_argument("--negatives", type=int, default=60)
    ap.add_argument("--max-distractors", type=int, default=2)
    ap.add_argument("--val-ratio", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force-download", action="store_true")
    ap.add_argument("--no-clean", action="store_true")
    args = ap.parse_args()
    raise SystemExit(generate(args))


if __name__ == "__main__":
    main()
