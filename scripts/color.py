"""Colour correction + looks for vlogs, travel and event footage (gaming montages grade themselves).

Usage:
  python color.py looks VIDEO@SECONDS [--out looks.png]
      One frame shown in every look, labelled, so you can pick by eye.
  python color.py apply VIDEO [--look clean|warm|cinematic|vivid|moody|vintage|none]
                        [--strength 0.7] [--out graded.mp4] [--compare]
      1) Correct: fixes dark/flat exposure and colour casts (blue-ish indoor light, green
         fluorescents) by measuring the footage. Golden-hour warmth is kept on purpose: the white
         balance is only nudged, never forced to neutral.
      2) Look: optional style on top. --strength 0..1 scales the whole thing.
      --compare also writes a before/after image.
      The grade is saved as a .cube LUT next to the output (load it in Premiere, Resolve, CapCut or
      Final Cut). --lut-only writes just the LUT: the fast route for long or 4K videos, since the
      editor applies it in real time on the graphics card.
"""

import argparse
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from common import dec_args, die, ff_path, ffmpeg, find_font, need, probe, safe_copy

# colour part (baked into a LUT) and spatial part (vignette/grain: a LUT can't hold those)
LOOKS = {
    "none": ("", ""),
    "clean": ("", ""),
    "warm": ("colortemperature=temperature=5200:mix=0.7,eq=saturation=1.06", ""),
    "cinematic": (
        "colorbalance=rs=-0.07:gs=0.0:bs=0.10:rh=0.08:gh=0.02:bh=-0.07,eq=contrast=1.08:saturation=0.9",
        "vignette=PI/6",
    ),
    "vivid": ("vibrance=intensity=0.3,eq=contrast=1.07:saturation=1.12", ""),
    "moody": (
        "colorbalance=bs=0.07:bm=0.03:rh=0.03,eq=brightness=-0.035:contrast=1.12:saturation=0.75",
        "vignette=PI/5",
    ),
    "vintage": ("curves=preset=vintage,eq=saturation=0.85", "noise=alls=6:allf=t"),
}
LUT_SIZE = 33  # the size Premiere, Resolve, CapCut and Final Cut all accept


def sample(video, info, n=24, w=160):
    h = int(w * info["height"] / info["width"]) // 2 * 2
    step = max(info["duration"] / n, 0.5)
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            *dec_args(),
            "-i",
            str(video),
            "-an",
            "-vf",
            f"fps=1/{step:.3f},scale={w}:{h}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
    )
    k = len(res.stdout) // (w * h * 3)
    if not k:
        die("Couldn't read frames.")
    return np.frombuffer(res.stdout[: k * w * h * 3], np.uint8).reshape(k, h, w, 3).astype(float) / 255


def correction(frames, strength):
    luma = frames @ np.array([0.2126, 0.7152, 0.0722])
    lo, hi = np.percentile(luma, 1.5), np.percentile(luma, 98.5)
    # levels: stretch toward full range, but never more than the footage needs
    lo_t = min(lo * strength, 0.08)  # input black point moves up toward the measured blacks
    hi_t = max(1 - (1 - hi) * strength, 0.6)  # input white point moves down toward the measured whites
    parts = [
        f"colorlevels=rimin={lo_t:.3f}:gimin={lo_t:.3f}:bimin={lo_t:.3f}:"
        f"rimax={hi_t:.3f}:gimax={hi_t:.3f}:bimax={hi_t:.3f}"
    ]
    # exposure: nudge the mid-tones toward a comfortable middle grey
    mid = np.median((luma - lo_t) / max(hi_t - lo_t, 1e-3))
    gamma = float(np.clip((np.log(0.46) / np.log(max(min(mid, 0.95), 0.05))) ** -1, 0.75, 1.45))
    gamma = 1 + (gamma - 1) * strength
    # white balance: gray-world gains, applied at half strength so warm/cool moods survive
    mean_rgb = frames.reshape(-1, 3).mean(axis=0)
    gains = mean_rgb.mean() / np.maximum(mean_rgb, 1e-3)
    gains = 1 + (np.clip(gains, 0.8, 1.25) - 1) * 0.5 * strength
    parts.append(f"colorchannelmixer=rr={gains[0]:.3f}:gg={gains[1]:.3f}:bb={gains[2]:.3f}")
    sat = float(np.mean(frames.max(axis=3) - frames.min(axis=3)))
    sat_boost = 1 + (0.08 if sat < 0.18 else 0.0) * strength
    parts.append(f"eq=gamma={gamma:.3f}:saturation={sat_boost:.3f}")
    info = {
        "black": round(float(lo), 3),
        "white": round(float(hi), 3),
        "midtone": round(float(mid), 3),
        "gamma": round(gamma, 3),
        "wb_gains": [round(float(g), 3) for g in gains],
    }
    return ",".join(parts), info


def look_chain(look, strength):
    chain = LOOKS[look][0]
    if not chain or strength >= 0.99:
        return chain
    # weaker look: blend the styled frame over the corrected one
    return f"split[a][b];[b]{chain}[s];[a][s]blend=all_mode=normal:all_opacity={strength:.2f}"


