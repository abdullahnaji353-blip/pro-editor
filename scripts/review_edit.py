"""Coach-style breakdown of an edit: what works, what to fix, with exact timestamps.

Usage: python review_edit.py MY_EDIT [--recipe target_recipe.json] [--song SONG --song-start SEC]
                             [--out-dir review]

--song: the clean song file used in the edit (and where in the song the edit starts). Beat
        tracking on the clean song is far more reliable than on the finished edit, where game
        sounds, voice and effects muddy the beat.

Checks:
  - music sync: every cut vs the nearest beat/hit; off-beat cuts listed with how many frames to move
  - pacing: shot lengths, monotony (all shots the same length), dead spots (shots that drag)
  - hook: how fast the first cut/visual change comes; silence at the start
  - ending: does it end on a beat, does the audio fade or hard-stop
  - loudness: integrated LUFS and true peak vs the ~-14 LUFS / -1 dBTP platforms normalise to
  - vs a target recipe (optional): pace, beat sync, color, flash rate compared to the reference style
Writes review.json plus contact sheets (_sheet.png / _cuts.png) to look at.
"""
import argparse
import re
import statistics as st
from pathlib import Path

from common import load_json, measure_lufs, need, probe, run, save_json


def opening_silence(path, sec=0.6):
    res = run([need("ffmpeg"), "-hide_banner", "-t", str(sec), "-i", str(path), "-vn",
               "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume:\s+(-?[\d.]+) dB", res.stderr)
    return float(m.group(1)) if m else None


def review(path, recipe=None, out_dir="review", song=None, song_start=0.0):
    from analyze_style import analyze_one
    from beats import analyze as beat_analyze

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    info = probe(path)
    fps = info["fps"] or 30
    frame = 1 / fps
    stats = analyze_one(path, out_dir)  # cuts, shots, color, flashes, sheets
    cuts, dur = stats["cuts"], stats["duration"]
    bounds = [0.0] + cuts + [dur]
    shots = [b - a for a, b in zip(bounds, bounds[1:])]
    good, fix, notes = [], [], []
    rep = {"file": info["path"], "duration": dur, "fps": fps, "size": f"{info['width']}x{info['height']}",
           "aspect": stats["aspect"], "num_cuts": len(cuts), "median_shot_sec": stats["median_shot_sec"]}

    # ---------------- music sync
    off_beat = []
    if info["has_audio"] or song:
        b = beat_analyze(song, song_start, song_start + dur) if song else beat_analyze(path)
        rep["beat_source"] = "song file" if song else "edit audio"
        marks = sorted(set(b["beats"]) | set(b.get("onsets", [])))
        beats = b["beats"]
        rep["tempo_bpm"] = b["tempo_bpm"]
        tol = 0.05
        hits = sum(1 for c in cuts if marks and min(abs(c - x) for x in marks) <= tol)
        covered, last = 0.0, -1.0
        for m in marks:
            lo, hi = max(m - tol, last), m + tol
            covered += max(0.0, hi - lo)
            last = max(last, hi)
        rep["beat_sync_pct"] = round(100 * hits / len(cuts), 1) if cuts else None
        rep["random_sync_pct"] = round(100 * min(1.0, covered / max(dur, 0.1)), 1)
        for c in cuts:
            near_mark = min(marks, key=lambda x: abs(x - c)) if marks else None
            if near_mark is None or abs(near_mark - c) <= 0.05:
                continue
            # suggest the nearest real beat within a quarter second
            near_beat = min(beats, key=lambda x: abs(x - c)) if beats else None
            if near_beat is not None and abs(near_beat - c) <= 0.25:
                frames = round((near_beat - c) / frame)
                if frames:
                    off_beat.append({"cut_at": round(c, 2), "move_to": round(near_beat, 2), "frames": frames})
        rep["off_beat_cuts"] = off_beat
        # If most "misses" are off by the same amount, the beat grid is shifted, not the cuts.
        grid_suspect = False
        if len(off_beat) >= 4:
            fr = sorted(o["frames"] for o in off_beat)
            medf = fr[len(fr) // 2]
            same = sum(1 for f in fr if abs(f - medf) <= 1)
            grid_suspect = same / len(fr) >= 0.6
        rep["beat_grid_suspect"] = grid_suspect
        sync, chance = rep["beat_sync_pct"], rep["random_sync_pct"] or 0
        if sync is not None:
            if grid_suspect:
                pass  # sync % is unreliable when the grid is shifted
            elif sync >= chance + 25:
                good.append(f"Cuts lock to the music: {sync}% land on a beat or hit (random cutting would get ~{chance}%).")
            elif sync >= chance + 10:
                notes.append(f"Beat sync is decent but loose: {sync}% on the music vs ~{chance}% for random cuts.")
            else:
                fix.append(f"Cuts mostly ignore the music: {sync}% on a beat/hit, about what random cutting gets (~{chance}%). "
                           "Turn on audio waveform/beat markers in your editor and cut on the kicks and snares.")
        if off_beat and grid_suspect:
            notes.append(f"{len(off_beat)} cuts look off-beat by about the same amount, which usually means the "
                         "beat tracker locked onto the wrong grid (hi-hats/off-beats), not that the cuts are wrong. "
                         + ("" if song else "Re-run with --song <the song file> for a reliable check, or ")
                         + "spot-check a few against the waveform before moving anything.")
        elif off_beat:
            worst = sorted(off_beat, key=lambda x: -abs(x["frames"]))[:8]
            listing = "; ".join(f"{o['cut_at']}s -> {o['move_to']}s ({'+' if o['frames'] > 0 else ''}{o['frames']}f)"
                                for o in worst)
            fix.append(f"{len(off_beat)} cut(s) sit just off a beat. Biggest misses: {listing}.")
    else:
        notes.append("No audio track, so music sync wasn't checked.")

    # ---------------- pacing
    if len(shots) >= 4:
        med = st.median(shots)
        spread = st.pstdev(shots) / (st.mean(shots) or 1)
        rep["shot_length_variation"] = round(spread, 2)
        if spread < 0.15 and len(shots) >= 8:
            fix.append("Every shot is almost the same length, which reads as robotic. Mix it up: hold a great moment "
                       "for 2-4 beats, then hit a burst of quick cuts.")
        elif spread > 0.35:
            good.append("Pacing has contrast: quick bursts and longer holds.")
        drag_limit = max(3 * med, 2.5)
        drags = [(round(a, 2), round(b - a, 2)) for a, b in zip(bounds, bounds[1:]) if b - a > drag_limit]
        rep["dead_spots"] = [{"start": s, "length": length} for s, length in drags]
        if drags:
            fix.append("Possible dead spots (shots that run long for this pace): " +
                       ", ".join(f"{s}s for {length}s" for s, length in drags[:6]) +
                       ". Trim them or add a speed ramp/zoom so something changes.")

    # ---------------- hook + ending
    first_change = cuts[0] if cuts else dur
    rep["first_cut_sec"] = round(first_change, 2)
    if dur <= 90:
        if first_change <= 1.0:
            good.append(f"Fast hook: first cut at {first_change:.2f}s.")
        elif first_change > 2.0:
            fix.append(f"Slow hook: nothing cuts until {first_change:.2f}s. Short-form viewers decide in about a second; "
                       "open on your best moment or a cut/flash in the first second.")
    if info["has_audio"]:
        beats = b["beats"] if (info["has_audio"] or song) else []
        sil = opening_silence(path)
        rep["opening_mean_db"] = sil
        if sil is not None and sil < -40:
            fix.append("The first half-second is nearly silent. Start the audio immediately so the hook lands.")
        if beats:
            end_off = min(abs(dur - x) for x in beats)
            if end_off <= 0.12:
                good.append("Ends on a beat.")
            else:
                notes.append(f"The video ends {end_off:.2f}s away from a beat. Ending exactly on a hit feels cleaner.")
        lufs, peak = measure_lufs(path)
        rep["lufs"], rep["true_peak_db"] = lufs, peak
        if lufs is not None:
            if lufs < -18:
                fix.append(f"Too quiet: {lufs} LUFS. TikTok/YouTube play around -14 LUFS, so it'll sound weak next to "
                           "other videos. Raise the overall level (with a limiter).")
            elif lufs > -9:
                fix.append(f"Very loud: {lufs} LUFS. Platforms will turn it down and it may sound squashed.")
            else:
                good.append(f"Loudness is in a good range ({lufs} LUFS).")
        if peak is not None and peak > -0.5:
            fix.append(f"Audio peaks at {peak} dBFS, so it's likely clipping. Put a limiter at about -1 dB on the master.")

    # ---------------- vs target recipe
    if recipe:
        r = load_json(recipe)
        cmp = {}
        tgt = (r.get("pacing") or {}).get("median_shot_sec")
        if tgt:
            ratio = stats["median_shot_sec"] / tgt
            cmp["pace"] = {"yours": stats["median_shot_sec"], "target": tgt}
            if ratio > 1.4:
                fix.append(f"Slower than the target style: your shots average {stats['median_shot_sec']}s vs {tgt}s. Cut more often.")
            elif ratio < 0.7:
                fix.append(f"Faster than the target style: {stats['median_shot_sec']}s shots vs {tgt}s. Let moments breathe.")
            else:
                good.append("Pace matches the target style.")
        tsync = (r.get("pacing") or {}).get("beat_sync_pct")
        if tsync and rep.get("beat_sync_pct") is not None:
            cmp["beat_sync"] = {"yours": rep["beat_sync_pct"], "target": tsync}
        col = r.get("color") or {}
        for k in ("brightness", "saturation", "contrast"):
            if col.get(k) is not None and stats.get(k) is not None:
                cmp[k] = {"yours": stats[k], "target": col[k]}
                diff = stats[k] - col[k]
                if abs(diff) > 0.12:
                    fix.append(f"{k.capitalize()} is {'higher' if diff > 0 else 'lower'} than the target look "
                               f"({stats[k]} vs {col[k]}).")
        tflash = (r.get("measured") or {}).get("flashes_per_min")
        if tflash is not None:
            cmp["flashes_per_min"] = {"yours": stats.get("flashes_per_min"), "target": tflash}
        rep["vs_target"] = cmp

    rep.update({"good": good, "fix": fix, "notes": notes,
                "sheet": stats.get("sheet"), "cuts_sheet": stats.get("cuts_sheet")})
    save_json(rep, Path(out_dir) / "review.json")
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("edit")
    ap.add_argument("--recipe", help="target style recipe from analyze_style.py")
    ap.add_argument("--out-dir", default="review")
    ap.add_argument("--song", help="the song used in the edit, for an accurate beat grid")
    ap.add_argument("--song-start", type=float, default=0.0, help="where in the song the edit starts (s)")
    a = ap.parse_args()
    r = review(a.edit, a.recipe, a.out_dir, a.song, a.song_start)
    print(f"{Path(a.edit).name}: {r['duration']}s, {r['num_cuts']} cuts, median shot {r['median_shot_sec']}s")
    for title, key in (("WORKING", "good"), ("FIX", "fix"), ("NOTES", "notes")):
        if r[key]:
            print(f"\n{title}")
            for line in r[key]:
                print(f"  - {line}")
    print(f"\nFull report -> {Path(a.out_dir) / 'review.json'}")
