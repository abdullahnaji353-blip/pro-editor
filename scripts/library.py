"""Clip library: make footage searchable by what happens in it.

Claude can't watch video, but it can read images. `index` turns each recording into
timestamped contact sheets (16 frames per image) plus an audio "heat" score per sheet, so Claude
can look through the footage, write labels for the moments that matter, and later find a moment
from a plain-language description.

Commands (all take --lib DIR, default ./clip-library):
  index VIDEO_OR_FOLDER...  [--every 4] [--accurate] [--audio-track N]
        Sample a frame every N seconds into sheets. Default reads keyframes only (very fast; times
        are exact, spacing follows the recording's keyframe interval). --accurate decodes every frame.
  status                    What's indexed, how many sheets are reviewed, how many clips are labeled.
  next [--n 4]              The hottest sheets not reviewed yet (look at these first).
  reviewed VIDEO_ID SHEETS  Mark sheets as looked at, e.g. 1-6,9.
  add VIDEO_ID START END --tags a,b,c --desc "..." [--quality 1-5] [--game fortnite]
                            Save a labeled clip (seconds in the source video).
  search "QUERY" [--top 8]  Find labeled clips matching a description (synonym-aware).
  zoom VIDEO_ID START END [--step 0.5]
                            Dense, accurate sheet of one window to confirm a moment / pick exact in-out.
  cut CLIP_ID|VIDEO_ID@START-END [--pad 0.5] [--out FILE]
                            Export a clip (accurate cut, re-encoded).
"""
import argparse
import hashlib
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import (VIDEO_EXTS, audio_tracks, collect_media, die, ff_path, ffmpeg, find_font,
                    load_json, need, probe, save_json)

COLS = 4
PER_SHEET = 16

SYNONYMS = [
    {"kill", "kills", "elim", "elims", "elimination", "eliminations", "eliminated", "knock", "knocked", "frag"},
    {"goal", "goals", "score", "scored", "scoring"},
    {"clutch", "1v2", "1v3", "1v4", "1vx", "comeback"},
    {"funny", "fail", "fails", "lol", "reaction", "laugh", "laughing", "chaos", "troll"},
    {"shotgun", "pump", "shotty"},
    {"sniper", "snipe", "sniped", "noscope", "no-scope"},
    {"build", "builds", "building", "edit", "edits", "piece", "piece-control", "box"},
    {"aerial", "aerials", "air-dribble", "flip-reset", "ceiling", "double-tap", "musty", "freestyle"},
    {"win", "won", "victory", "victory-royale", "crown", "dub"},
    {"save", "saves", "block", "blocked"},
    {"end", "endgame", "end-game", "final", "last", "zone"},
    {"start", "beginning", "early", "drop", "landing", "hot-drop"},
]


def lib_paths(lib):
    lib = Path(lib)
    return lib, lib / "library.json"


def load_lib(lib):
    lib, jf = lib_paths(lib)
    if jf.exists():
        return load_json(jf)
    return {"version": 1, "videos": {}, "clips": []}


def save_lib(lib, data):
    save_json(data, lib_paths(lib)[1])