def build_lut(chain, path, n=LUT_SIZE):
    """Bake a chain of colour filters into a .cube LUT by running ffmpeg on every lattice colour.
    The same file renders the video here and can be loaded in any editor (real-time on the GPU)."""
    v = np.arange(n) / (n - 1)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")  # .cube order: red changes fastest
    lattice = np.stack([r, g, b], -1).reshape(n, n * n, 3)
    raw = (lattice * 65535 + 0.5).astype("<u2").tobytes()
    if chain:
        # 4:4:4 around eq so no colour is ever averaged with its neighbour in the lattice
        safe = chain.replace("eq=", "format=yuv444p,eq=")
        res = subprocess.run(
            [
                need("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb48le",
                "-s",
                f"{n * n}x{n}",
                "-i",
                "-",
                "-vf",
                f"format=gbrp16le,{safe}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb48le",
                "-",
            ],
            input=raw,
            capture_output=True,
        )
        if res.returncode or len(res.stdout) != len(raw):
            die("Couldn't build the colour LUT: " + res.stderr.decode(errors="replace")[-300:])
        raw = res.stdout
    out = np.frombuffer(raw, "<u2").reshape(-1, 3) / 65535
    with open(path, "w", encoding="utf-8") as f:
        f.write(f'TITLE "pro-editor grade"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        f.write("\n".join(f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in out) + "\n")
    return path


def cmd_apply(a):
    info = probe(a.video)
    if not info["has_video"]:
        die("No video.")
    if a.look not in LOOKS:
        die(f"Unknown look. Choose: {', '.join(LOOKS)}")
    frames = sample(a.video, info)
    corr, stats = correction(frames, a.strength)
    if a.look == "none":
        corr = ""
    color = ",".join(x for x in (corr, look_chain(a.look, a.strength)) if x)
    spatial = LOOKS[a.look][1]
    if spatial and a.strength < 0.99:
        spatial = (
            spatial.replace("PI/6", f"PI/{6 / max(a.strength, 0.2):.2f}")
            .replace("PI/5", f"PI/{5 / max(a.strength, 0.2):.2f}")
            .replace("alls=6", f"alls={max(1, round(6 * a.strength))}")
        )
    out = Path(a.out or Path(a.video).with_name(Path(a.video).stem + f"_{a.look}.mp4"))
    cube = out.with_suffix(".cube")
    build_lut(color, cube)
    print(
        f"Measured: blacks {stats['black']}, whites {stats['white']}, midtones {stats['midtone']} -> "
        f"gamma {stats['gamma']}, white-balance gains {stats['wb_gains']}"
    )
    print(
        f"LUT -> {cube}"
        + (f"  (add the {spatial.split('=')[0]} separately in your editor: LUTs only hold colour)" if spatial else "")
    )
    if a.lut_only:
        return
    with tempfile.TemporaryDirectory() as td:
        lut = safe_copy(cube, td, "grade.cube")
        vf = f"format=gbrpf32le,lut3d=file='{ff_path(lut)}':interp=tetrahedral"
        vf += (f",{spatial}" if spatial else "") + ",format=yuv420p"
        ffmpeg(
            [
                *dec_args(),
                "-i",
                a.video,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(out),
            ],
            hw=True,
        )
    if a.compare:
        t = min(info["duration"] / 2, info["duration"] - 0.1)
        cmp = out.with_suffix(".compare.png")
        ffmpeg(
            [
                "-ss",
                f"{t:.2f}",
                "-i",
                a.video,
                "-ss",
                f"{t:.2f}",
                "-i",
                str(out),
                "-filter_complex",
                "[0:v]scale=640:-2,drawtext=text='BEFORE':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.6:x=10:y=10"
                f"{_font()}[l];[1:v]scale=640:-2,drawtext=text='AFTER':fontcolor=white:fontsize=28:box=1:"
                f"boxcolor=black@0.6:x=10:y=10{_font()}[r];[l][r]hstack",
                "-frames:v",
                "1",
                str(cmp),
            ]
        )
        print(f"Before/after -> {cmp}")
    print(f"Done -> {out}")


def _font():
    f = find_font()
    return f":fontfile='{ff_path(f)}'" if f else ""


def cmd_looks(a):
    if "@" not in a.frame:
        die("Use VIDEO@SECONDS")
    video, t = a.frame.rsplit("@", 1)
    info = probe(video)
    frames = sample(video, info, n=12)
    corr, _ = correction(frames, 0.7)
    names = list(LOOKS)
    with tempfile.TemporaryDirectory() as td:
        for i, name in enumerate(names):
            chain = "" if name == "none" else ",".join(x for x in (corr, *LOOKS[name]) if x)
            label = "original" if name == "none" else name
            vf = (
                f"scale=480:-2{(',' + chain) if chain else ''},drawtext=text='{label}':fontcolor=white:fontsize=26:"
                f"box=1:boxcolor=black@0.6:boxborderw=6:x=10:y=10{_font()}"
            )
            ffmpeg(["-ss", t, "-i", video, "-frames:v", "1", "-vf", vf, str(Path(td) / f"l{i:02d}.png")])
        ffmpeg(["-i", str(Path(td) / "l%02d.png"), "-vf", "tile=4x2:padding=4:margin=4", "-frames:v", "1", a.out])
    print(f"{Path(a.out).resolve()}\n  Looks: {', '.join(n for n in names if n != 'none')} (plus the original)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("looks")
    p.add_argument("frame")
    p.add_argument("--out", default="looks.png")
    p = sub.add_parser("apply")
    p.add_argument("video")
    p.add_argument("--look", default="clean")
    p.add_argument("--strength", type=float, default=0.7)
    p.add_argument("--out")
    p.add_argument("--compare", action="store_true")
    p.add_argument("--lut-only", action="store_true", help="only write the .cube LUT (load it in your editor)")
    a = ap.parse_args()
    {"looks": cmd_looks, "apply": cmd_apply}[a.cmd](a)
