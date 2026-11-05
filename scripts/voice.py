"""Clean up a voice track: rumble, background hiss/hum, harsh 's' sounds, uneven volume.

Usage: python voice.py VIDEO_OR_AUDIO [--strength light|medium|strong] [--audio-track N]
                       [--lufs -14] [--out cleaned.mp4]

light  - gentle: rumble cut + a little denoise. Good mics, quiet rooms.
medium - default: denoise, de-ess, compression so quiet and loud parts sit closer together.
strong - noisy rooms / phone mics. Can sound a bit processed; preview it.
Video is copied untouched; only the audio is processed. Keeps your hype moments loud (the
compressor is gentle, and a limiter catches peaks instead of flattening everything).
"""

import argparse
from pathlib import Path

from common import die, ffmpeg, normalize_loudness, probe

LEVELS = {  # denoise amount (dB), how far pauses are pushed down (dB), compression ratio, presence boost
    "light": (10, 10, 2.0, 1.0),
    "medium": (18, 18, 2.5, 2.0),
    "strong": (28, 26, 3.0, 2.5),
}


def measure(path, track):
    """Noise floor and speech level (dBFS) from 50 ms windows: quiet 10th vs loud 90th percentile."""
    import tempfile

    import numpy as np
    import soundfile as sf

    from common import extract_audio

    with tempfile.TemporaryDirectory() as td:
        wav = extract_audio(path, Path(td) / "a.wav", sr=16000, track=track)
        y, sr = sf.read(str(wav))
    if y.ndim > 1:
        y = y.mean(axis=1)
    n = int(sr * 0.05)
    frames = y[: len(y) // n * n].reshape(-1, n)
    rms = 20 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-9)
    return float(np.percentile(rms, 10)), float(np.percentile(rms, 90))


def chain_for(strength, noise_db, speech_db):
    nr, gate_range, ratio, presence = LEVELS[strength]
    lin = lambda db: 10 ** (db / 20)
    # gate opens a bit above the hiss but well below speech; only the pauses get pushed down
    thr = noise_db + max(6.0, min(12.0, (speech_db - noise_db) * 0.35))
    parts = [
        "highpass=f=80",
        f"afftdn=nr={nr}:nf={max(-80, min(-20, noise_db)):.0f}:tn=1",
        f"agate=threshold={lin(thr):.5f}:range={lin(-gate_range):.4f}:ratio=4:attack=4:release=180:knee=3",
        "deesser=i=0.35" if strength != "light" else "",
        f"acompressor=threshold={lin(speech_db - 8):.4f}:ratio={ratio}:attack=8:release=140:makeup=1",
        f"equalizer=f=3200:t=q:w=1.2:g={presence}",
    ]
    if strength == "strong":
        parts.insert(1, "lowpass=f=14000")
    return ",".join(p for p in parts if p)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--strength", choices=list(LEVELS), default="medium")
    ap.add_argument("--audio-track", type=int, default=0)
    ap.add_argument("--lufs", type=float, default=-14.0, help="loudness target (-14 for social, -16 for long talks)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    info = probe(a.input)
    if not info["has_audio"]:
        die("No audio to clean.")
    out = Path(a.out or Path(a.input).with_name(Path(a.input).stem + "_clean" + Path(a.input).suffix))
    noise_db, speech_db = measure(a.input, a.audio_track)
    chain = chain_for(a.strength, noise_db, speech_db) + ",alimiter=limit=0.89"
    print(f"Noise floor {noise_db:.0f} dB, speech {speech_db:.0f} dB")
    if info["has_video"]:
        ffmpeg(
            [
                "-i",
                a.input,
                "-map",
                "0:v:0",
                "-map",
                f"0:a:{a.audio_track}",
                "-c:v",
                "copy",
                "-af",
                chain,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(out),
            ]
        )
    else:
        ffmpeg(["-i", a.input, "-map", f"0:a:{a.audio_track}", "-af", chain, "-ar", "48000", str(out)])
    got = normalize_loudness(out, a.lufs) if info["has_video"] else None
    print(f"Done -> {out} ({a.strength}{f', {got} LUFS' if got is not None else ''})")
