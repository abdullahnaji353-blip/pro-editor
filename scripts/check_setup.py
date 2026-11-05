"""Check that ffmpeg, ffprobe and the Python libraries pro-editor needs are installed.

Usage: python check_setup.py
Prints OK/MISSING per item plus the exact install commands for this OS.
"""

import importlib
import platform
import shutil
import sys

ok = True
system = platform.system()
print(f"System: {system}, Python {sys.version.split()[0]}")

if sys.version_info < (3, 9):  # noqa: UP036 - this runs on old Pythons to say "please upgrade"
    ok = False
    print("MISSING  Python 3.9 or newer")

for tool in ("ffmpeg", "ffprobe"):
    if shutil.which(tool):
        print(f"OK       {tool}")
    else:
        ok = False
        print(f"MISSING  {tool}")

for mod in ("numpy", "librosa", "soundfile"):
    try:
        m = importlib.import_module(mod)
        print(f"OK       {mod} {getattr(m, '__version__', '')}")
    except Exception:
        ok = False
        print(f"MISSING  {mod}")

print("\nOptional (only for some features):")
for mod, why, pkg in (
    ("faster_whisper", "transcripts, /talk, jump cuts on fillers, word captions", "faster-whisper"),
    ("cv2", "face-tracking vertical crop and the avatar", '"opencv-python-headless<5"'),
    ("mediapipe", "the avatar's hand tracking and /talk's sound recognition (laughs, cheers...)", "mediapipe"),
    ("PIL", "the avatar's speech bubbles", "pillow"),
    ("playwright", "/create (records the animated scenes)", "playwright && python -m playwright install chromium"),
):
    try:
        m = importlib.import_module(mod)
        extra = ""
        if mod == "cv2":
            from pathlib import Path

            if not (Path(m.data.haarcascades) / "haarcascade_frontalface_default.xml").exists():
                extra = "  (no face detector files: reinstall with " + pkg + ")"
        print(f"OK       {mod} {getattr(m, '__version__', '')}{extra}")
    except Exception:
        print(f"-        {mod}: needed for {why}. Install: python -m pip install {pkg}")

if not ok:
    print("\nInstall steps:")
    if not shutil.which("ffmpeg"):
        if system == "Windows":
            print("  winget install --id Gyan.FFmpeg -e   (then close and reopen the terminal)")
        elif system == "Darwin":
            print("  brew install ffmpeg")
        else:
            print("  sudo apt install ffmpeg   (or your distro's package manager)")
    print("  python -m pip install numpy librosa soundfile")
    sys.exit(1)

try:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from common import hw_encoder

    enc = hw_encoder()
    print(
        f"\nGraphics-card encoding: {enc}"
        if enc
        else "\nGraphics-card encoding: not available, renders use the CPU (slower for 1440p/4K)"
    )
except Exception:
    pass
print("All set. (python selftest.py runs every tool once, if you want proof.)")
