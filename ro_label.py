"""
Rotulador simples para treinar YOLO.

Uso:
  python ro_label.py
  python ro_label.py --data datasets/ro_mob/payon_dun04_dataset.yaml

Controles:
  mouse arrastando = desenha uma caixa no mob
  0-9              = seleciona classe pelo ID
  [ ou ]           = classe anterior/proxima
  n ou Enter       = salva e vai para proxima imagem
  d ou Backspace   = remove ultima caixa
  c                = limpa todas as caixas da imagem
  p                = volta uma imagem
  s                = salva sem avancar
  q ou Esc         = sair

Caixas vazias tambem sao salvas. Use isso para frames sem mob.
"""

import argparse
import glob
import hashlib
import os
import shutil

try:
    import cv2
except Exception:
    cv2 = None


RAW_DIR = os.path.join("datasets", "ro_mob", "images", "raw")
TRAIN_IMG_DIR = os.path.join("datasets", "ro_mob", "images", "train")
VAL_IMG_DIR = os.path.join("datasets", "ro_mob", "images", "val")
TRAIN_LABEL_DIR = os.path.join("datasets", "ro_mob", "labels", "train")
VAL_LABEL_DIR = os.path.join("datasets", "ro_mob", "labels", "val")
CLASS_ID = 0
WINDOW = "Rotular mobs YOLO"
CLASSES = {0: "mob"}


state = {
    "img": None,
    "view": None,
    "boxes": [],
    "dragging": False,
    "start": None,
    "current": None,
    "class_id": 0,
}


def ensure_dirs():
    for path in [RAW_DIR, TRAIN_IMG_DIR, VAL_IMG_DIR, TRAIN_LABEL_DIR, VAL_LABEL_DIR]:
        os.makedirs(path, exist_ok=True)


def split_for(name):
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return "val" if int(digest[:8], 16) % 5 == 0 else "train"


def split_dirs(name):
    split = split_for(name)
    if split == "val":
        return VAL_IMG_DIR, VAL_LABEL_DIR
    return TRAIN_IMG_DIR, TRAIN_LABEL_DIR


def image_files():
    exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(RAW_DIR, ext)))
    return sorted(files)


def load_classes_from_yaml(path):
    classes = {}
    if not path or not os.path.exists(path):
        return {CLASS_ID: "mob"}

    in_names = False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "names:":
                in_names = True
                continue
            if in_names:
                if not line.startswith(" ") and not line.startswith("\t"):
                    break
                if ":" not in stripped:
                    continue
                key, value = stripped.split(":", 1)
                try:
                    class_id = int(key.strip())
                except ValueError:
                    continue
                classes[class_id] = value.strip().strip("'\"")

    return classes or {CLASS_ID: "mob"}


def class_name(class_id):
    return CLASSES.get(class_id, f"class_{class_id}")


def normalize_box(box, width, height):
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0, x1), min(width - 1, x2)))
    y1, y2 = sorted((max(0, y1), min(height - 1, y2)))
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    cx = x1 + bw / 2
    cy = y1 + bh / 2
    return cx / width, cy / height, bw / width, bh / height


def denormalize_box(line, width, height):
    parts = line.strip().split()
    if len(parts) != 5:
        return None
    class_id = int(float(parts[0]))
    cx, cy, bw, bh = map(float, parts[1:])
    x1 = int((cx - bw / 2) * width)
    y1 = int((cy - bh / 2) * height)
    x2 = int((cx + bw / 2) * width)
    y2 = int((cy + bh / 2) * height)
    return class_id, x1, y1, x2, y2


def label_path_for(raw_path):
    name = os.path.basename(raw_path)
    _, label_dir = split_dirs(name)
    stem = os.path.splitext(name)[0]
    return os.path.join(label_dir, stem + ".txt")


def load_boxes(raw_path, img):
    path = label_path_for(raw_path)
    if not os.path.exists(path):
        return []
    h, w = img.shape[:2]
    boxes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            box = denormalize_box(line, w, h)
            if box:
                boxes.append(box)
    return boxes