def video_id(path):
    p = Path(path).resolve()
    st = p.stat()
    h = hashlib.sha1(f"{p}:{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:6]
    stem = re.sub(r"[^A-Za-z0-9]+", "-", p.stem).strip("-")[:24] or "video"
    return f"{stem}-{h}"


def parse_ranges(spec):
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out |= set(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return sorted(out)


def fmt_t(t):
    m, s = divmod(t, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:05.2f}" if h else f"{m}:{s:05.2f}"


def sample_frames(path, every, accurate, out_dir, width=320):
    """Write timestamp-labelled JPGs; return their times (seconds)."""
    font = find_font()
    label = ""
    if font:
        label = (f",drawtext=fontfile='{ff_path(font)}':text='%{{pts\\:hms}}':fontsize=22:fontcolor=white:"
                 f"box=1:boxcolor=black@0.6:boxborderw=4:x=6:y=6")
    vf = (f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{every})',"
          f"scale={width}:-2{label},showinfo")
    cmd = [need("ffmpeg"), "-hide_banner"]
    if not accurate:
        cmd += ["-skip_frame", "nokey"]
    cmd += ["-i", str(path), "-an", "-vf", vf, "-fps_mode", "vfr", "-q:v", "4",
            str(Path(out_dir) / "f_%06d.jpg")]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-1200:])
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def tile(frames_dir, start_idx, n, out_png):
    rows = math.ceil(n / COLS)
    ffmpeg(["-start_number", str(start_idx), "-i", str(Path(frames_dir) / "f_%06d.jpg"),
            "-vf", f"tile={COLS}x{rows}:padding=3:margin=3:color=black", "-frames:v", "1", str(out_png)])


def audio_heat(path, times, track=0):
    """Loudness-spike score (0-1) around each sampled time."""
    try:
        import numpy as np
        from highlights import audio_curve, STEP
    except Exception:
        return [0.0] * len(times)
    info = probe(path)
    if not info["has_audio"] or not times:
        return [0.0] * len(times)
    n = max(1, int(info["duration"] / STEP))
    curve = audio_curve(path, n, track)
    out = []
    for i, t in enumerate(times):
        nxt = times[i + 1] if i + 1 < len(times) else t + 4
        a, b = int(t / STEP), max(int(t / STEP) + 1, int(nxt / STEP))
        out.append(float(np.max(curve[a:b])) if b <= len(curve) and a < b else 0.0)
    if out:
        lo, hi = min(out), max(out)
        out = [round((x - lo) / ((hi - lo) or 1), 3) for x in out]
    return out


