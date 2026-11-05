"""YouTube chapters for talking videos, from the transcript.

Usage: python chapters.py TRANSCRIPT --at "1:Intro" "14:Trying the new map" "31:Final thoughts"
                          [--map cut.map.json] [--video final.mp4 --out final_chapters.mp4] [--txt chapters.txt]

--at takes script line numbers (from `vlog_cut.py script`) and a title for each chapter. Claude picks
the lines by reading the script for topic changes. Times follow the edit when --map is given
(the .map.json from `vlog_cut.py cut`). The first chapter is forced to 0:00, chapters shorter than
10 s are merged (YouTube needs 3+ chapters, each 10 s+), and --video embeds them into a copy of the
file (no re-encode).
"""
import argparse
from pathlib import Path

from common import die, ffmpeg, load_json, probe


def out_time(t, mapping):
    if not mapping:
        return t
    for r in mapping["ranges"]:
        if r["src_start"] - 0.05 <= t <= r["src_end"] + 0.05:
            return r["out_start"] + max(0.0, t - r["src_start"])
    # the line's start was cut: use the next kept moment after it
    later = [r for r in mapping["ranges"] if r["src_start"] >= t]
    return later[0]["out_start"] if later else None


def ts(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript")
    ap.add_argument("--at", nargs="+", required=True, help='"LINE:Title" entries')
    ap.add_argument("--map")
    ap.add_argument("--video")
    ap.add_argument("--out")
    ap.add_argument("--txt", default="chapters.txt")
    a = ap.parse_args()

    tr = load_json(a.transcript)
    mapping = load_json(a.map) if a.map else None
    by_id = {s["id"]: s for s in tr["segments"]}
    chaps = []
    for item in a.at:
        if ":" not in item:
            die(f"Use LINE:Title, got '{item}'")
        line, title = item.split(":", 1)
        seg = by_id.get(int(line))
        if not seg:
            die(f"Line {line} isn't in the transcript")
        start = seg["words"][0]["start"] if seg.get("words") else seg["start"]
        t = out_time(start, mapping)
        if t is None:
            print(f"Skipped '{title}': line {line} was cut out of the video")
            continue
        chaps.append([t, title.strip()])
    chaps.sort()
    if not chaps:
        die("No chapters left.")
    chaps[0][0] = 0.0
    merged = []
    for t, title in chaps:
        if merged and t - merged[-1][0] < 10:
            print(f"Merged '{title}' into '{merged[-1][1]}' (chapters need 10 s+)")
            continue
        merged.append([t, title])
    end = probe(a.video)["duration"] if a.video else None
    if end and merged and end - merged[-1][0] < 10 and len(merged) > 1:
        print(f"Merged last chapter '{merged[-1][1]}' (under 10 s before the end)")
        merged.pop()
    lines = [f"{ts(t)} {title}" for t, title in merged]
    Path(a.txt).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if len(merged) < 3:
        print("Note: YouTube shows chapters only with 3 or more.")
    if a.video:
        out = Path(a.out or Path(a.video).with_name(Path(a.video).stem + "_chapters.mp4"))
        meta = Path(a.txt).with_suffix(".ffmeta")
        rows = [";FFMETADATA1"]
        for k, (t, title) in enumerate(merged):
            stop = merged[k + 1][0] if k + 1 < len(merged) else end
            rows += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int(stop * 1000)}",
                     f"title={title}"]
        meta.write_text("\n".join(rows) + "\n", encoding="utf-8")
        ffmpeg(["-i", a.video, "-i", str(meta), "-map", "0", "-map_metadata", "1", "-map_chapters", "1",
                "-c", "copy", "-movflags", "+faststart", str(out)])
        print(f"Chapters embedded -> {out}")
    print(f"Paste into the YouTube description -> {a.txt}")
