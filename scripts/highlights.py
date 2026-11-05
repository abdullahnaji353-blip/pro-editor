"""Find the most intense moments in long gameplay recordings.

Usage: python highlights.py VIDEO_OR_FOLDER [...] [--top 10] [--pre 3] [--post 2]
                            [--out highlights.json] [--export-dir clips/]

Scores every half-second by loudness spikes (gunfire, eliminations, goal horns, hype voice)
plus on-screen motion, then keeps the top peaks as clips with some lead-in and follow-through.

--mode scenic     for travel / events / vlogs: scores how good each moment LOOKS (sharp, colourful,
                  well exposed, some movement) and keeps shots that look different from each other.
                  Audio is ignored.
--mode reactions  scores the VOICE band (yells, laughs, "NO WAY") and barely weighs motion, with
                  longer lead-in so the setup of the funny moment survives. Point --audio-track at
                  the mic track when the recording has one.
It finds LOUD + BUSY moments. It cannot tell a cracked play from a messy one, so treat the
result as a shortlist to review, not a final pick.
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from common import (VIDEO_EXTS, audio_tracks, collect_media, dec_args, extract_audio, ffmpeg, need, probe, run, save_json,
                    smooth)

STEP = 0.5  # seconds per scoring window


def zscore(x):
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return (x - x.mean()) / sd if sd > 1e-9 else np.zeros_like(x)


VOICE_BAND = "highpass=f=250,lowpass=f=3400"


def audio_curve(path, n, track=0, voice=False):
    import librosa

    with tempfile.TemporaryDirectory() as td:
        wav = extract_audio(path, Path(td) / "a.wav", sr=16000, track=track,
                            af=VOICE_BAND if voice else None)
        y, sr = librosa.load(str(wav), sr=16000, mono=True)
    hop = int(sr * STEP)
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    # emphasise sudden rises over constant loudness (music bed, wind)
    base = smooth(rms, 20)
    spike = np.clip(rms - base, 0, None)
    curve = 0.6 * zscore(spike) + 0.4 * zscore(rms)
    return np.resize(curve, n) if len(curve) else np.zeros(n)


def motion_curve(path, n):
    res = run([need("ffmpeg"), "-hide_banner", *dec_args(), "-i", str(path), "-an", "-vf",
               f"fps={1/STEP},scale=160:-2,signalstats,metadata=print:file=-", "-f", "null", "-"])
    vals = [float(v) for v in re.findall(r"lavfi\.signalstats\.YDIF=([\d.]+)", res.stdout)]
    return np.resize(zscore(vals), n) if vals else np.zeros(n)


def find_scenic(path, top, pre, post, min_gap):
    """Best-looking, varied moments. One frame per second, scored like a thumbnail, plus movement."""
    from thumbnail import score as look_score, too_similar
    info = probe(path)
    W, H = 192, 108
    res = subprocess.run([need("ffmpeg"), "-hide_banner", "-loglevel", "error", *dec_args(), "-i", str(path), "-an",
                          "-vf", f"fps=1,scale={W}:{H}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True)
    n = len(res.stdout) // (W * H * 3)
    if not n:
        return []
    frames = np.frombuffer(res.stdout[: n * W * H * 3], np.uint8).reshape(n, H, W, 3).astype(float)
    from analyze_style import scene_cuts
    cuts = scene_cuts(path)  # shot boundaries: a cut is not "movement", and clips stay inside one shot
    looks = np.array([look_score(f) for f in frames])
    motion = np.array([0.0] + [np.abs(frames[i] - frames[i - 1]).mean() for i in range(1, n)])
    for c in cuts:
        k = int(np.ceil(c))
        if 0 <= k < n:
            motion[k] = 0.0
    # some movement is good (a pan, people walking); a whip/shake blur is not -> cap it
    mot = np.clip(motion / (np.percentile(motion, 90) or 1), 0, 1.2)
    total = zscore(looks) + 0.35 * zscore(np.minimum(mot, 0.8))
    picks = []
    for idx in np.argsort(total)[::-1]:
        t = float(idx)
        if any(abs(t - p) < min_gap for p, _, _ in picks):
            continue
        if any(too_similar(frames[idx], frames[int(p)]) for p, _, _ in picks):
            continue  # looks like a shot we already have
        picks.append((t, float(total[idx]), idx))
        if len(picks) >= top:
            break
    out = []
    bounds = [0.0] + cuts + [info["duration"]]
    for t, sc, _ in picks:
        lo = max([b for b in bounds if b <= t + 0.05], default=0.0)
        hi = min([b for b in bounds if b > t + 0.05], default=info["duration"])
        start, end = max(lo, t - pre), min(hi, t + post)
        if end - start < 1.5:            # short shot: take the whole shot
            start, end = lo, hi
        out.append({"source": info["path"], "peak": round(t, 2), "start": round(start, 2),
                    "end": round(end, 2), "score": round(sc, 3), "mode": "scenic"})
    return out


def find(path, top, pre, post, min_gap, track=0, mode="action", context=8.0):
    info = probe(path)
    n = max(1, int(info["duration"] / STEP))
    tracks = audio_tracks(path) if info["has_audio"] else []
    if tracks and track >= len(tracks):
        track = 0
    voice = mode == "reactions"
    a = audio_curve(path, n, track, voice) if tracks else np.zeros(n)
    m = motion_curve(path, n)
    score = a + (0.15 if voice else 0.6) * m
    score = smooth(score, 3)
    picks = []
    for idx in np.argsort(score)[::-1]:
        t = idx * STEP
        if any(abs(t - p) < min_gap for p, _ in picks):
            continue
        picks.append((t, float(score[idx])))
        if len(picks) >= top:
            break
    # Lead-in with context: walk back from the peak while activity stays above the recording's
    # baseline, so the clip starts where the fight/play actually starts (setup -> moment -> reaction).
    base = float(np.median(score) + 0.25 * np.std(score))
    out = []
    for t, s in picks:
        k = int(t / STEP)
        while context > 0 and k > 0 and score[k - 1] > base and (t - (k - 1) * STEP) <= context:
            k -= 1
        lead = max(pre, t - k * STEP + 0.5) if context > 0 else pre
        start, end = max(0.0, t - lead), min(info["duration"], t + post)
        out.append({"source": info["path"], "peak": round(t, 2), "start": round(start, 2),
                    "end": round(end, 2), "score": round(s, 3), "mode": mode})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--top", type=int, default=10, help="highlights per video")
    ap.add_argument("--pre", type=float, default=None, help="seconds kept before the peak (3; reactions 5)")
    ap.add_argument("--post", type=float, default=None, help="seconds kept after the peak (2; reactions 4)")
    ap.add_argument("--min-score", type=float, default=0.5, help="drop picks weaker than this")
    ap.add_argument("--context", type=float, default=8.0,
                    help="max extra lead-in (s) to include the setup before a peak; 0 = fixed --pre only")
    ap.add_argument("--mode", choices=["action", "reactions", "scenic"], default="action",
                    help="action = fights/goals; reactions = funny moments from your voice; "
                         "scenic = best-looking varied shots (travel/events/vlogs)")
    ap.add_argument("--min-gap", type=float, default=8.0, help="min seconds between highlights")
    ap.add_argument("--out", default="highlights.json")
    ap.add_argument("--export-dir", default=None, help="also cut each highlight to its own mp4")
    ap.add_argument("--audio-track", type=int, default=0,
                    help="which audio track to score (0 = first). Use the game-only track if there is one")
    ap.add_argument("--tracks-only", action="store_true", help="just list each file's audio tracks and exit")
    a = ap.parse_args()

    files = collect_media(a.inputs, VIDEO_EXTS)
    track_report = {}
    for v in files:
        tr = audio_tracks(v)
        track_report[str(v)] = tr
        desc = ", ".join(f"#{t['track']} {t['title'] or 'untitled'}" for t in tr) or "none"
        print(f"{v.name}: {len(tr)} audio track(s): {desc}")
    if a.tracks_only:
        raise SystemExit(0)

    allh = []
    for v in files:
        print(f"Scanning {v.name} ...")
        pre = a.pre if a.pre is not None else {"reactions": 5.0, "scenic": 1.5}.get(a.mode, 3.0)
        post = a.post if a.post is not None else {"reactions": 4.0, "scenic": 2.5}.get(a.mode, 2.0)
        if a.mode == "scenic":
            hs = find_scenic(v, a.top, pre, post, a.min_gap)
        else:
            hs = find(v, a.top, pre, post, a.min_gap, a.audio_track, a.mode, a.context)
        allh += hs
    allh.sort(key=lambda h: -h["score"])
    kept = [h for h in allh if h["score"] >= a.min_score]
    if len(kept) < len(allh):
        print(f"Dropped {len(allh) - len(kept)} weak pick(s) below score {a.min_score} (--min-score to change)")
    allh = kept or allh[:1]
    for i, h in enumerate(allh, 1):
        h["rank"] = i
        if a.export_dir:
            Path(a.export_dir).mkdir(parents=True, exist_ok=True)
            clip = Path(a.export_dir) / f"hl_{i:02d}_{Path(h['source']).stem}_{int(h['peak'])}s.mp4"
            ffmpeg(["-ss", str(h["start"]), "-i", h["source"], "-t", str(h["end"] - h["start"]),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                    str(clip)])
            h["clip"] = str(clip.resolve())
    save_json({"highlights": allh, "audio_tracks": track_report, "scored_track": a.audio_track}, a.out)
    print(f"{len(allh)} highlights -> {a.out}")
    for h in allh[:10]:
        print(f"  #{h['rank']}  {Path(h['source']).name}  {h['start']}-{h['end']}s  score {h['score']}")
