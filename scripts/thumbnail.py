"""YouTube thumbnails: find the best frames, then build a 1280x720 thumbnail with bold text.

Usage:
  python thumbnail.py candidates VIDEO [--highlights h.json] [--top 8] [--out-dir thumbs]
      Scores frames for sharpness (no motion blur), colour and exposure, drops near-duplicates,
      and writes thumbs/candidates.png (numbered) + candidates.json. Look at the sheet and pick.
  python thumbnail.py make VIDEO@TIME --text "1V4 CLUTCH" [--sub "no way"] [--side left|right]
                      [--color yellow] [--out thumb.jpg]
      Builds the thumbnail: fills 16:9, punches colour/contrast, adds a vignette and huge outlined
      text on one side. Saved as JPG under YouTube's 2 MB limit.
Thumbnail rules that matter: one clear subject, 3-5 words max, readable at phone size.
"""

import argparse
import re
import subprocess
from pathlib import Path

import numpy as np

from common import die, ff_path, ffmpeg, find_font, load_json, need, probe, save_json

SW, SH = 192, 108  # scoring size


def grab_small(video, times):
    frames = []
    for t in times:
        res = subprocess.run(
            [
                need("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{t:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={SW}:{SH}",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
        )
        if len(res.stdout) == SW * SH * 3:
            frames.append((t, np.frombuffer(res.stdout, np.uint8).reshape(SH, SW, 3).astype(float)))
    return frames


def keyframe_times(video, every):
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-skip_frame",
            "nokey",
            "-i",
            str(video),
            "-an",
            "-vf",
            f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{every})',showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def score(img):
    gray = img @ np.array([0.299, 0.587, 0.114])
    gx, gy = np.diff(gray, axis=1), np.diff(gray, axis=0)
    sharp = (np.abs(gx).mean() + np.abs(gy).mean()) / 2  # motion blur kills this
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    bright = gray.mean()
    exposure = 1 - min(1, abs(bright - 120) / 120)  # penalise near-black / blown-out frames
    contrast = gray.std() / 64
    return 0.45 * min(sharp / 12, 1.5) + 0.3 * min(colorful / 60, 1.5) + 0.15 * exposure + 0.1 * min(contrast, 1.5)


def too_similar(a, b):
    ha = np.histogram(a, bins=24, range=(0, 256))[0] / a.size
    hb = np.histogram(b, bins=24, range=(0, 256))[0] / b.size
    return np.abs(ha - hb).sum() < 0.12


def cmd_candidates(a):
    info = probe(a.video)
    if a.highlights:
        peaks = [
            h["peak"]
            for h in load_json(a.highlights)["highlights"]
            if Path(h["source"]).resolve() == Path(a.video).resolve()
        ]
        times = sorted(
            {round(p + d, 2) for p in peaks for d in (-1.0, -0.5, 0, 0.5, 1.0, 1.5) if 0 <= p + d < info["duration"]}
        )
    else:
        every = max(1.0, info["duration"] / 80)
        times = keyframe_times(a.video, every)
    if not times:
        die("No candidate frames found.")
    print(f"Scoring {len(times)} frames ...")
    scored = sorted(((score(img), t, img) for t, img in grab_small(a.video, times)), key=lambda x: -x[0])
    picks = []
    for s, t, img in scored:
        if all(not too_similar(img, p[2]) for p in picks):
            picks.append((s, t, img))
        if len(picks) >= a.top:
            break
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    font = find_font()
    for i, (_, t, _) in enumerate(picks, 1):
        label = (
            (
                f",drawtext=fontfile='{ff_path(font)}':text='#{i}  {t:.1f}s':fontsize=28:fontcolor=white:"
                f"box=1:boxcolor=black@0.7:boxborderw=6:x=10:y=10"
            )
            if font
            else ""
        )
        ffmpeg(
            [
                "-ss",
                f"{t:.3f}",
                "-i",
                a.video,
                "-frames:v",
                "1",
                "-vf",
                f"scale=480:-2{label}",
                str(out / f"cand_{i:02d}.png"),
            ]
        )
    rows = (len(picks) + 3) // 4
    ffmpeg(
        [
            "-i",
            str(out / "cand_%02d.png"),
            "-vf",
            f"tile=4x{rows}:padding=4:margin=4",
            "-frames:v",
            "1",
            str(out / "candidates.png"),
        ]
    )
    save_json(
        {
            "video": str(Path(a.video).resolve()),
            "candidates": [{"n": i, "time": round(t, 2), "score": round(s, 3)} for i, (s, t, _) in enumerate(picks, 1)],
        },
        out / "candidates.json",
    )
    print(f"{out / 'candidates.png'}")
    for i, (_, t, _) in enumerate(picks, 1):
        print(f"  #{i}  {t:.2f}s  score {s:.2f}")


def cmd_make(a):
    if "@" not in a.frame:
        die("Use VIDEO@SECONDS, e.g. match.mp4@123.4")
    video, t = a.frame.rsplit("@", 1)
    font = find_font()
    if not font:
        die("No bold font found on this system for the text.")
    fp = ff_path(font)
    side_x = "w*0.05" if a.side == "left" else "w-text_w-w*0.05"
    words = a.text.upper()
    size = int(min(170, 1280 * 0.55 / max(len(words) * 0.55, 1)))
    txt = words.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "eq=contrast=1.12:saturation=1.3:brightness=0.02,unsharp=5:5:0.8,vignette=PI/5,"
        f"drawtext=fontfile='{fp}':text='{txt}':fontsize={size}:fontcolor={a.color}:borderw=14:bordercolor=black:"
        f"shadowcolor=black@0.6:shadowx=8:shadowy=8:x={side_x}:y=h*0.10"
    )
    if a.sub:
        sub = a.sub.upper().replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
        vf += (
            f",drawtext=fontfile='{fp}':text='{sub}':fontsize={int(size * 0.45)}:fontcolor=white:borderw=8:"
            f"bordercolor=black:x={side_x}:y=h*0.10+{int(size * 1.08)}"
        )
    out = Path(a.out)
    for q in (2, 4, 7):
        ffmpeg(["-ss", t, "-i", video, "-frames:v", "1", "-vf", vf, "-q:v", str(q), str(out)])
        if out.stat().st_size < 2_000_000:
            break
    print(f"{out.resolve()}  ({out.stat().st_size // 1024} KB, 1280x720)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("candidates")
    p.add_argument("video")
    p.add_argument("--highlights")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--out-dir", default="thumbs")
    p = sub.add_parser("make")
    p.add_argument("frame")
    p.add_argument("--text", required=True)
    p.add_argument("--sub")
    p.add_argument("--side", choices=["left", "right"], default="left")
    p.add_argument("--color", default="yellow")
    p.add_argument("--out", default="thumbnail.jpg")
    a = ap.parse_args()
    {"candidates": cmd_candidates, "make": cmd_make}[a.cmd](a)
