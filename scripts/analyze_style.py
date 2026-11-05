"""Break 1+ reference edits down into a reusable "style recipe".

Usage: python analyze_style.py REF1 [REF2 ...] --out-dir style_out [--name my-style]

Writes to --out-dir:
  recipe.json            merged style recipe (feed to build_montage.py)
  <ref>_stats.json       raw numbers per reference
  <ref>_sheet.png        contact sheet: one frame from the middle of each shot (look at it!)
  <ref>_cuts.png         frames just before / on / after the first cuts (shows transitions)

What it measures: aspect ratio, fps, shot length + pace, how tightly cuts land on the beat,
cuts-per-beat, brightness/saturation/contrast, white/black flash frequency, motion intensity.
What it can NOT measure reliably (Claude should judge from the sheets): zoom/shake style,
text style, speed ramps, overlays, specific transitions.
"""

import argparse
import re
import statistics as st
import subprocess
import tempfile
from pathlib import Path

from common import dec_args, die, ffmpeg, need, probe, run, save_json

CUT_FPS = 30
HIST_THRESHOLD = 0.22  # min colour-histogram change for a cut
LOCAL_RATIO = 3.0  # and it must stand out this much vs nearby frames (ignores fast camera motion)


def _histograms(path, w=64, h=36, bins=16, chunk=900):
    """Per-frame colour histograms (n, 3, bins), normalised. Streams the video in chunks so even
    a 45-minute file never sits in memory at once."""
    import numpy as np

    proc = subprocess.Popen(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            *dec_args(),
            "-i",
            str(path),
            "-an",
            "-vf",
            f"fps={CUT_FPS},scale={w}:{h}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    fsize = w * h * 3
    out = []
    while True:
        buf = proc.stdout.read(fsize * chunk)
        n = len(buf) // fsize
        if n == 0:
            break
        fr = np.frombuffer(buf[: n * fsize], dtype=np.uint8).reshape(n, h * w, 3)
        q = (fr // (256 // bins)).astype(np.int64)  # bin per pixel and channel
        offs = (np.arange(n)[:, None] * 3 + np.arange(3)[None, :]) * bins  # (n, 3) slot of each histogram
        counts = np.bincount((q + offs[:, None, :]).ravel(), minlength=n * 3 * bins).reshape(n, 3, bins)
        out.append(counts / float(h * w))
    proc.wait()
    return np.concatenate(out) if out else np.zeros((0, 3, bins))


def scene_cuts(path):
    """Content-based cut detection: global colour-histogram jumps that stand out locally.

    Histograms barely move during fast pans/flicks or noisy footage, so gameplay motion
    doesn't fake cuts the way pixel-difference detectors do. One-to-three-frame flashes
    (frame goes white/black then returns to the same shot) are not counted as cuts.
    """
    import numpy as np

    hist = _histograms(path)
    n = len(hist)
    if n < 3:
        return []

    def hd(i, j):
        return float(np.abs(hist[i] - hist[j]).sum(axis=1).mean() / 2)  # 0..1

    d = np.concatenate([[0.0], np.abs(np.diff(hist, axis=0)).sum(axis=2).mean(axis=1) / 2])
    cuts = []
    for i in np.nonzero(d >= HIST_THRESHOLD)[0]:  # only frames that could be cuts
        if i < 1:
            continue
        lo, hi = max(1, i - 15), min(n, i + 16)
        neigh = np.delete(d[lo:hi], i - lo)
        if d[i] < LOCAL_RATIO * (np.median(neigh) + 0.01):
            continue
        # flash check: does the picture return to the previous shot within 3 frames?
        if any(i + k < n and hd(i + k, i - 1) < HIST_THRESHOLD * 0.6 for k in (1, 2, 3)):
            continue
        t = round(int(i) / CUT_FPS, 3)
        # effects that settle a few frames after a cut (flash fading, RGB glitch ending, zoom
        # snapping back) look like a second cut: ignore changes within ~5 frames of the last cut
        if not cuts or t - cuts[-1] > 0.17:
            cuts.append(t)
    return cuts


def frame_stats(path, fps=10, limit=None, keyframes_only=False):
    lim = ["-t", str(limit)] if limit else []
    if keyframes_only:  # much faster: only decodes keyframes (fine for average colour)
        lim += ["-skip_frame", "nokey"]
    res = run(
        [
            need("ffmpeg"),
            "-hide_banner",
            *dec_args(),
            *lim,
            "-i",
            str(path),
            "-an",
            "-vf",
            f"fps={fps},scale=160:-2,signalstats,metadata=print:file=-",
            "-f",
            "null",
            "-",
        ]
    )
    frames, cur = [], {}
    for line in res.stdout.splitlines():
        if line.startswith("frame:"):
            if cur:
                frames.append(cur)
            cur = {}
        m = re.match(r"lavfi\.signalstats\.(YAVG|SATAVG|YLOW|YHIGH|YDIF)=([\d.]+)", line)
        if m:
            cur[m.group(1)] = float(m.group(2))
    if cur:
        frames.append(cur)
    return frames


def count_flashes(frames, fps=10):
    """A flash = brightness spikes up (or down) hard vs the previous frame and comes back quickly."""
    y = [f.get("YAVG", 0) for f in frames]
    flashes = 0
    i = 1
    while i < len(y) - 1:
        if abs(y[i] - y[i - 1]) > 45 and abs(y[i] - y[min(i + 3, len(y) - 1)]) > 30:
            flashes += 1
            i += 3
        else:
            i += 1
    return flashes


def make_sheet(path, times, out_png, cols=4, width=320):
    if not times:
        return None
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            ffmpeg(
                [
                    "-ss",
                    f"{max(t, 0):.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={width}:-2",
                    str(Path(td) / f"f{i:03d}.png"),
                ]
            )
        n = len(times)
        rows = (n + cols - 1) // cols
        ffmpeg(
            [
                "-framerate",
                "1",
                "-i",
                str(Path(td) / "f%03d.png"),
                "-vf",
                f"tile={cols}x{rows}:padding=4:margin=4:color=black",
                "-frames:v",
                "1",
                str(out_png),
            ]
        )
    return str(out_png)


def analyze_one(path, out_dir):
    from beats import analyze as beat_analyze

    info = probe(path)
    if not info["has_video"]:
        die(f"{path} has no video stream")
    dur = info["duration"]
    cuts = [c for c in scene_cuts(path) if 0.15 < c < dur - 0.15]
    bounds = [0.0] + cuts + [dur]
    shots = [round(b - a, 3) for a, b in zip(bounds, bounds[1:]) if b - a > 0.04]

    stats = {
        "file": info["path"],
        "duration": round(dur, 2),
        "width": info["width"],
        "height": info["height"],
        "fps": info["fps"],
        "aspect": "9:16"
        if info["height"] > info["width"] * 1.3
        else "1:1"
        if abs(info["height"] - info["width"]) < info["width"] * 0.1
        else "16:9",
        "cuts": cuts,
        "num_shots": len(shots),
        "median_shot_sec": round(st.median(shots), 3) if shots else dur,
        "mean_shot_sec": round(st.mean(shots), 3) if shots else dur,
        "shortest_shot_sec": min(shots) if shots else dur,
        "cuts_per_sec": round(len(cuts) / dur, 3) if dur else 0,
    }

    # beat relationship
    stats.update({"tempo_bpm": None, "beat_sync_pct": None, "cut_every_beats": None})
    if info["has_audio"]:
        try:
            b = beat_analyze(path)
            beats = b["beats"]
            stats["tempo_bpm"] = b["tempo_bpm"]
            if beats and cuts:
                # A cut is "on the music" if it lands within ~1.5 frames of a beat or a hit/onset.
                tol = 0.05
                marks = sorted(set(beats) | set(b.get("onsets", [])))
                hits = sum(1 for c in cuts if min(abs(c - x) for x in marks) <= tol)
                stats["beat_sync_pct"] = round(100 * hits / len(cuts), 1)
                # what random cutting would score, given how busy the music is
                covered, last = 0.0, -1.0
                for m in marks:
                    lo, hi = max(m - tol, last), m + tol
                    covered += max(0.0, hi - lo)
                    last = max(last, hi)
                stats["random_sync_pct"] = round(100 * min(1.0, covered / max(dur, 0.1)), 1)
                beat_len = 60 / b["tempo_bpm"] if b["tempo_bpm"] else 0.5
                raw = stats["median_shot_sec"] / beat_len
                stats["cut_every_beats"] = min([0.5, 1, 2, 4, 8], key=lambda k: abs(k - raw))
        except Exception as e:  # beat tracking is best-effort
            stats["beat_error"] = str(e)[:200]

    frames = frame_stats(path)
    if frames:
        ya = [f.get("YAVG", 0) for f in frames]
        sat = [f.get("SATAVG", 0) for f in frames]
        con = [f.get("YHIGH", 0) - f.get("YLOW", 0) for f in frames]
        dif = [f.get("YDIF", 0) for f in frames[1:]] or [0]
        stats.update(
            {
                "brightness": round(st.mean(ya) / 255, 3),
                "saturation": round(st.mean(sat) / 128, 3),
                "contrast": round(st.mean(con) / 255, 3),
                "motion_intensity": round(st.mean(dif) / 255, 4),
                "flashes_per_min": round(count_flashes(frames) / (dur / 60), 2) if dur else 0,
            }
        )

    stem = Path(path).stem
    mids = [round(a + (b - a) / 2, 3) for a, b in zip(bounds, bounds[1:])][:16]
    stats["sheet"] = make_sheet(path, mids, Path(out_dir) / f"{stem}_sheet.png")
    around = []
    for c in cuts[:4]:
        around += [c - 0.12, c + 0.02, c + 0.15]
    stats["cuts_sheet"] = make_sheet(path, around, Path(out_dir) / f"{stem}_cuts.png", cols=3, width=240)
    save_json(stats, Path(out_dir) / f"{stem}_stats.json")
    return stats


def merge(all_stats, name):
    def avg(key):
        vals = [s[key] for s in all_stats if s.get(key) is not None]
        return round(st.mean(vals), 3) if vals else None

    aspects = [s["aspect"] for s in all_stats]
    ceb = [s["cut_every_beats"] for s in all_stats if s.get("cut_every_beats")]
    sync = avg("beat_sync_pct")
    chance = avg("random_sync_pct") or 0
    flashes = avg("flashes_per_min") or 0
    motion = avg("motion_intensity") or 0
    return {
        "name": name,
        "source_refs": [s["file"] for s in all_stats],
        "format": {"aspect": max(set(aspects), key=aspects.count), "fps": 60 if (avg("fps") or 30) > 45 else 30},
        "pacing": {
            "median_shot_sec": avg("median_shot_sec"),
            "cut_every_beats": st.median(ceb) if ceb else 2,
            "beat_sync_pct": sync,
            "random_sync_pct": chance,
            "snap_cuts_to_beats": sync is None or sync >= chance + 15,
            "tempo_bpm_ref": avg("tempo_bpm"),
        },
        "color": {"brightness": avg("brightness"), "saturation": avg("saturation"), "contrast": avg("contrast")},
        "effects": {
            "_note": "Starting guesses from the numbers. Claude should adjust after viewing the contact sheets.",
            "flash_on_strong_beats": flashes >= 2,
            "flash_color": "white",
            "zoom_punch_on_beats": motion > 0.06 or flashes >= 2,
            "zoom_amount": 1.12,
            "shake_on_drops": motion > 0.08,
            "slowmo_on_drops": True,
            "slowmo_speed": 0.5,
            "letterbox": False,
            "text_overlays": [],
        },
        "measured": {"flashes_per_min": flashes, "motion_intensity": motion},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--out-dir", default="style_out")
    ap.add_argument("--name", default="custom-style")
    a = ap.parse_args()
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    stats = []
    for r in a.refs:
        print(f"Analyzing {r} ...")
        s = analyze_one(r, a.out_dir)
        print(
            f"  {s['num_shots']} shots, median {s['median_shot_sec']}s, beat sync {s['beat_sync_pct']}% "
            f"(random would be {s.get('random_sync_pct')}%), tempo {s['tempo_bpm']}"
        )
        stats.append(s)
    recipe = merge(stats, a.name)
    save_json(recipe, Path(a.out_dir) / "recipe.json")
    print(f"Recipe -> {Path(a.out_dir) / 'recipe.json'}")
