"""Edit ONE clip from a list of timed operations ("slow-mo on the last kill, then speed back up").

Usage: python clip_fx.py INPUT EDIT.json [--out out.mp4] [--preview]

EDIT.json (times are seconds in the INPUT clip unless an op says "time": "output"):
{
  "trim": [2.0, 14.5],                 // optional
  "aspect": "keep",                    // keep | 16:9 | 9:16 | 1:1 | 4:5
  "fit": "crop",                       // crop | blur (only when changing aspect)
  "fps": 60,
  "slowmo_audio": "stretch",           // stretch (time-stretched game audio) | mute
  "ops": [
    {"type": "speed",  "start": 4.0, "end": 6.0, "speed": 0.35},
    {"type": "ramp",   "at": 8.2, "fast": 2.0, "slow": 0.4, "before": 0.8, "after": 0.6},
    {"type": "freeze", "at": 9.0, "dur": 0.7},
    {"type": "zoom",   "at": 8.2, "amount": 1.18},
    {"type": "flash",  "at": 8.2, "color": "white"},
    {"type": "shake",  "at": 8.2, "dur": 0.6},
    {"type": "rgb",    "at": 8.2},
    {"type": "text",   "text": "1v3", "start": 0, "end": 1.5, "position": "top"}
  ],
  "music": {"file": "song.mp3", "start": 30.0, "volume": 1.0, "game_volume": 0.3},   // optional
  "normalize_lufs": -14
}
(Comments are for reading only; real JSON can't contain them.)

speed/ramp ranges must not overlap. Motion blur is added automatically to fast (>1.4x) parts.
Prints the source->output time map so text/effects can be checked against the result.
"""

import argparse
import tempfile
from pathlib import Path

from common import (
    blur_radius,
    concat_line,
    die,
    ff_path,
    ffmpeg,
    find_font,
    frame_size,
    load_json,
    normalize_loudness,
    preview_size,
    probe,
    resolve_res,
    save_json,
)


def build_pieces(spec, dur):
    t0, t1 = spec.get("trim") or [0.0, dur]
    t0, t1 = max(0.0, float(t0)), min(dur, float(t1))
    ranges = []
    for op in spec.get("ops", []):
        if op["type"] == "speed":
            ranges.append((float(op["start"]), float(op["end"]), float(op["speed"])))
        elif op["type"] == "ramp":
            at = float(op["at"])
            ranges.append((at - float(op.get("before", 0.8)), at, float(op.get("fast", 2.0))))
            ranges.append((at, at + float(op.get("after", 0.6)), float(op.get("slow", 0.4))))
    ranges = sorted((max(a, t0), min(b, t1), s) for a, b, s in ranges if b > t0 and a < t1)
    for (_, b1, _), (a2, _, _) in zip(ranges, ranges[1:]):
        if a2 < b1 - 1e-6:
            die(f"Speed ranges overlap around {a2:.2f}s. Adjust the ops.")
    freezes = sorted(
        (float(o["at"]), float(o.get("dur", 0.7)))
        for o in spec.get("ops", [])
        if o["type"] == "freeze" and t0 <= float(o["at"]) <= t1
    )
    # split timeline into pieces at every range edge and freeze point
    cuts = sorted({t0, t1, *[x for a, b, _ in ranges for x in (a, b)], *[f for f, _ in freezes]})
    pieces = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 1e-3:
            continue
        spd = next((s for ra, rb, s in ranges if ra <= a + 1e-6 and b <= rb + 1e-6), 1.0)
        pieces.append({"kind": "play", "a": a, "b": b, "speed": spd})
    for at, fd in freezes:  # insert freeze before the piece starting at `at`
        idx = next((i for i, p in enumerate(pieces) if abs(p["a"] - at) < 1e-6), len(pieces))
        pieces.insert(idx, {"kind": "freeze", "a": at, "b": at, "speed": 0, "dur": fd})
    t = 0.0
    for p in pieces:
        p["out_start"] = t
        t += p["dur"] if p["kind"] == "freeze" else (p["b"] - p["a"]) / p["speed"]
        p["out_end"] = t
    return pieces


def src_to_out(pieces, s):
    for p in pieces:
        if p["kind"] == "play" and p["a"] - 1e-6 <= s <= p["b"] + 1e-6:
            return p["out_start"] + (s - p["a"]) / p["speed"]
    return None


def atempo_chain(speed):
    parts, s = [], speed
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts)


def fit_chain(W, H, fit):
    if not W:
        return "null"
    if fit == "blur":
        return (
            f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur={blur_radius(W, H)}:2[bgb];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
        )
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


