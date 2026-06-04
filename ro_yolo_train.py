"""
Treina o detector YOLO de mobs.

Fluxo:
  1. Capture frames: python ro_bot.py --dataset
  2. Rotule mobs em formato YOLO:
     datasets/ro_mob/images/train/*.png
     datasets/ro_mob/labels/train/*.txt
     datasets/ro_mob/images/val/*.png
     datasets/ro_mob/labels/val/*.txt
  3. Treine: python ro_yolo_train.py

Instale antes:
  python -m pip install ultralytics
"""

import argparse
import glob
import os
import shutil
import sys


def contar_arquivos(data_dir):
    imgs_train = glob.glob(os.path.join(data_dir, "images", "train", "*.*"))
    imgs_val = glob.glob(os.path.join(data_dir, "images", "val", "*.*"))
    labels_train = glob.glob(os.path.join(data_dir, "labels", "train", "*.txt"))
    labels_val = glob.glob(os.path.join(data_dir, "labels", "val", "*.txt"))
    return len(imgs_train), len(imgs_val), len(labels_train), len(labels_val)


def main():
    ap = argparse.ArgumentParser(description="Treinar YOLO para detectar mobs")
    ap.add_argument("--data", default=os.path.join("datasets", "ro_mob", "dataset.yaml"))
    ap.add_argument("--base", default="yolo11n.pt", help="Modelo base Ultralytics")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default=None, help="Ex.: 0 para GPU, cpu para CPU")
    ap.add_argument("--output", default=os.path.join("models", "mob_yolo.pt"),
                    help="Caminho do modelo final copiado de weights/best.pt")
    args = ap.parse_args()

    try:
        from ultralytics import YOLO
    except Exception:
        print("Ultralytics nao esta instalado.")
        print("Instale com: python -m pip install ultralytics")
        sys.exit(1)

    data_dir = os.path.dirname(args.data)
    n_it, n_iv, n_lt, n_lv = contar_arquivos(data_dir)
    print(f"Dataset: {data_dir}")
    print(f"  train: {n_it} imagem(ns), {n_lt} label(s)")
    print(f"  val  : {n_iv} imagem(ns), {n_lv} label(s)")
    if n_it == 0 or n_iv == 0 or n_lt == 0 or n_lv == 0:
        print()
        print("Dataset incompleto. Rotule e separe imagens em train/val antes de treinar.")
        print("Use uma ferramenta como Label Studio, CVAT, Roboflow ou labelImg exportando formato YOLO.")
        sys.exit(1)

    model = YOLO(args.base)
    kwargs = {
        "data": args.data,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "project": "runs",
        "name": "ro_mob_yolo",
        "exist_ok": True,
    }
    if args.device is not None:
        kwargs["device"] = args.device

    results = model.train(**kwargs)
    save_dir = str(getattr(results, "save_dir", os.path.join("runs", "ro_mob_yolo")))
    best = os.path.join(save_dir, "weights", "best.pt")
    if not os.path.exists(best):
        best = os.path.join("runs", "ro_mob_yolo", "weights", "best.pt")

    if os.path.exists(best):
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        destino = args.output
        shutil.copy2(best, destino)
        print(f"Modelo salvo em: {destino}")
    else:
        print("Treino terminou, mas nao encontrei weights/best.pt.")


if __name__ == "__main__":
    main()
