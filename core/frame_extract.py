from pathlib import Path

import cv2


def extract_last_frame(video_path, out_png):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video_path}")
    last = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        last = frame
    cap.release()
    if last is None:
        raise RuntimeError(f"no frames in {video_path}")
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_png), last)
    height, width = last.shape[:2]
    return out_png, (width, height)


def probe_video(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps else 0.0
    cap.release()
    return {"width": width, "height": height, "fps": fps, "duration": duration}