def piece_video_filter(p, spec, W, H, fps, events):
    parts = [fit_chain(W, H, spec.get("fit", "crop")), "setsar=1"]
    if p["kind"] == "play" and p["speed"] != 1:
        if p["speed"] > 1.4:
            parts.append("tmix=frames=3")
        parts.append(f"setpts=(PTS-STARTPTS)/{p['speed']}")
        parts.append(f"framerate=fps={fps}" if p["speed"] < 1 else f"fps={fps}")
    else:
        parts.append(f"fps={fps}")
    for ev in events:  # times local to this piece's output
        T = ev["local"]
        if ev["type"] == "zoom":
            z = float(ev.get("amount", 1.15)) - 1
            parts.append(
                f"zoompan=z='1+{z:.3f}*gte(it\\,{T:.3f})*pow(max(0\\,1-(it-{T:.3f})/0.3)\\,2)':d=1:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W or 'iw'}x{H or 'ih'}:fps={fps}"
            )
        elif ev["type"] == "shake":
            d = float(ev.get("dur", 0.6))
            parts.append(
                f"scale=trunc(iw*1.06/2)*2:trunc(ih*1.06/2)*2,"
                f"crop=trunc(iw/1.06/2)*2:trunc(ih/1.06/2)*2:"
                f"x='(iw-ow)/2+(iw-ow)/2*sin(t*47)*exp(-(t-{T:.3f})*3)*between(t\\,{T:.3f}\\,{T + d:.3f})':"
                f"y='(ih-oh)/2+(ih-oh)/2*cos(t*39)*exp(-(t-{T:.3f})*3)*between(t\\,{T:.3f}\\,{T + d:.3f})'"
            )
        elif ev["type"] == "flash":
            sign = -1 if ev.get("color", "white") == "black" else 1
            parts.append(
                f"eq=eval=frame:brightness='{sign}*between(t\\,{T:.3f}\\,{T + 0.15:.3f})*(1-(t-{T:.3f})/0.15)'"
            )
        elif ev["type"] == "rgb":
            px = max(2, int(14 * (W or 1920) / 1080))
            parts.append(f"rgbashift=rh=-{px}:bh={px}:enable='between(t,{T:.3f},{T + 0.15:.3f})'")
    parts += ["tpad=stop_mode=clone:stop=-1", "format=yuv420p"]
    return ",".join(parts)


def text_filters(spec, pieces, W, H):
    font = find_font()
    out = []
    for o in spec.get("ops", []):
        if o["type"] != "text":
            continue
        if o.get("time") == "output":
            s, e = float(o.get("start", 0)), float(o.get("end", 2))
        else:
            s = src_to_out(pieces, float(o.get("start", 0)))
            e = src_to_out(pieces, float(o.get("end", 2)))
            if s is None or e is None:
                print(f"WARNING: text '{o['text']}' falls outside the kept range; skipped")
                continue
        txt = str(o["text"]).replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
        from layout import text_size, text_y

        size = text_size(W, H, o["text"])
        y = text_y(o.get("position", "top"), W, H)
        fontopt = f"fontfile='{ff_path(font)}':" if font else ""
        out.append(
            f"drawtext={fontopt}text='{txt}':fontsize={size}:fontcolor=white:borderw=6:bordercolor=black:"
            f"x=(w-text_w)/2:y={y}:enable='between(t,{s:.3f},{e:.3f})'"
        )
    return ",".join(out)


