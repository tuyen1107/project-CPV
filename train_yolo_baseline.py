from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a YOLO baseline for the helmet dataset.")
    parser.add_argument("--data", default="data/data.yaml", help="Path to YOLO data.yaml")
    parser.add_argument("--model", default="yolov8s.pt", help="Pretrained YOLO checkpoint")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--batch", default="16", help="Batch size, or 'auto'")
    parser.add_argument("--device", default="0", help="CUDA device id, 'cpu', or 'mps'")
    parser.add_argument("--project", default="runs/helmet_project", help="Output project folder")
    parser.add_argument("--name", default="baseline", help="Run name")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics is not installed. Run: pip install ultralytics"
        ) from exc

    data_path = Path(args.data).resolve()
    model = YOLO(args.model)

    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        pretrained=True,
        patience=25,
        cache=False,
        workers=4,
        cos_lr=True,
        close_mosaic=10,
        degrees=0.0,
        perspective=0.0,
        translate=0.05,
        scale=0.30,
        fliplr=0.5,
        mosaic=0.7,
        mixup=0.05,
        copy_paste=0.0,
    )

    model.val(data=str(data_path), imgsz=args.imgsz, device=args.device)


if __name__ == "__main__":
    main()
