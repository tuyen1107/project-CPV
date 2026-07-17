from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import cv2


@dataclass
class Detection:
    class_id: int
    confidence: float
    xyxy: tuple[float, float, float, float]

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run YOLO video demo with rider tracking and temporal label smoothing."
    )
    parser.add_argument("--model", default="best.pt", help="Path to YOLO checkpoint.")
    parser.add_argument(
        "--source",
        required=True,
        help="Input source: video path, webcam index (for example 0), IP camera URL, or YouTube URL.",
    )
    parser.add_argument(
        "--output",
        default="runs/detect/video_demo_tracked.mp4",
        help="Path to output annotated video.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the annotated stream live. Press 'q' to stop.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Process the stream without saving the annotated output video.",
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold.")
    parser.add_argument("--device", default="cpu", help="Inference device.")
    parser.add_argument(
        "--tracker",
        default="bytetrack.yaml",
        help="Ultralytics tracker config name or path.",
    )
    parser.add_argument(
        "--history",
        type=int,
        default=12,
        help="How many recent per-track decisions to keep.",
    )
    parser.add_argument(
        "--upper-rider-ratio",
        type=float,
        default=0.55,
        help="Only detections in the upper portion of the rider box can vote helmet/no_helmet.",
    )
    parser.add_argument(
        "--match-padding",
        type=float,
        default=0.08,
        help="Extra horizontal padding when matching head detections to a rider.",
    )
    parser.add_argument(
        "--min-votes",
        type=int,
        default=4,
        help="Minimum recent votes before showing a stable helmet/no_helmet label.",
    )
    return parser.parse_args()


def point_in_rider_zone(
    point: tuple[float, float],
    rider_box: tuple[float, float, float, float],
    upper_rider_ratio: float,
    match_padding: float,
) -> bool:
    px, py = point
    x1, y1, x2, y2 = rider_box
    width = max(1.0, x2 - x1)
    padded_x1 = x1 - width * match_padding
    padded_x2 = x2 + width * match_padding
    upper_y2 = y1 + (y2 - y1) * upper_rider_ratio
    return padded_x1 <= px <= padded_x2 and y1 <= py <= upper_y2


def choose_vote(
    rider_box: tuple[float, float, float, float],
    detections: list[Detection],
    upper_rider_ratio: float,
    match_padding: float,
) -> str | None:
    best_vote: tuple[str, float] | None = None
    for detection in detections:
        if detection.class_id not in {0, 1}:
            continue
        if not point_in_rider_zone(
            detection.center,
            rider_box,
            upper_rider_ratio=upper_rider_ratio,
            match_padding=match_padding,
        ):
            continue
        vote = "helmet" if detection.class_id == 0 else "no_helmet"
        if best_vote is None or detection.confidence > best_vote[1]:
            best_vote = (vote, detection.confidence)
    return best_vote[0] if best_vote else None


def stable_label(votes: deque[str], min_votes: int) -> str:
    if not votes:
        return "unknown"
    counts = Counter(votes)
    top_label, top_count = counts.most_common(1)[0]
    if top_count < min_votes:
        return "unknown"
    return top_label


def color_for_label(label: str) -> tuple[int, int, int]:
    if label == "helmet":
        return (0, 200, 0)
    if label == "no_helmet":
        return (0, 80, 255)
    return (180, 180, 180)


def is_youtube_url(url: str) -> bool:
    hostname = urlparse(url).netloc.lower()
    return any(domain in hostname for domain in ("youtube.com", "youtu.be", "m.youtube.com"))


def resolve_youtube_source(url: str) -> tuple[str, str]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise SystemExit(
            "YouTube URL detected but 'yt_dlp' is not installed. "
            "Run: pip install yt-dlp"
        ) from exc

    options = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    direct_url = info.get("url")
    if not direct_url:
        raise SystemExit(f"Could not resolve direct stream from YouTube URL: {url}")

    title = info.get("title") or url
    return direct_url, f"YouTube: {title}"


def parse_source(source: str) -> tuple[int | str, str]:
    normalized = source.strip()
    lowered = normalized.lower()

    if normalized.lstrip("-").isdigit():
        camera_index = int(normalized)
        return camera_index, f"webcam[{camera_index}]"

    if lowered.startswith(("rtsp://", "rtmp://", "http://", "https://", "udp://", "tcp://")):
        if is_youtube_url(normalized):
            return resolve_youtube_source(normalized)
        return normalized, normalized

    source_path = Path(normalized).expanduser()
    if source_path.exists():
        resolved = str(source_path.resolve())
        return resolved, resolved

    raise SystemExit(
        "Unsupported --source value. Use a video path, webcam index such as 0, "
        "an IP camera URL such as http://192.168.1.5:4747/video, "
        "or a YouTube URL."
    )


def infer_output_fps(source: int | str) -> float:
    if isinstance(source, int):
        return 25.0

    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        return 25.0

    fps = capture.get(cv2.CAP_PROP_FPS)
    capture.release()
    if fps and fps > 1:
        return float(fps)
    return 25.0


def draw_box(
    frame,
    box: tuple[float, float, float, float],
    text: str,
    color: tuple[int, int, int],
) -> None:
    x1, y1, x2, y2 = [int(v) for v in box]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.rectangle(frame, (x1, max(0, y1 - 26)), (x2, y1), color, -1)
    cv2.putText(
        frame,
        text,
        (x1 + 4, max(16, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    args = parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Ultralytics is not installed. Run: pip install ultralytics") from exc

    source, source_label = parse_source(args.source)

    output_path = None
    if not args.no_save:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    track_votes: dict[int, deque[str]] = defaultdict(lambda: deque(maxlen=args.history))

    stream = model.track(
        source=source,
        stream=True,
        persist=True,
        tracker=args.tracker,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        verbose=False,
    )

    writer = None
    frame_count = 0
    output_fps = infer_output_fps(source)

    try:
        for result in stream:
            frame = result.orig_img.copy()
            boxes = result.boxes
            detections: list[Detection] = []

            if boxes is not None and boxes.xyxy is not None:
                xyxy_list = boxes.xyxy.cpu().tolist()
                cls_list = boxes.cls.int().cpu().tolist()
                conf_list = boxes.conf.cpu().tolist()
                id_list = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(xyxy_list)

                for xyxy, class_id, confidence in zip(xyxy_list, cls_list, conf_list):
                    detections.append(
                        Detection(
                            class_id=int(class_id),
                            confidence=float(confidence),
                            xyxy=tuple(float(v) for v in xyxy),
                        )
                    )

                rider_rows = [
                    (tuple(float(v) for v in xyxy), int(track_id), float(confidence))
                    for xyxy, class_id, confidence, track_id in zip(xyxy_list, cls_list, conf_list, id_list)
                    if int(class_id) == 2 and track_id is not None
                ]

                for rider_box, track_id, rider_conf in rider_rows:
                    vote = choose_vote(
                        rider_box=rider_box,
                        detections=detections,
                        upper_rider_ratio=args.upper_rider_ratio,
                        match_padding=args.match_padding,
                    )
                    if vote is not None:
                        track_votes[track_id].append(vote)

                    label = stable_label(track_votes[track_id], min_votes=args.min_votes)
                    color = color_for_label(label)
                    title = f"id {track_id} rider {label} {rider_conf:.2f}"
                    draw_box(frame, rider_box, title, color)

                for detection in detections:
                    if detection.class_id not in {0, 1}:
                        continue
                    label = "helmet" if detection.class_id == 0 else "no_helmet"
                    draw_box(
                        frame,
                        detection.xyxy,
                        f"{label} {detection.confidence:.2f}",
                        color_for_label(label),
                    )

            if writer is None and output_path is not None:
                height, width = frame.shape[:2]
                writer = cv2.VideoWriter(
                    str(output_path),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    output_fps,
                    (width, height),
                )
                if not writer.isOpened():
                    raise SystemExit(f"Could not open output video for writing: {output_path}")

            if writer is not None:
                writer.write(frame)

            if args.show:
                cv2.imshow("Helmet Demo", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_count += 1
    finally:
        if writer is not None:
            writer.release()
        if args.show:
            cv2.destroyAllWindows()

    print(f"Input source: {source_label}")
    print(f"Output video: {output_path if output_path is not None else 'disabled'}")
    print(f"Frames processed: {frame_count}")
    print(f"Temporal history per rider: {args.history}")
    print(f"Minimum votes for stable label: {args.min_votes}")


if __name__ == "__main__":
    main()
