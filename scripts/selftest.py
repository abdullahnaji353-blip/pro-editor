"""One-command health check of the whole plugin on this computer.

Usage: python selftest.py [--models] [--keep]

Makes small test videos and songs, runs every tool on them (previews where possible), and prints a
PASS/FAIL table with what to do about each failure. Also reports whether the graphics card is used
for encoding. --models also tests the speech model (downloads ~75 MB the first time) and face
detection. --keep leaves the test files so you can look at them.
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FIX = {
    "ffmpeg": "Install ffmpeg (Windows: winget install --id Gyan.FFmpeg -e, then reopen the terminal).",
    "python": "python -m pip install numpy librosa soundfile",
    "faster_whisper": "python -m pip install faster-whisper",
    "cv2": 'python -m pip install "opencv-python-headless<5"',
}


def sh(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[-3:]


def make_media(d):
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    kicks = "aevalsrc='0.7*sin(2*PI*55*t)*exp(-mod(t,0.5)*18)+0.2*random(0)*exp(-mod(t+0.25,0.5)*40)':s=44100:d=20"
    subprocess.run(ff + ["-f", "lavfi", "-i", kicks, "-c:a", "libmp3lame", "song.mp3"], cwd=d, check=True)
    for i, (src, size) in enumerate([("testsrc2", "1920x1080"), ("mandelbrot", "1280x720")], 1):
        subprocess.run(
            ff
            + [
                "-f",
                "lavfi",
                "-i",
                f"{src}=s={size}:r=60",
                "-f",
                "lavfi",
                "-i",
                "aevalsrc='0.03*random(0)+if(between(t,3,3.6),0.8*random(0),0)':s=48000:d=8",
                "-t",
                "8",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                f"clip{i}.mp4",
            ],
            cwd=d,
            check=True,
        )
    speech = "+".join(f"between(t,{a},{b})" for a, b in [(0.5, 2.5), (3.5, 5.5), (7.0, 9.0)])
    subprocess.run(
        ff
        + [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=1280x720:r=30:d=10",
            "-f",
            "lavfi",
            "-i",
            f"aevalsrc='0.004*random(0)+({speech})*0.5*sin(2*PI*180*t)*(0.55+0.45*sin(2*PI*4.5*t))':s=48000:d=10",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            "talk.mp4",
        ],
        cwd=d,
        check=True,
    )
    words = lambda a, b, txt: [
        {
            "w": w,
            "start": round(a + k * (b - a) / len(txt.split()), 3),
            "end": round(a + (k + 1) * (b - a) / len(txt.split()) - 0.03, 3),
            "p": 0.9,
        }
        for k, w in enumerate(txt.split())
    ]
    segs = [(0.5, 2.5, "hey welcome back"), (3.5, 5.5, "um today we test"), (7.0, 9.0, "oh clip that")]
    json.dump(
        {
            "segments": [
                {"id": k + 1, "start": a, "end": b, "text": t, "words": words(a, b, t)}
                for k, (a, b, t) in enumerate(segs)
            ]
        },
        open(Path(d) / "talk.json", "w"),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", action="store_true")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    results = []
    t_all = time.time()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("FAIL ffmpeg not found. " + FIX["ffmpeg"])
        sys.exit(1)
    if any(importlib.util.find_spec(m) is None for m in ("numpy", "librosa", "soundfile")):
        print("FAIL missing Python packages. " + FIX["python"])
        sys.exit(1)

    from common import hw_encoder

    enc = hw_encoder()
    gpu_line = (
        f"GPU encoding: {enc} (final renders use your graphics card)"
        if enc
        else "GPU encoding: none found, renders use the CPU (fine, just slower for 1440p/4K)"
    )

    d = Path(tempfile.mkdtemp(prefix="pro-editor-selftest-"))
    print(f"Making test media in {d} ...")
    make_media(d)
    py = sys.executable
    S = str(HERE)
    tests = [
        ("checkup (footage problems)", [py, f"{S}/checkup.py", "clip1.mp4", "--out-dir", "chk"]),
        ("beat detection", [py, f"{S}/beats.py", "song.mp3", "--out", "b.json"]),
        (
            "highlights",
            [
                py,
                f"{S}/highlights.py",
                "clip1.mp4",
                "clip2.mp4",
                "--top",
                "1",
                "--min-score",
                "-9",
                "--out",
                "h.json",
                "--export-dir",
                "hl",
            ],
        ),
        (
            "montage (preview)",
            [
                py,
                f"{S}/build_montage.py",
                "--song",
                "song.mp3",
                "--highlights",
                "h.json",
                "--length",
                "5",
                "--sfx",
                "--cold-open",
                "--preview",
                "--out",
                "m.mp4",
            ],
        ),
        (
            "montage (full quality, uses GPU if any)",
            [
                py,
                f"{S}/build_montage.py",
                "--song",
                "song.mp3",
                "--clips",
                "clip1.mp4",
                "--length",
                "3",
                "--out",
                "mf.mp4",
                "--plan-out",
                "pf.json",
                "--xml-out",
                "mf.xml",
            ],
        ),
        (
            "export (TikTok + YouTube)",
            [py, f"{S}/export.py", "m.mp4", "--platforms", "tiktok", "youtube", "--out-dir", "exp"],
        ),
        ("edit review", [py, f"{S}/review_edit.py", "m.mp4", "--song", "song.mp3", "--out-dir", "rv"]),
        ("clip library", [py, f"{S}/library.py", "--lib", "lib", "index", "clip1.mp4"]),
        (
            "jump cuts",
            [
                py,
                f"{S}/vlog_cut.py",
                "cut",
                "talk.mp4",
                "--transcript",
                "talk.json",
                "--fillers",
                "--punch-in",
                "1.1",
                "--out",
                "cut.mp4",
            ],
        ),
        (
            "word captions",
            [py, f"{S}/captions.py", "cut.mp4", "talk.json", "--map", "cut.map.json", "--out", "cap.mp4", "--preview"],
        ),
        ("voice cleanup", [py, f"{S}/voice.py", "talk.mp4", "--out", "clean.mp4"]),
        ("vertical crop", [py, f"{S}/reframe.py", "talk.mp4", "--keyframes", "0:0.5", "--out", "v.mp4", "--preview"]),
        ("color + LUT", [py, f"{S}/color.py", "apply", "clip1.mp4", "--look", "cinematic", "--out", "g.mp4"]),
        (
            "chapters",
            [
                py,
                f"{S}/chapters.py",
                "talk.json",
                "--at",
                "1:Intro",
                "3:Outro",
                "--video",
                "talk.mp4",
                "--out",
                "talk_ch.mp4",
                "--txt",
                "ch.txt",
            ],
        ),
        ("thumbnail", [py, f"{S}/thumbnail.py", "make", "clip1.mp4@2", "--text", "test", "--out", "t.jpg"]),
        ("safe zones", [py, f"{S}/layout.py", "safe", "m.mp4@1", "--out", "safe.png"]),
        (
            "/talk (spoken commands)",
            [py, f"{S}/listen.py", "hear", "talk.mp4", "--transcript", "talk.json", "--no-sounds", "--out-dir", "talk"],
        ),
    ]
    if importlib.util.find_spec("cv2"):
        tests.append(
            (
                "avatar (fixed spot, no tracking)",
                [
                    py,
                    f"{S}/avatar.py",
                    "render",
                    "clip1.mp4",
                    "--anchor",
                    "fixed",
                    "--pos",
                    "0.5,0.85",
                    "--end",
                    "3",
                    "--preview",
                    "--say",
                    "hi!@1-2.5",
                    "--out",
                    "av.mp4",
                ],
            )
        )
    for name, cmd in tests:
        t0 = time.time()
        ok, tail = sh(cmd, d)
        results.append((name, ok, time.time() - t0, tail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name:42s} {time.time() - t0:5.1f}s")
        if not ok:
            for line in tail:
                print(f"        {line[:160]}")
    if a.models:
        print("\nOptional parts:")
        t0 = time.time()
        try:
            from faster_whisper import WhisperModel

            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(d / "talk.mp4"),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(d / "talk.wav"),
                ],
                check=True,
            )
            list(WhisperModel("tiny", device="auto", compute_type="int8").transcribe(str(d / "talk.wav"))[0])
            results.append(("speech model", True, time.time() - t0, []))
            print(f"  PASS  {'speech model (transcripts)':42s} {time.time() - t0:5.1f}s")
        except ImportError:
            print("  SKIP  speech model: not installed. " + FIX["faster_whisper"])
        except Exception as e:
            results.append(("speech model", False, time.time() - t0, [str(e)[:160]]))
            print(
                f"  FAIL  speech model: couldn't download/load it ({type(e).__name__}). It downloads once on "
                "first use, so check the internet connection (or a firewall/proxy) and run this again."
            )
        try:
            import cv2

            ok = not cv2.CascadeClassifier(
                str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
            ).empty()
            results.append(("face detection", ok, 0, []))
            print(f"  {'PASS' if ok else 'FAIL'}  face detection" + ("" if ok else ": " + FIX["cv2"]))
        except ImportError:
            print("  SKIP  face detection: not installed. " + FIX["cv2"])
        if importlib.util.find_spec("mediapipe"):
            from common import get_model

            for name, url, env, label in [
                (
                    "hand_landmarker.task",
                    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                    "hand_landmarker/float16/latest/hand_landmarker.task",
                    "PRO_EDITOR_HAND_MODEL",
                    "hand tracking",
                ),
                (
                    "yamnet.tflite",
                    "https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/"
                    "float32/latest/yamnet.tflite",
                    "PRO_EDITOR_YAMNET_MODEL",
                    "sound recognition",
                ),
            ]:
                t0 = time.time()
                try:
                    get_model(name, url, env, label)
                    ok, tail = (
                        sh(
                            [
                                py,
                                f"{S}/listen.py",
                                "hear",
                                "talk.mp4",
                                "--transcript",
                                "talk.json",
                                "--out-dir",
                                "talk2",
                            ],
                            d,
                        )
                        if name == "yamnet.tflite"
                        else (True, [])
                    )
                    results.append((label, ok, time.time() - t0, tail))
                    print(f"  {'PASS' if ok else 'FAIL'}  {label + ' model':42s} {time.time() - t0:5.1f}s")
                except SystemExit:
                    results.append((label, False, time.time() - t0, []))
                    print(f"  FAIL  {label} model couldn't download: check the internet connection and run again.")
        else:
            print("  SKIP  avatar hand tracking and /talk sounds: python -m pip install mediapipe")

    # speed check: how long renders take on THIS computer
    from common import ffmpeg as ff_render

    print("\nRender speed on this computer:")
    for label, size, fps in [("1080p", "1920x1080", 60), ("4K", "3840x2160", 60)]:
        t0 = time.time()
        try:
            ff_render(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=s={size}:r={fps}:d=3",
                    "-vf",
                    "eq=saturation=1.1,unsharp=5:5:0.4",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    str(d / f"speed_{label}.mp4"),
                ],
                hw=True,
            )
            per_min = (time.time() - t0) / 3 * 60 * 1.5  # x1.5: real footage is harder to compress than test bars
            print(
                f"  {label}{fps}: about {per_min / 60:.1f} min of rendering per minute of finished video"
                + (
                    " (long 4K videos: use previews while deciding, render full quality once)"
                    if label == "4K" and per_min > 300
                    else ""
                )
            )
        except (RuntimeError, SystemExit) as e:
            print(f"  {label}: render failed ({str(e).splitlines()[-1][:120]})")
    print(f"\n{gpu_line}")
    if not a.models:
        if importlib.util.find_spec("faster_whisper"):
            print("Transcripts: installed (add --models to test the speech model)")
        else:
            print("Transcripts: not installed (only for vlogs/captions): " + FIX["faster_whisper"])
        if importlib.util.find_spec("cv2"):
            print("Face tracking: installed")
        else:
            print("Face tracking: not installed (only for vertical vlogs): " + FIX["cv2"])
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed in {time.time() - t_all:.0f}s.")
    if a.keep:
        print(f"Test files kept in {d}")
    else:
        shutil.rmtree(d, ignore_errors=True)
    sys.exit(1 if failed else 0)