def save_label(raw_path):
    img = state["img"]
    h, w = img.shape[:2]
    name = os.path.basename(raw_path)
    img_dir, label_dir = split_dirs(name)
    dst_img = os.path.join(img_dir, name)
    dst_label = label_path_for(raw_path)

    shutil.copy2(raw_path, dst_img)
    with open(dst_label, "w", encoding="utf-8") as f:
        for item in state["boxes"]:
            class_id, *box = item
            cx, cy, bw, bh = normalize_box(box, w, h)
            f.write(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    print(f"[OK] {name}: {len(state['boxes'])} caixa(s) -> {split_for(name)}")


def draw(raw_path, idx, total):
    img = state["img"].copy()
    for item in state["boxes"]:
        class_id, *box = item
        x1, y1, x2, y2 = box
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, class_name(class_id), (x1, max(18, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

    if state["dragging"] and state["start"] and state["current"]:
        x1, y1 = state["start"]
        x2, y2 = state["current"]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 1)

    atual = f"{state['class_id']}:{class_name(state['class_id'])}"
    txt = f"{idx + 1}/{total}  caixas={len(state['boxes'])}  classe={atual}  split={split_for(os.path.basename(raw_path))}"
    cv2.putText(img, txt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(img, "0-9 classe | [ ] troca classe | N/Enter salva+proxima | D remove | C limpa | Q sai",
                (8, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1)
    state["view"] = img
    cv2.imshow(WINDOW, img)


def on_mouse(event, x, y, flags, userdata):
    if event == cv2.EVENT_LBUTTONDOWN:
        state["dragging"] = True
        state["start"] = (x, y)
        state["current"] = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and state["dragging"]:
        state["current"] = (x, y)
    elif event == cv2.EVENT_LBUTTONUP and state["dragging"]:
        x1, y1 = state["start"]
        x2, y2 = x, y
        if abs(x2 - x1) >= 5 and abs(y2 - y1) >= 5:
            state["boxes"].append((state["class_id"], x1, y1, x2, y2))
        state["dragging"] = False
        state["start"] = None
        state["current"] = None


def trocar_classe(delta):
    ids = sorted(CLASSES)
    if not ids:
        return
    atual = state["class_id"]
    try:
        idx = ids.index(atual)
    except ValueError:
        idx = 0
    state["class_id"] = ids[(idx + delta) % len(ids)]


def main():
    global CLASSES
    if cv2 is None:
        print("OpenCV nao esta instalado neste Python.")
        print("Instale com: python -m pip install opencv-python")
        return

    ap = argparse.ArgumentParser(description="Rotulador YOLO simples/multi-classe")
    ap.add_argument("--data", default=os.path.join("datasets", "ro_mob", "dataset.yaml"),
                    help="YAML do dataset com names:")
    args = ap.parse_args()

    CLASSES = load_classes_from_yaml(args.data)
    state["class_id"] = min(CLASSES)

    ensure_dirs()
    files = image_files()
    if not files:
        print(f"Nenhuma imagem encontrada em {RAW_DIR}")
        print("Capture com: python ro_bot.py --dataset")
        return

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, on_mouse)
    idx = 0
    print("Classes carregadas:")
    for class_id, name in sorted(CLASSES.items()):
        print(f"  {class_id}: {name}")

    while 0 <= idx < len(files):
        raw_path = files[idx]
        img = cv2.imread(raw_path)
        if img is None:
            print(f"[SKIP] Nao abriu: {raw_path}")
            idx += 1
            continue

        state["img"] = img
        state["boxes"] = load_boxes(raw_path, img)
        state["dragging"] = False
        state["start"] = None
        state["current"] = None

        while True:
            draw(raw_path, idx, len(files))
            key = cv2.waitKey(30) & 0xFF
            if key in (27, ord("q")):
                cv2.destroyAllWindows()
                return
            if key in (13, ord("n")):
                save_label(raw_path)
                idx += 1
                break
            if key == ord("s"):
                save_label(raw_path)
            if key in (ord("d"), 8):
                if state["boxes"]:
                    state["boxes"].pop()
            if key == ord("c"):
                state["boxes"].clear()
            if key == ord("p"):
                idx = max(0, idx - 1)
                break
            if ord("0") <= key <= ord("9"):
                class_id = key - ord("0")
                if class_id in CLASSES:
                    state["class_id"] = class_id
            if key == ord("["):
                trocar_classe(-1)
            if key == ord("]"):
                trocar_classe(1)

    cv2.destroyAllWindows()
    print("Fim das imagens.")


if __name__ == "__main__":
    main()