def render(inp, spec, out_path, preview=False):
    info = probe(inp)
    if not info["has_video"]:
        die("Input has no video.")
    pieces = build_pieces(spec, info["duration"])
    if not pieces:
        die("Nothing to render (check trim).")
    fps = int(spec.get("fps") or round(info["fps"] or 30))
    aspect = spec.get("aspect", "keep")
    if aspect == "keep":
        W, H = info["width"] // 2 * 2, info["height"] // 2 * 2
    else:
        W, H = frame_size(aspect, resolve_res(spec.get("resolution", 1080), [inp]))
    if preview:
        (W, H), fps = preview_size(W, H), 30

    # attach point effects to the piece they land in (by source time)
    for o in spec.get("ops", []):
        if o["type"] in ("zoom", "flash", "shake", "rgb"):
            at = float(o["at"])
            for p in pieces:
                if p["kind"] == "play" and p["a"] - 1e-6 <= at < p["b"]:
                    p.setdefault("events", []).append({**o, "local": (at - p["a"]) / p["speed"]})
                    break

    with tempfile.TemporaryDirectory() as td:
        vlist, alist = [], []
        for i, p in enumerate(pieces):
            f0, f1 = round(p["out_start"] * fps), round(p["out_end"] * fps)
            n = max(1, f1 - f0)
            D = n / fps
            vpart, apart = Path(td) / f"p{i:03d}.mp4", Path(td) / f"p{i:03d}.wav"
            if p["kind"] == "freeze":
                still = Path(td) / f"p{i:03d}.png"
                ffmpeg(["-ss", f"{p['a']:.3f}", "-i", str(inp), "-frames:v", "1", str(still)])
                ffmpeg(
                    [
                        "-loop",
                        "1",
                        "-framerate",
                        str(fps),
                        "-i",
                        str(still),
                        "-an",
                        "-vf",
                        f"{fit_chain(W, H, spec.get('fit', 'crop'))},setsar=1,format=yuv420p",
                        "-frames:v",
                        str(n),
                        "-r",
                        str(fps),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-crf",
                        "16",
                        str(vpart),
                    ]
                )
            else:
                src_len = p["b"] - p["a"]
                ffmpeg(
                    [
                        "-ss",
                        f"{p['a']:.3f}",
                        "-t",
                        f"{src_len + 0.15:.3f}",
                        "-i",
                        str(inp),
                        "-an",
                        "-vf",
                        piece_video_filter(p, spec, W, H, fps, p.get("events", [])),
                        "-frames:v",
                        str(n),
                        "-r",
                        str(fps),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-crf",
                        "16",
                        str(vpart),
                    ]
                )
            # audio for exactly D seconds
            if (
                info["has_audio"]
                and p["kind"] == "play"
                and (p["speed"] == 1 or spec.get("slowmo_audio", "stretch") == "stretch")
            ):
                af = "aresample=48000"
                if p["speed"] != 1:
                    af += "," + atempo_chain(p["speed"])
                ffmpeg(
                    [
                        "-ss",
                        f"{p['a']:.3f}",
                        "-t",
                        f"{p['b'] - p['a'] + 0.1:.3f}",
                        "-i",
                        str(inp),
                        "-vn",
                        "-af",
                        f"{af},apad,atrim=0:{D:.5f}",
                        "-ac",
                        "2",
                        "-c:a",
                        "pcm_s16le",
                        str(apart),
                    ]
                )
            else:
                ffmpeg(
                    [
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=48000:cl=stereo",
                        "-t",
                        f"{D:.5f}",
                        "-c:a",
                        "pcm_s16le",
                        str(apart),
                    ]
                )
            vlist.append(concat_line(vpart))
            alist.append(concat_line(apart))
        (Path(td) / "v.txt").write_text("\n".join(vlist), encoding="utf-8")
        (Path(td) / "a.txt").write_text("\n".join(alist), encoding="utf-8")
        inputs = [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(Path(td) / "v.txt"),
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(Path(td) / "a.txt"),
        ]
        total = pieces[-1]["out_end"]
        m = spec.get("music")
        if m:
            inputs += ["-ss", str(m.get("start", 0)), "-t", f"{total:.3f}", "-i", m["file"]]
            graph = (
                f"[1:a]volume={m.get('game_volume', 0.3)}[g];[2:a]aresample=48000,volume={m.get('volume', 1.0)},"
                f"afade=t=out:st={max(total - 1.2, 0):.3f}:d=1.2[mu];"
                f"[mu][g]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
            )
        else:
            graph = "[1:a]anull[a]"
        tf = text_filters(spec, pieces, W, H)
        graph += f";[0:v]{tf or 'null'}[v]"
        enc = ["-preset", "veryfast", "-crf", "26"] if preview else ["-preset", "medium", "-crf", "18"]
        ffmpeg(
            [
                *inputs,
                "-filter_complex",
                graph,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                *enc,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-t",
                f"{total:.3f}",
                "-movflags",
                "+faststart",
                str(out_path),
            ],
            hw=True,
        )
    if spec.get("normalize_lufs", -14) is not None:
        normalize_loudness(out_path, float(spec.get("normalize_lufs", -14)))
    return pieces


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("edit")
    ap.add_argument("--out", default="clip_edit.mp4")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    spec = load_json(a.edit)
    m = spec.get("music")
    if m and m.get("file") and not Path(m["file"]).exists():
        alt = Path(a.edit).resolve().parent / m["file"]  # relative to the edit file, not the shell
        if alt.exists():
            m["file"] = str(alt)
        else:
            die(f"Music file not found: {m['file']}")
    pieces = render(a.input, spec, a.out, a.preview)
    print("Time map (source -> output):")
    for p in pieces:
        if p["kind"] == "freeze":
            print(f"  freeze @{p['a']:.2f}s -> {p['out_start']:.2f}-{p['out_end']:.2f}s")
        else:
            print(f"  {p['a']:.2f}-{p['b']:.2f}s x{p['speed']:g} -> {p['out_start']:.2f}-{p['out_end']:.2f}s")
    save_json({"pieces": pieces}, Path(a.out).with_suffix(".map.json"))
    print(f"Done -> {a.out}")