# ------------------------------------------------------------------ commands
def cmd_index(a):
    data = load_lib(a.lib)
    lib = Path(a.lib)
    for v in collect_media(a.inputs, VIDEO_EXTS):
        vid = video_id(v)
        if vid in data["videos"] and not a.force:
            print(f"{v.name}: already indexed as {vid}")
            continue
        info = probe(v)
        if not info["has_video"]:
            print(f"{v.name}: no video stream, skipped")
            continue
        out = lib / vid
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        print(f"Indexing {v.name} ({fmt_t(info['duration'])}) ...")
        with tempfile.TemporaryDirectory() as td:
            times = sample_frames(v, a.every, a.accurate, td)
            if not times:
                die(f"No frames sampled from {v}")
            gaps = [b - x for x, b in zip(times, times[1:])]
            med_gap = sorted(gaps)[len(gaps) // 2] if gaps else a.every
            tracks = audio_tracks(v) if info["has_audio"] else []
            track = a.audio_track if a.audio_track < len(tracks) else 0
            heat = audio_heat(v, times, track) if tracks else [0.0] * len(times)
            sheets = []
            for k in range(0, len(times), PER_SHEET):
                n = min(PER_SHEET, len(times) - k)
                png = out / f"sheet_{k // PER_SHEET + 1:03d}.png"
                tile(td, k + 1, n, png)
                sheets.append({"n": k // PER_SHEET + 1, "file": str(png.resolve()),
                               "times": times[k:k + n], "heat": max(heat[k:k + n]) if heat else 0,
                               "reviewed": False})
        data["videos"][vid] = {"path": str(v.resolve()), "duration": info["duration"],
                               "fps": info["fps"], "size": f"{info['width']}x{info['height']}",
                               "sample_every": round(med_gap, 2), "audio_tracks": len(tracks),
                               "sheets": sheets}
        save_lib(a.lib, data)
        warn = ""
        if med_gap > a.every * 2.5:
            warn = f"  (keyframes are {med_gap:.1f}s apart; use --accurate for tighter spacing)"
        print(f"  {vid}: {len(times)} frames -> {len(sheets)} sheets, one frame per ~{med_gap:.1f}s{warn}")


def cmd_status(a):
    data = load_lib(a.lib)
    if not data["videos"]:
        print("Library is empty. Run: library.py index <videos>")
        return
    for vid, v in data["videos"].items():
        done = sum(s["reviewed"] for s in v["sheets"])
        clips = sum(1 for c in data["clips"] if c["video"] == vid)
        print(f"{vid}: {Path(v['path']).name}, {fmt_t(v['duration'])}, sheets reviewed {done}/{len(v['sheets'])}, "
              f"labeled clips {clips}")
    print(f"Total labeled clips: {len(data['clips'])}")


def cmd_next(a):
    data = load_lib(a.lib)
    todo = [(s["heat"], vid, s) for vid, v in data["videos"].items() for s in v["sheets"] if not s["reviewed"]]
    todo.sort(key=lambda x: -x[0])
    if not todo:
        print("Every sheet has been reviewed.")
        return
    for heat, vid, s in todo[:a.n]:
        print(f"{vid} sheet {s['n']}  {fmt_t(s['times'][0])}-{fmt_t(s['times'][-1])}  heat {heat:.2f}\n  {s['file']}\n"
              f"  frame times (left->right, top->bottom): {', '.join(f'{t:.1f}' for t in s['times'])}")
    print(f"{len(todo)} sheets left to review.")


def cmd_reviewed(a):
    data = load_lib(a.lib)
    v = data["videos"].get(a.video) or die(f"Unknown video id {a.video}")
    nums = set(parse_ranges(a.sheets))
    for s in v["sheets"]:
        if s["n"] in nums:
            s["reviewed"] = True
    save_lib(a.lib, data)
    print(f"Marked {len(nums)} sheet(s) reviewed for {a.video}.")


def cmd_add(a):
    data = load_lib(a.lib)
    v = data["videos"].get(a.video) or die(f"Unknown video id {a.video}")
    start, end = max(0.0, a.start), min(a.end, v["duration"])
    if end <= start:
        die("END must be after START")
    n = 1 + sum(1 for c in data["clips"] if c["video"] == a.video)
    cid = f"{a.video}#{n}"
    tags = [t.strip().lower().replace(" ", "-") for t in a.tags.split(",") if t.strip()]
    clip = {"id": cid, "video": a.video, "start": round(start, 2), "end": round(end, 2), "tags": tags,
            "desc": a.desc, "quality": a.quality, "game": a.game}
    data["clips"].append(clip)
    save_lib(a.lib, data)
    print(f"Saved {cid}: {fmt_t(start)}-{fmt_t(end)} [{', '.join(tags)}]")


def expand(token):
    token = token.lower()
    for group in SYNONYMS:
        if token in group:
            return group
    return {token}


def cmd_search(a):
    data = load_lib(a.lib)
    if not data["clips"]:
        print("No labeled clips yet. Index footage, review sheets and add labels first.")
        return
    tokens = [t for t in re.findall(r"[a-z0-9#\-]+", a.query.lower()) if t not in
              {"the", "a", "an", "my", "with", "where", "i", "me", "clip", "moment", "that", "of", "in", "on", "and", "got"}]
    scored = []
    for c in data["clips"]:
        hay_tags = set(c["tags"])
        hay_desc = set(re.findall(r"[a-z0-9#\-]+", (c.get("desc") or "").lower()))
        score = 0.0
        for t in tokens:
            group = expand(t)
            if hay_tags & group:
                score += 2
            elif hay_desc & group:
                score += 1
        if score:
            score += 0.2 * (c.get("quality") or 3)
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        print("No match. Try other words, or check the unreviewed sheets (library.py next).")
        return
    for s, c in scored[:a.top]:
        v = data["videos"][c["video"]]
        print(f"{c['id']}  score {s:.1f}  {Path(v['path']).name} {fmt_t(c['start'])}-{fmt_t(c['end'])}  "
              f"q{c.get('quality')}  [{', '.join(c['tags'])}]\n    {c.get('desc', '')}")


def cmd_zoom(a):
    data = load_lib(a.lib)
    v = data["videos"].get(a.video) or die(f"Unknown video id {a.video}")
    span = a.end - a.start
    if span <= 0 or span / a.step > 48:
        die("Window too long for one zoom sheet (max 48 frames): shorten it or raise --step")
    out = Path(a.lib) / a.video / f"zoom_{a.start:.1f}-{a.end:.1f}.png"
    with tempfile.TemporaryDirectory() as td:
        font = find_font()
        label = ""
        if font:
            label = (f",drawtext=fontfile='{ff_path(font)}':text='%{{pts\\:hms}}':fontsize=22:fontcolor=white:"
                     f"box=1:boxcolor=black@0.6:boxborderw=4:x=6:y=6")
        ffmpeg(["-ss", str(a.start), "-t", str(span), "-copyts", "-i", v["path"], "-an",
                "-vf", f"fps=1/{a.step}:start_time={a.start},scale=320:-2{label}", "-q:v", "4",
                str(Path(td) / "f_%06d.jpg")])
        n = len(list(Path(td).glob("f_*.jpg")))
        if not n:
            die("No frames in that window.")
        tile(td, 1, n, out)
    print(f"{out.resolve()}\n  {n} frames, one every {a.step}s from {fmt_t(a.start)}")


def cmd_cut(a):
    data = load_lib(a.lib)
    if "@" in a.target:
        vid, rng = a.target.split("@", 1)
        s, e = (float(x) for x in rng.split("-", 1))
        tags = []
    else:
        c = next((c for c in data["clips"] if c["id"] == a.target), None) or die(f"Unknown clip {a.target}")
        vid, s, e, tags = c["video"], c["start"], c["end"], c["tags"]
    v = data["videos"].get(vid) or die(f"Unknown video id {vid}")
    s, e = max(0.0, s - a.pad), min(v["duration"], e + a.pad)
    slug = "_".join(tags[:3]) or "clip"
    out = Path(a.out) if a.out else Path(a.lib) / "clips" / f"{vid}_{int(s)}-{int(e)}_{slug}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg(["-ss", f"{s:.3f}", "-i", v["path"], "-t", f"{e - s:.3f}", "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(out)])
    print(f"{out.resolve()}  ({e - s:.1f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", default="clip-library")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index"); p.add_argument("inputs", nargs="+"); p.add_argument("--every", type=float, default=4.0)
    p.add_argument("--accurate", action="store_true"); p.add_argument("--audio-track", type=int, default=0)
    p.add_argument("--force", action="store_true")
    sub.add_parser("status")
    p = sub.add_parser("next"); p.add_argument("--n", type=int, default=4)
    p = sub.add_parser("reviewed"); p.add_argument("video"); p.add_argument("sheets")
    p = sub.add_parser("add"); p.add_argument("video"); p.add_argument("start", type=float); p.add_argument("end", type=float)
    p.add_argument("--tags", required=True); p.add_argument("--desc", default="")
    p.add_argument("--quality", type=int, default=3, choices=range(1, 6)); p.add_argument("--game", default="")
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--top", type=int, default=8)
    p = sub.add_parser("zoom"); p.add_argument("video"); p.add_argument("start", type=float); p.add_argument("end", type=float)
    p.add_argument("--step", type=float, default=0.5)
    p = sub.add_parser("cut"); p.add_argument("target"); p.add_argument("--pad", type=float, default=0.5)
    p.add_argument("--out")
    a = ap.parse_args()
    {"index": cmd_index, "status": cmd_status, "next": cmd_next, "reviewed": cmd_reviewed, "add": cmd_add,
     "search": cmd_search, "zoom": cmd_zoom, "cut": cmd_cut}[a.cmd](a)
