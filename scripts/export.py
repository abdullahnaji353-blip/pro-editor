"""Export a finished edit for each platform, with optional captions / text.

Usage:
  python export.py INPUT --platforms tiktok youtube [--fit crop|blur] [--out-dir exports]
                   [--srt captions.srt | --transcribe] [--text "TEXT@START-END[@top|center|bottom]" ...]
                   [--trim START-END] [--watermark "@handle"] [--lufs -14 | --no-normalize]

Caption/text times are relative to the (trimmed) clip.

Platforms: tiktok, reels, shorts (9:16 1080x1920), square (1:1), feed (4:5 1080x1350), youtube (16:9).
--fit crop  fills the frame (cuts the sides of 16:9 gameplay).
--fit blur  keeps the whole frame over a blurred copy of itself.
--transcribe needs the optional faster-whisper package (speech captions; useless for music-only edits).
"""

import argparse
import shutil
import tempfile
from pathlib import Path

from common import (
    blur_radius,
    die,
    ff_path,
    ffmpeg,
    find_font,
    frame_size,
    normalize_loudness,
    probe,
    resolve_res,
    safe_copy,
)

PLATFORMS = {
    "tiktok": ("9:16", 1080, 1920, 600),
    "reels": ("9:16", 1080, 1920, 180),
    "shorts": ("9:16", 1080, 1920, 180),
    "square": ("1:1", 1080, 1080, None),
    "feed": ("4:5", 1080, 1350, None),
    "youtube": ("16:9", 1920, 1080, None),
}


