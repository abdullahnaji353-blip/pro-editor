"""Make 3 versions of the same edit to A/B test what your audience likes.

Usage: python variants.py --song SONG (--clips ... | --highlights h.json) [--recipe r.json]
                          [--song-start S] [--length L] [--fit crop|blur] [--sfx]
                          [--out-dir variants] [--full]

A  "Best clip first"  - opens on your highest-scoring moment (strongest hook).
B  "Remix"            - same song section, clips reshuffled (tests clip order).
C  "Straight to drop" - song starts ~1s before its first drop, best clip on the drop
                        (tests instant energy vs build-up).
Previews by default (fast); --full renders all three at full quality.
Post them a few days apart (same time of day) and compare retention/views, not just likes.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from common import die, probe, save_json

HERE = Path(__file__).resolve().parent


def run_build(base, extra, out, preview):
    cmd = [sys.executable, str(HERE / "build_montage.py"), *base, *extra, "--out", str(out),
           "--plan-out", str(out.with_suffix(".plan.json")), "--xml-out", str(out.with_suffix(".xml"))]
    if preview:
        cmd.append("--preview")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"Variant {out.name} failed:\n{res.stderr[-1500:]}")
    return probe(out)["duration"]


if __name__ == "__main__":
    from beats import analyze as beat_analyze

    ap = argparse.ArgumentParser()
    ap.add_argument("--song", required=True)
    ap.add_argument("--clips", nargs="*")
    ap.add_argument("--highlights")
    ap.add_argument("--recipe")
    ap.add_argument("--song-start", type=float, default=0.0)
    ap.add_argument("--length", type=float, default=30.0)
    ap.add_argument("--fit", choices=["crop", "blur"], default="crop")
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--res", default=None, help="passed to build_montage (1080, 1440, 2160, source)")
    ap.add_argument("--out-dir", default="variants")
    ap.add_argument("--full", action="store_true", help="full quality instead of previews")
    a = ap.parse_args()
    if not (a.clips or a.highlights):
        die("Pass --clips or --highlights")

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = ["--song", a.song, "--length", str(a.length), "--fit", a.fit]
    if a.clips:
        base += ["--clips", *a.clips]
    if a.highlights:
        base += ["--highlights", a.highlights]
    if a.recipe:
        base += ["--recipe", a.recipe]
    if a.sfx:
        base += ["--sfx"]
    if a.res:
        base += ["--res", str(a.res)]

    # C: find the first drop after the chosen start, begin ~1s before it
    song_dur = probe(a.song)["duration"]
    b = beat_analyze(a.song, a.song_start, min(song_dur, a.song_start + a.length + 20))
    drops = [d for d in b["drops"] if d > 1.5]
    c_start = a.song_start + (drops[0] - 1.0) if drops else a.song_start
    c_start = max(0.0, min(c_start, song_dur - a.length))

    plan = [
        ("A_best_clip_first", "Opens on your strongest moment", ["--song-start", str(a.song_start), "--hook-first"]),
        ("B_remix", "Same song section, clips in a different order",
         ["--song-start", str(a.song_start), "--shuffle", "--seed", "23"]),
        ("C_straight_to_drop", f"Song starts at {c_start:.1f}s, ~1s before its drop; best clip on the drop",
         ["--song-start", f"{c_start:.3f}", "--hook-first"]),
    ]
    summary = []
    for name, why, extra in plan:
        out = out_dir / f"{name}{'' if a.full else '_preview'}.mp4"
        print(f"Rendering {name} ...")
        dur = run_build(base, extra, out, not a.full)
        summary.append({"name": name, "file": str(out.resolve()), "what_changes": why, "duration": round(dur, 2)})
        print(f"  -> {out} ({dur:.1f}s)  {why}")
    save_json({"variants": summary,
               "how_to_test": "Post one every 2-3 days at the same time of day. Compare average watch time / "
                              "retention and views after 48h. The winner tells you what to repeat."},
              out_dir / "variants.json")
    print(f"Summary -> {out_dir / 'variants.json'}")
