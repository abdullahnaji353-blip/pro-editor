import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg not installed"
)


def make_video(path, size="320x180", seconds=1, extra_in=(), extra_out=()):
    """Small test clip with a tone, made with ffmpeg."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        *extra_in,
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=s={size}:r=30:d={seconds}",
        "-f",
        "lavfi",
        "-i",
        f"sine=f=440:d={seconds}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        *extra_out,
        str(path),
    ]
    subprocess.run(cmd, check=True)
    return path


def words_line(start, text, gap=0.06):
    """A transcript line with evenly timed words, the way faster-whisper returns them."""
    out, t = [], start
    for w in text.split():
        d = 0.18 + 0.03 * len(w)
        out.append({"w": w, "start": round(t, 3), "end": round(t + d, 3), "p": 0.9})
        t += d + gap
    return out


def transcript(lines):
    segs = []
    for i, (start, text) in enumerate(lines, 1):
        ws = words_line(start, text)
        segs.append({"id": i, "start": start, "end": ws[-1]["end"], "text": text, "words": ws})
    return {"language": "en", "segments": segs}
