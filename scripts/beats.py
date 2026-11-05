"""Detect tempo, beats, strong beats (downbeat-ish) and drops in a song.

Usage: python beats.py SONG [--out beats.json] [--start SEC] [--end SEC]
Accepts audio files or videos (audio is extracted).
"""

import argparse
import tempfile
from pathlib import Path

import numpy as np

from common import extract_audio, probe, save_json, smooth


def analyze(song, start=0.0, end=None):
    import librosa

    song = Path(song)
    with tempfile.TemporaryDirectory() as td:
        wav = song
        if song.suffix.lower() not in {".wav"}:
            wav = extract_audio(song, Path(td) / "a.wav")
        y, sr = librosa.load(str(wav), sr=22050, mono=True, offset=start, duration=(end - start) if end else None)
    dur = len(y) / sr
    hop = 512
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    # Strength of each beat = onset strength at that frame, normalised 0..1
    strength = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(beat_frames) else np.array([])
    if strength.size:
        strength = (strength - strength.min()) / (np.ptp(strength) or 1)

    # Guess bar phase: which of 4 offsets has the highest average beat strength -> downbeats
    downbeats = []
    if len(beat_times) >= 8:
        phase = int(np.argmax([strength[i::4].mean() for i in range(4)]))
        downbeats = beat_times[phase::4].tolist()

    # Drops: biggest jumps in short-term loudness (RMS over ~1s windows)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    win = max(1, int(sr / hop))
    sm = smooth(rms, win)
    rise = np.diff(sm, prepend=sm[0])
    drops = []
    for idx in np.argsort(rise)[::-1]:
        t = float(librosa.frames_to_time(idx, sr=sr, hop_length=hop))
        if t < 2 or any(abs(t - d) < 6 for d in drops):
            continue
        drops.append(t)
        if len(drops) >= 3:
            break
    # snap drops to nearest beat
    if len(beat_times):
        drops = sorted(float(beat_times[np.argmin(np.abs(beat_times - d))]) for d in drops)

    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop, units="time")

    return {
        "song": str(song.resolve()),
        "offset": start,
        "duration": round(dur, 3),
        "tempo_bpm": round(tempo, 2),
        "beats": [round(float(t), 3) for t in beat_times],
        "beat_strength": [round(float(s), 3) for s in strength],
        "downbeats": [round(float(t), 3) for t in downbeats],
        "drops": [round(d, 3) for d in drops],
        "onsets": [round(float(t), 3) for t in onsets],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--out", default="beats.json")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    a = ap.parse_args()
    probe(a.song)  # fail early on unreadable files
    r = analyze(a.song, a.start, a.end)
    save_json(r, a.out)
    print(f"Tempo {r['tempo_bpm']} BPM, {len(r['beats'])} beats, drops at {r['drops']} -> {a.out}")
