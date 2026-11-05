"""Check a finished render before showing it: what you'd catch by scrubbing through it.

Usage:
  python check_render.py VIDEO [--out-dir check] [--cuts 2.4,5.1,...] [--sections 0,12,30]
  python check_render.py VIDEO --window 12.0 15.5 [--out strip.png]

Full check (writes <out-dir>/report.md and <out-dir>/cuts.png):
  loudness    integrated LUFS and true peak of the whole file, and the level of each section
              (an end card 15 dB under the rest, or music louder than the voice, shows up here)
  cuts        found by picture change (or given with --cuts); for each one a strip of frames
              around it with the waveform under it, and a flag when the audio jumps (a pop)
  black       stretches of black picture
  frozen      stretches where the picture doesn't change (a stuck frame or a dead spot)
  silence     stretches with no sound at all

--window: one filmstrip + waveform image of that stretch, to look at a moment closely.

Claude can't hear the result: this measures it. Report the numbers, don't claim it sounds good.
"""

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from common import need, probe


def run(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def loudness(video, start=None, dur=None):
    pre = ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}"] if start is not None else []
    err = run([*pre, "-i", str(video), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", err)
    tp = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    f = lambda v: float(v) if v and v != "-inf" else float("-inf")  # noqa: E731
    return f(i[-1] if i else None), f(tp[-1] if tp else None)


def scene_cuts(video, thresh=0.32):
    err = run(["-i", str(video), "-an", "-vf", f"select='gt(scene,{thresh})',showinfo", "-f", "null", "-"])
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", err)]


def spans(video, filt, start_key, end_key, extra=None):
    err = run(["-i", str(video), *(extra or []), filt[0], filt[1], "-f", "null", "-"])
    a = [float(x) for x in re.findall(start_key + r"[:=]\s*([\d.]+)", err)]
    b = [float(x) for x in re.findall(end_key + r"[:=]\s*([\d.]+)", err)]
    return list(zip(a, b))


def audio(video, sr=8000):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def pop_at(x, sr, t):
    """How much louder the 10 ms right at t is than the 100 ms around it (dB). Big = a click."""
    i = int(t * sr)
    w, ctx = max(1, sr // 100), sr // 10
    if i - ctx < 0 or i + ctx > len(x):
        return 0.0
    at = np.max(np.abs(x[i - w : i + w])) + 1e-6
    around = np.sqrt(np.mean(np.concatenate([x[i - ctx : i - w], x[i + w : i + ctx]]) ** 2)) + 1e-6
    return float(20 * np.log10(at / (around * 1.414)))


def strip(video, start, end, out, n=8, h=180, x=None, sr=None, marks=()):
    """n frames across [start, end] in a row, waveform under it, cut marks in red."""
    from PIL import Image, ImageDraw

    info = probe(video)
    w = int(h * info["width"] / info["height"]) // 2 * 2
    frames = []
    with tempfile.TemporaryDirectory() as td:
        for k in range(n):
            t = start + (end - start) * (k + 0.5) / n
            f = Path(td) / f"{k}.png"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", str(video), "-frames:v", "1",
                 "-vf", f"scale={w}:{h}", str(f)],
                check=False,
            )  # fmt: skip
            im = Image.open(f).convert("RGB") if f.exists() else Image.new("RGB", (w, h))
            ImageDraw.Draw(im).text((4, 3), f"{t:.2f}s", fill=(255, 220, 0))
            frames.append(im)
    W, wave_h = w * n, 90
    img = Image.new("RGB", (W, h + wave_h), (18, 18, 22))
    for k, im in enumerate(frames):
        img.paste(im, (k * w, 0))
    d = ImageDraw.Draw(img)
    if x is None:
        x, sr = audio(video)
    seg = x[int(max(0, start) * sr) : int(end * sr)]
    if len(seg):
        cols = np.array_split(np.abs(seg), W)
        mid = h + wave_h // 2
        for c, col in enumerate(cols):
            v = float(col.max()) if len(col) else 0.0
            d.line([(c, mid - v * wave_h / 2), (c, mid + v * wave_h / 2)], fill=(90, 200, 230))
    for m in marks:
        if start <= m <= end:
            cx = int((m - start) / (end - start) * W)
            d.line([(cx, 0), (cx, h + wave_h)], fill=(255, 60, 60), width=2)
    img.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out-dir", default="check")
    ap.add_argument("--cuts", help="cut times in seconds, comma separated (default: found by picture change)")
    ap.add_argument("--sections", help="section starts for per-section loudness, e.g. 0,12,30 (default: quarters)")
    ap.add_argument("--window", nargs=2, type=float, metavar=("START", "END"))
    ap.add_argument("--out", help="image path for --window")
    a = ap.parse_args()
    need("ffmpeg")
    video = Path(a.video)
    info = probe(video)
    D = info["duration"]

    if a.window:
        s, e = a.window
        out = a.out or f"strip_{s:.1f}-{e:.1f}.png"
        print(f"Strip -> {strip(video, s, e, out)}")
        return

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Check: {video.name}", "", f"{info['width']}x{info['height']}, {D:.1f} s", ""]
    problems = []

    if info["has_audio"]:
        lufs, TP = loudness(video)
        lines += ["## Loudness", "", f"- whole file: {lufs:.1f} LUFS, true peak {TP:.1f} dBTP"]
        if TP > -1.0:
            problems.append(f"true peak {TP:.1f} dBTP: may clip after upload (aim for -1 or lower)")
        if lufs < -18 or lufs > -10:
            problems.append(f"loudness {lufs:.1f} LUFS: social apps expect about -14")
        starts = [float(v) for v in a.sections.split(",")] if a.sections else [D * k / 4 for k in range(4)]
        edges = [*starts, D]
        levels = []
        for s, e in zip(edges, edges[1:]):
            if e - s >= 1.0:
                li, _ = loudness(video, s, e - s)
                levels.append((s, e, li))
                lines.append(f"- {s:6.1f}-{e:6.1f}s: {li:.1f} LUFS")
        real = [lv for *_, lv in levels if lv > -70]
        if real:
            loudest = max(real)
            for s, e, li in levels:
                if -70 < li < loudest - 10:
                    problems.append(f"{s:.1f}-{e:.1f}s is {loudest - li:.0f} dB quieter than the loudest part")
        lines.append("")
    else:
        lines += ["No audio track.", ""]

    cuts = [float(v) for v in a.cuts.split(",")] if a.cuts else scene_cuts(video)
    x, sr = audio(video) if info["has_audio"] else (np.zeros(1, np.float32), 8000)
    lines += ["## Cuts", "", f"{len(cuts)} cut(s)" + ("" if a.cuts else " found by picture change"), ""]
    pops = []
    for t in cuts:
        db = pop_at(x, sr, t) if info["has_audio"] else 0
        flag = db > 12
        if flag:
            pops.append(t)
        lines.append(f"- {t:7.2f}s" + (f"  audio jumps {db:.0f} dB: likely a click, fade the edges" if flag else ""))
    if pops:
        problems.append(f"possible clicks at {', '.join(f'{t:.2f}s' for t in pops)}")
    if cuts:
        from PIL import Image

        shown = (pops + [c for c in cuts if c not in pops])[:12]
        rows = [strip(video, max(0, t - 0.6), min(D, t + 0.6), out_dir / f"cut_{i:02d}.png", n=6, h=140, x=x,
                      sr=sr, marks=[t]) for i, t in enumerate(sorted(shown))]  # fmt: skip
        ims = [Image.open(r) for r in rows]
        sheet = Image.new("RGB", (max(i.width for i in ims), sum(i.height + 6 for i in ims)), (40, 40, 40))
        y = 0
        for im in ims:
            sheet.paste(im, (0, y))
            y += im.height + 6
        sheet.save(out_dir / "cuts.png")
        for r in rows:
            Path(r).unlink(missing_ok=True)
        lines += ["", "Frames around each cut (red line) with the waveform: cuts.png", ""]

    black = spans(video, ("-vf", "blackdetect=d=0.25:pix_th=0.08"), "black_start", "black_end", ["-an"])
    frozen = spans(video, ("-vf", "freezedetect=n=0.002:d=1.5"), "freeze_start", "freeze_end", ["-an"])
    silent = (
        spans(video, ("-af", "silencedetect=n=-50dB:d=1.0"), "silence_start", "silence_end", ["-vn"])
        if info["has_audio"]
        else []
    )
    for name, sp, note in (
        ("Black", black, "black picture"),
        ("Frozen", frozen, "picture doesn't move"),
        ("Silent", silent, "no sound"),
    ):
        if sp:
            lines += [f"## {name}", ""] + [f"- {s:.2f}-{e:.2f}s ({e - s:.1f}s)" for s, e in sp] + [""]
            for s, e in sp:
                fade = (s < 0.1 or e > D - 0.2) and e - s < 1.5  # a short fade in/out is fine
                if not fade:
                    problems.append(f"{note} {s:.1f}-{e:.1f}s")

    lines = lines[:4] + ["## Problems", ""] + ([f"- {p}" for p in problems] or ["- none found"]) + [""] + lines[4:]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(problems)} problem(s)" + (":" if problems else ""))
    for p in problems:
        print(f"  - {p}")
    print(f"Report -> {out_dir / 'report.md'}" + (f", cut strips -> {out_dir / 'cuts.png'}" if cuts else ""))


if __name__ == "__main__":
    main()
