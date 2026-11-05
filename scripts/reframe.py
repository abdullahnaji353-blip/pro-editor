"""Vertical crop that follows a face, like a camera operator: holds still while you move a little,
glides smoothly when you leave the middle of the frame.

Usage: python reframe.py VIDEO [--out vertical.mp4] [--aspect 9:16] [--keyframes "0:0.5,8:0.3"]
                         [--deadzone 0.12] [--preview]

Face detection uses OpenCV's built-in face detector (pip install "opencv-python-headless<5";
OpenCV 5 no longer ships the detector files). No face found -> centre crop, with a warning.
--keyframes sets the crop centre by hand (time:fraction of width), e.g. to stay on one person
when two are talking, or to fix a spot where detection picked the wrong face.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from common import dec_args, die, ffmpeg, frame_size, need, normalize_loudness, probe, resolve_res

SAMPLE_FPS = 6
DET_W = 640


def detect_faces(video, info):
    """Return (times, centres as fraction of width or nan, sizes as fraction of height)."""
    try:
        import cv2
    except ImportError:
        die('Face tracking needs OpenCV:  python -m pip install "opencv-python-headless<5"')
    xml = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not xml.exists():
        die('This OpenCV has no face detector files (OpenCV 5+). Run: python -m pip install "opencv-python-headless<5"')
    det = cv2.CascadeClassifier(str(xml))
    h = int(DET_W * info["height"] / info["width"]) // 2 * 2
    proc = subprocess.Popen([need("ffmpeg"), "-hide_banner", "-loglevel", "error", *dec_args(), "-i", str(video), "-an",
                             "-vf", f"fps={SAMPLE_FPS},scale={DET_W}:{h},format=gray", "-f", "rawvideo", "-"],
                            stdout=subprocess.PIPE)
    frame_bytes = DET_W * h
    times, cx, sz = [], [], []
    prev = None
    i = 0
    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        img = np.frombuffer(buf, np.uint8).reshape(h, DET_W)
        faces = det.detectMultiScale(img, scaleFactor=1.12, minNeighbors=5, minSize=(int(h * 0.07),) * 2)
        c, s = float("nan"), 0.0
        if len(faces):
            # biggest face, but prefer staying on the same person between samples
            def rank(f):
                x, y, w, hh = f
                centre = (x + w / 2) / DET_W
                stick = 0.0 if prev is None else abs(centre - prev)
                return w * hh * (1.0 - min(stick, 0.5))
            x, y, w, hh = max(faces, key=rank)
            c, s = (x + w / 2) / DET_W, hh / h
            prev = c
        times.append(i / SAMPLE_FPS)
        cx.append(c)
        sz.append(s)
        i += 1
    proc.wait()
    return np.array(times), np.array(cx), np.array(sz)


def camera_path(times, cx, crop_frac, deadzone):
    """Simulate a smooth operator. Returns crop-centre fraction per sample."""
    valid = ~np.isnan(cx)
    if not valid.any():
        return np.full(len(times), 0.5), 0.0
    # hold the last known face position through gaps (look-away, motion blur)
    filled = cx.copy()
    last = cx[valid][0]
    for k in range(len(filled)):
        if np.isnan(filled[k]):
            filled[k] = last
        else:
            last = filled[k]
    # light median to kill single-sample detector jumps
    med = np.array([np.median(filled[max(0, k - 2):k + 3]) for k in range(len(filled))])
    half = crop_frac / 2
    cam = np.empty_like(med)
    c = float(np.clip(med[0], half, 1 - half))
    for k, target in enumerate(med):
        target = float(np.clip(target, half, 1 - half))
        off = target - c
        if abs(off) > deadzone * crop_frac:          # face left the comfortable middle of the shot
            c += off * 0.22                           # glide (about 0.5 s to settle)
        cam[k] = c
    return cam, float(valid.mean())


def manual_path(times, spec, crop_frac):
    pts = sorted((float(a), float(b)) for a, b in (p.split(":") for p in spec.split(",")))
    half = crop_frac / 2
    xs, ys = [p[0] for p in pts], [min(max(p[1], half), 1 - half) for p in pts]
    return np.interp(times, xs, ys)


def render(video, info, cam_times, cam, crop_frac, out, W, H, preview):
    src_w, src_h = info["width"], info["height"]
    cw = int(src_w * crop_frac) // 2 * 2
    fps = round(info["fps"] or 30)
    # one command per output frame while the camera moves, interpolated -> smooth pans
    t_out = np.arange(0, info["duration"], 1 / fps)
    xs = np.interp(t_out, cam_times, cam) * src_w - cw / 2
    xs = np.clip(np.round(xs), 0, src_w - cw).astype(int)
    lines, last = [], None
    for t, x in zip(t_out, xs):
        if x != last:
            lines.append(f"{t:.4f} crop@c x {x};")
            last = x
    if preview:
        W, H = W // 4 * 2, H // 4 * 2
    with tempfile.TemporaryDirectory() as td:
        cmds = Path(td) / "cmds.txt"
        cmds.write_text("\n".join(lines) + "\n", encoding="utf-8")
        enc = ["-preset", "veryfast", "-crf", "24"] if preview else ["-preset", "medium", "-crf", "18"]
        cpath = cmds.as_posix().replace(":", "\\:")
        ffmpeg(["-i", str(video), "-vf",
                f"sendcmd=f='{cpath}',crop@c=w={cw}:h={src_h}:x={xs[0]}:y=0,scale={W}:{H},setsar=1,format=yuv420p",
                "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", *enc, "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(out)], hw=True)
    return len(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", default="vertical.mp4")
    ap.add_argument("--aspect", choices=["9:16", "4:5", "1:1"], default="9:16")
    ap.add_argument("--keyframes", help='manual crop centres "time:fraction,..." (overrides face tracking)')
    ap.add_argument("--deadzone", type=float, default=0.12, help="how far you can move before the camera follows")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--res", default="1080", help="output short side: 1080 (TikTok/Reels max), 1440, 2160, source (bigger only helps YouTube Shorts)")
    a = ap.parse_args()

    info = probe(a.video)
    if not info["has_video"]:
        die("No video stream.")
    aw, ah = {"9:16": (9, 16), "4:5": (4, 5), "1:1": (1, 1)}[a.aspect]
    W, H = frame_size(a.aspect, resolve_res(a.res, [a.video]))
    crop_frac = (info["height"] * aw / ah) / info["width"]
    if crop_frac >= 1:
        # already vertical (phone footage): nothing to track, just fit it to the target size
        print("Already vertical: fitting it to the target size instead of reframing.")
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p")
        if a.preview:
            vf = vf.replace(f"scale={W}:{H}", f"scale={W // 2}:{H // 2}").replace(f"crop={W}:{H}", f"crop={W // 2}:{H // 2}")
        ffmpeg(["-i", a.video, "-vf", vf, "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
                "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(a.out)], hw=True)
        print(f"Done -> {a.out}")
        raise SystemExit(0)
    if a.keyframes:
        times = np.arange(0, info["duration"] + 1 / SAMPLE_FPS, 1 / SAMPLE_FPS)
        cam, found = manual_path(times, a.keyframes, crop_frac), 1.0
        print("Using manual keyframes.")
    else:
        print("Finding faces ...")
        times, cx, _ = detect_faces(a.video, info)
        cam, found = camera_path(times, cx, crop_frac, a.deadzone)
        print(f"  face found in {found * 100:.0f}% of samples")
        if found < 0.2:
            print("  Warning: little or no face found, so this is mostly a centre crop. For gameplay use "
                  "export.py --fit hud/blur; for people off-centre use --keyframes.")
    n = render(a.video, info, times, cam, crop_frac, a.out, W, H, a.preview)
    if info["has_audio"]:
        normalize_loudness(a.out, -14.0)
    print(f"Done -> {a.out} ({n} camera moves)")