def fit_graph(W, H, fit, hud=None, place="bottom"):
    if fit == "hud":
        from layout import hud_graph, resolve_regions

        if not hud:
            die("--fit hud needs --hud regions (presets or x,y,w,h[,scale])")
        return "[0:v]" + hud_graph(W, H, resolve_regions(hud), place)
    if fit == "blur":
        return (
            f"[0:v]split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur={blur_radius(W, H)}:2[bgb];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    return f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"


def parse_text(spec):
    parts = spec.split("@")
    if len(parts) < 2 or "-" not in parts[1]:
        die(f"Bad --text '{spec}'. Use TEXT@START-END or TEXT@START-END@top")
    s, e = parts[1].split("-", 1)
    return {"text": parts[0], "start": float(s), "end": float(e), "position": parts[2] if len(parts) > 2 else "center"}


def drawtext(o, W, H):
    font = find_font()
    txt = o["text"].replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
    from layout import text_y

    y = text_y(o["position"], W, H)
    fontopt = f"fontfile='{ff_path(font)}':" if font else ""
    from layout import text_size

    size = text_size(W, H, o["text"], 0.9)
    return (
        f"drawtext={fontopt}text='{txt}':fontsize={size}:fontcolor=white:borderw=5:"
        f"bordercolor=black:x=(w-text_w)/2:y={y}:enable='between(t,{o['start']},{o['end']})'"
    )


def watermark(tag, W, H):
    """Small semi-transparent tag, top-left, inside the TikTok/Reels safe zone."""
    font = find_font()
    txt = tag.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")
    fontopt = f"fontfile='{ff_path(font)}':" if font else ""
    return (
        f"drawtext={fontopt}text='{txt}':fontsize={int(min(W, H) * 0.04)}:fontcolor=white@0.7:"
        f"borderw=2:bordercolor=black@0.5:x=w*0.05:y=h*0.06"
    )


def transcribe(src, srt_out):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("Speech captions need faster-whisper:  python -m pip install faster-whisper")

    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    model = WhisperModel("small", device="auto", compute_type="int8")
    segments, _ = model.transcribe(str(src), vad_filter=True)
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [str(i), f"{ts(seg.start)} --> {ts(seg.end)}", seg.text.strip(), ""]
    Path(srt_out).write_text("\n".join(lines), encoding="utf-8")
    return srt_out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--platforms", nargs="+", default=["tiktok"], choices=list(PLATFORMS))
    ap.add_argument("--fit", choices=["crop", "blur", "hud"], default="blur")
    ap.add_argument(
        "--res",
        default="1080",
        help="YouTube and Shorts output resolution: 1080, 1440, 2160/4k or "
        "'source' (TikTok/Reels/feed stay 1080p: they downscale anything bigger)",
    )
    ap.add_argument("--hud", nargs="*", help="HUD regions for --fit hud: presets or x,y,w,h[,scale]")
    ap.add_argument("--hud-place", choices=["top", "bottom"], default="bottom")
    ap.add_argument("--out-dir", default="exports")
    ap.add_argument("--srt")
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("--text", action="append", default=[])
    ap.add_argument("--trim", help="START-END in seconds")
    ap.add_argument("--lufs", type=float, default=-14.0, help="loudness target (platforms play ~-14)")
    ap.add_argument("--no-normalize", action="store_true", help="keep the audio level as is")
    ap.add_argument("--watermark", help="small text tag in a corner, e.g. @naji (off unless given)")
    a = ap.parse_args()

    info = probe(a.input)
    if not info["has_video"]:
        die("Input has no video.")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(a.input).stem
    trimmed = None
    if a.trim:  # trim first so caption/text times are relative to the trimmed clip
        s, e = (float(x) for x in a.trim.split("-", 1))
        trimmed = out_dir / f"_{stem}_trim_tmp.mp4"
        ffmpeg(
            [
                "-ss",
                str(s),
                "-i",
                a.input,
                "-t",
                str(e - s),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "16",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                str(trimmed),
            ]
        )
        a.input = str(trimmed)
        info = probe(a.input)
    srt = a.srt
    if a.transcribe:
        srt = transcribe(a.input, out_dir / f"{stem}.srt")
        print(f"Captions -> {srt}")
    texts = [parse_text(t) for t in a.text]

    dur = info["duration"]

    yt_res = resolve_res(a.res, [a.input])
    scratch = tempfile.TemporaryDirectory()  # removed automatically when the script exits
    tmpdir = scratch.name
    done = {}
    for p in a.platforms:
        aspect, W, H, max_len = PLATFORMS[p]
        if p in ("youtube", "shorts"):
            W, H = frame_size(aspect, yt_res)
        out = out_dir / f"{stem}_{p}_{W}x{H}.mp4"
        if (W, H) in done:  # same frame size as an earlier platform: reuse the render
            shutil.copyfile(done[(W, H)], out)
            print(f"{p} -> {out} (same render as {done[(W, H)].name})")
            continue
        if max_len and dur > max_len:
            print(f"WARNING {p}: video is {dur:.0f}s, platform limit is {max_len}s")
        regs = []
        for h in a.hud or []:
            regs.append(dict(zip(["x", "y", "w", "h", "scale"], [float(x) for x in h.split(",")])) if "," in h else h)
        chain = fit_graph(W, H, a.fit if (W < H or a.fit != "hud") else "blur", regs, a.hud_place)
        if srt:
            srt = str(safe_copy(srt, tmpdir, "subs.srt"))
            style = (
                f"FontName=Arial,FontSize={14 if H > W else 18},Bold=1,PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,BorderStyle=1,Outline=3,Alignment=2,MarginV={int(H * 0.06 / 2)}"
            )
            chain += f",subtitles='{ff_path(srt)}':force_style='{style}'"
        for o in texts:
            chain += "," + drawtext(o, W, H)
        if a.watermark:
            chain += "," + watermark(a.watermark, W, H)
        chain += ",format=yuv420p[v]"
        args = ["-i", a.input, "-filter_complex", chain, "-map", "[v]"]
        if info["has_audio"]:
            args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]

        args += [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-profile:v",
            "high",
            "-movflags",
            "+faststart",
            str(out),
        ]
        ffmpeg(args, hw=True)
        if info["has_audio"] and not a.no_normalize:
            normalize_loudness(out, a.lufs)
        done[(W, H)] = out
        print(f"{p} -> {out}")
    if trimmed:
        Path(trimmed).unlink(missing_ok=True)
