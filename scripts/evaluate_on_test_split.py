from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a YOLO checkpoint on the test split of a YOLO dataset."
    )
    parser.add_argument(
        "--model",
        default="best.pt",
        help="Path to the YOLO checkpoint.",
    )
    parser.add_argument(
        "--data",
        default="data_3class_with_test/data.yaml",
        help="Path to the YOLO data.yaml file.",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Validation image size.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Validation device.",
    )
    parser.add_argument(
        "--output-json",
        default="test_metrics_summary.json",
        help="Where to save the summarized metrics JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Ultralytics is not installed. Run: pip install ultralytics") from exc

    model = YOLO(args.model)
    metrics = model.val(
        data=str(Path(args.data).resolve()),
        split="test",
        imgsz=args.imgsz,
        device=args.device,
        verbose=False,
    )

    names = getattr(metrics, "names", None) or getattr(model, "names", {})
    box = metrics.box
    class_index = list(getattr(box, "ap_class_index", []))
    map50_by_class = list(getattr(box, "ap50", []))
    map95_by_class = list(getattr(box, "ap", []))

    class_metrics: list[dict[str, object]] = []
    for idx, class_id in enumerate(class_index):
        class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
        class_metrics.append(
            {
                "class_id": int(class_id),
                "class_name": class_name,
                "map50": float(map50_by_class[idx]),
                "map50_95": float(map95_by_class[idx]),
            }
        )

    summary = {
        "model": str(Path(args.model).resolve()),
        "data": str(Path(args.data).resolve()),
        "split": "test",
        "imgsz": args.imgsz,
        "precision": float(box.mp),
        "recall": float(box.mr),
        "map50": float(box.map50),
        "map50_95": float(box.map),
        "class_metrics": class_metrics,
        "save_dir": str(metrics.save_dir),
    }

    output_path = Path(args.output_json).resolve()
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Model: {summary['model']}")
    print(f"Data: {summary['data']}")
    print("Split: test")
    print(f"Precision: {summary['precision']:.4f}")
    print(f"Recall: {summary['recall']:.4f}")
    print(f"mAP50: {summary['map50']:.4f}")
    print(f"mAP50-95: {summary['map50_95']:.4f}")
    for item in class_metrics:
        print(
            f"{item['class_name']}: "
            f"mAP50={item['map50']:.4f}, mAP50-95={item['map50_95']:.4f}"
        )
    print(f"Saved summary to {output_path}")
    print(f"Ultralytics save dir: {summary['save_dir']}")


if __name__ == "__main__":
    main()
