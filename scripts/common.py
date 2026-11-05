"""Shared helpers for the pro-editor scripts: ffmpeg/ffprobe wrappers, JSON IO, font lookup."""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def need(tool):
    path = shutil.which(tool)
    if not path:
        die(f"'{tool}' not found on PATH. Run check_setup.py for install steps.")
    return path


def run(cmd, quiet=True):
    """Run a command list; raise with stderr tail on failure."""
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        tail = "\n".join(res.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"Command failed ({cmd[0]}):\n{tail}")
    if not quiet and res.stdout:
        print(res.stdout)
    return res


# ------------------------------------------------------------------ GPU encode / decode
# Final renders use the graphics card's video encoder when one works (several times faster for
# 1440p/4K). Each candidate is test-encoded once and the answer cached. If a GPU encode ever fails,
# the same command is retried on the CPU automatically. Env PRO_EDITOR_GPU=0 turns this off;
# PRO_EDITOR_GPU=nvenc|qsv|amf|videotoolbox forces one. Temporary pieces always use the CPU so a
# file is never stitched from mixed encoders.
_HW_CANDIDATES = ["h264_nvenc", "h264_videotoolbox", "h264_qsv", "h264_amf"]
_HW = {"enc": "unset", "dec": "unset", "warned": False}


def _cache_file():
    return Path.home() / ".cache" / "pro-editor" / "gpu.json"


def _ffmpeg_id():
    res = subprocess.run([need("ffmpeg"), "-hide_banner", "-version"], capture_output=True, text=True)
    return (shutil.which("ffmpeg") or "") + "|" + (res.stdout.splitlines() or [""])[0]


def hw_encoder():
    """Name of a working hardware H.264 encoder, or None."""
    if _HW["enc"] != "unset":
        return _HW["enc"]
    pref = os.environ.get("PRO_EDITOR_GPU", "auto").lower()
    if pref in ("0", "off", "no", "cpu", "false"):
        _HW["enc"] = None
        return None
    cands = [c for c in _HW_CANDIDATES if pref == "auto" or pref in c]
    cache, key = _cache_file(), _ffmpeg_id()
    try:
        data = json.loads(cache.read_text())
        if data.get("key") == key and data.get("pref") == pref:
            _HW["enc"] = data.get("encoder")
            return _HW["enc"]
    except Exception:
        pass
    found = None
    for c in cands:
        r = subprocess.run(
            [
                need("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=s=640x360:r=30:d=0.5",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                c,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            found = c
            break
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key, "pref": pref, "encoder": found}))
    except Exception:
        pass
    _HW["enc"] = found
    return found


def dec_args():
    """['-hwaccel', 'auto'] when hardware decoding is allowed (falls back to software by itself)."""
    if os.environ.get("PRO_EDITOR_GPU", "auto").lower() in ("0", "off", "no", "cpu", "false"):
        return []
    return ["-hwaccel", "auto"]


def _hw_video_args(enc, crf, preset):
    fast = preset in ("ultrafast", "superfast", "veryfast", "faster", "fast")
    q = int(round(float(crf))) + 1
    if enc == "h264_nvenc":
        return [
            "-c:v",
            enc,
            "-preset",
            "p2" if fast else "p5",
            "-rc",
            "vbr",
            "-cq",
            str(q),
            "-b:v",
            "0",
            "-profile:v",
            "high",
        ]
    if enc == "h264_qsv":
        return ["-c:v", enc, "-preset", "veryfast" if fast else "medium", "-global_quality", str(q)]
    if enc == "h264_amf":
        return [
            "-c:v",
            enc,
            "-quality",
            "speed" if fast else "quality",
            "-rc",
            "cqp",
            "-qp_i",
            str(q),
            "-qp_p",
            str(q + 2),
            "-qp_b",
            str(q + 4),
        ]
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-q:v", str(max(20, min(90, 100 - q * 2))), "-allow_sw", "1"]
    return None


def _swap_to_hw(args, enc):
    """Replace '-c:v libx264 ... -preset P -crf C [-profile:v X]' with the hardware encoder's options."""
    if "-c:v" not in args:
        return None
    i = args.index("-c:v")
    if args[i + 1] != "libx264":
        return None
    out, preset, crf, k = [], "medium", "18", 0
    while k < len(args):
        if k == i:
            k += 2
            continue
        if k > i and args[k] in ("-preset", "-crf", "-profile:v", "-tune", "-x264-params") and k + 1 < len(args):
            if args[k] == "-preset":
                preset = args[k + 1]
            elif args[k] == "-crf":
                crf = args[k + 1]
            k += 2
            continue
        out.append(args[k])
        k += 1
    hw = _hw_video_args(enc, crf, preset)
    if not hw:
        return None
    return out[:-1] + hw + out[-1:]  # keep the output path last


def ffmpeg(args, hw=False):
    """Run ffmpeg. libx264 outputs are always 8-bit 4:2:0 (plays everywhere). hw=True: try the GPU
    encoder first and fall back to the CPU command automatically if it fails."""
    args = list(args)
    if "-c:v" in args and args[args.index("-c:v") + 1] == "libx264" and "-pix_fmt" not in args:
        args = args[:-1] + ["-pix_fmt", "yuv420p", args[-1]]
    base = [need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y"]
    if hw:
        enc = hw_encoder()
        swapped = _swap_to_hw(args, enc) if enc else None
        if swapped:
            res = subprocess.run(base + swapped, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.returncode == 0:
                return res
            if not _HW["warned"]:
                print(f"  (GPU encoder {enc} failed on this render; using the CPU instead)")
                _HW["warned"] = True
    return run(base + args)


def probe(path):
    """Return dict with duration, width, height, fps, has_audio for a media file."""
    res = run([need("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    data = json.loads(res.stdout)
    info = {
        "path": str(Path(path).resolve()),
        "duration": float(data["format"].get("duration", 0) or 0),
        "width": None,
        "height": None,
        "fps": None,
        "has_audio": False,
        "has_video": False,
    }
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            if s.get("disposition", {}).get("attached_pic"):
                continue
            info["has_video"] = True
            info["width"], info["height"] = s.get("width"), s.get("height")
            # phones often store portrait video as landscape + a rotation flag; ffmpeg turns the
            # frames upright when decoding, so report the size you actually get
            rot = 0
            for sd in s.get("side_data_list") or []:
                if "rotation" in sd:
                    try:
                        rot = int(round(float(sd["rotation"])))
                    except (TypeError, ValueError):
                        pass
            if not rot and (s.get("tags") or {}).get("rotate"):
                try:
                    rot = int(s["tags"]["rotate"])
                except ValueError:
                    pass
            info["rotation"] = rot
            if abs(rot) % 180 == 90 and info["width"] and info["height"]:
                info["width"], info["height"] = info["height"], info["width"]
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            num, den = (rate.split("/") + ["1"])[:2]
            try:
                info["fps"] = round(float(num) / float(den), 3) if float(den) else None
            except ValueError:
                info["fps"] = None
            if not info["duration"] and s.get("duration"):
                info["duration"] = float(s["duration"])
        if s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def extract_audio(src, dst_wav, sr=22050, track=0, af=None):
    extra = ["-af", af] if af else []
    ffmpeg(
        ["-i", str(src), "-map", f"0:a:{track}", "-vn", *extra, "-ac", "1", "-ar", str(sr), "-f", "wav", str(dst_wav)]
    )
    return dst_wav


def audio_tracks(path):
    """List audio streams with their titles (OBS multi-track recordings name them)."""
    res = run(
        [
            need("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index,channels:stream_tags=title,handler_name",
            "-of",
            "json",
            str(path),
        ]
    )
    out = []
    for i, s in enumerate(json.loads(res.stdout).get("streams", [])):
        tags = s.get("tags", {})
        out.append(
            {
                "track": i,
                "channels": s.get("channels"),
                "title": tags.get("title")
                or ("" if tags.get("handler_name", "").endswith("Handler") else tags.get("handler_name", "")),
            }
        )
    return out


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return path


def measure_lufs(path):
    """Integrated loudness (LUFS) and true peak (dBFS) of a file's first audio track."""
    import re

    res = run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]
    )
    tail = res.stderr[res.stderr.rfind("Summary:") :]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    pk = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    return (float(i.group(1)) if i else None, float(pk.group(1)) if pk else None)


def normalize_loudness(path, target=-14.0, ceiling_db=-2.0):
    """Hit a loudness target: measure, apply gain + peak limiter, re-measure and correct once
    (the limiter eats some loudness on already-loud mixes). Rewrites audio, copies video."""
    lufs, _ = measure_lufs(path)
    if lufs is None or lufs < -70:  # silent
        return lufs
    gain = target - lufs
    if abs(gain) < 0.3:
        return lufs
    path = Path(path)
    tmp = path.with_name(path.stem + "._norm" + path.suffix)
    limit = 10 ** (ceiling_db / 20)
    result = lufs
    for _ in range(3):
        ffmpeg(
            [
                "-i",
                str(path),
                "-map",
                "0",
                "-c:v",
                "copy",
                "-c:s",
                "copy",
                "-af",
                f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:level=disabled",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                str(tmp),
            ]
        )
        result = measure_lufs(tmp)[0]
        if result is None or abs(target - result) <= 0.5 or gain > 20:
            break
        gain += target - result
    tmp.replace(path)
    return result


def collect_media(paths, exts):
    """Expand files/folders into a sorted list of media files with the given extensions."""
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(x for x in p.iterdir() if x.suffix.lower() in exts)
        elif p.exists():
            out.append(p)
        else:
            die(f"File not found: {p}")
    return out


def find_font():
    """Best-effort bold sans font for drawtext. Returns a path or None."""
    candidates = []
    system = platform.system()
    if system == "Windows":
        windir = os.environ.get("WINDIR", "C:/Windows")
        candidates += [f"{windir}/Fonts/arialbd.ttf", f"{windir}/Fonts/impact.ttf", f"{windir}/Fonts/arial.ttf"]
    elif system == "Darwin":
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


RES_STEPS = (720, 1080, 1440, 2160)
_ASPECTS = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1), "4:5": (4, 5)}


def snap_res(short_side):
    """Largest standard resolution (by short side) that the footage actually has."""
    ok = [r for r in RES_STEPS if r <= short_side + 8]
    return ok[-1] if ok else RES_STEPS[0]


def resolve_res(res, sources=()):
    """'1080' / 1440 / '4k' / 'source' -> short-side pixels. 'source' = best of the given files."""
    r = str(res or "1080").lower().replace("p", "")
    if r in ("4k", "uhd"):
        return 2160
    if r in ("2k", "qhd"):
        return 1440
    if r == "source":
        sides = []
        for s in sources:
            try:
                i = probe(s)
                if i["width"] and i["height"]:
                    sides.append(min(i["width"], i["height"]))
            except Exception:
                pass
        return snap_res(max(sides)) if sides else 1080
    return int(r)


def frame_size(aspect, res=1080):
    """Output width, height for an aspect ratio at a resolution (short side), both even."""
    a, b = _ASPECTS.get(aspect, (16, 9))
    short = int(res)
    if a >= b:
        h, w = short, short * a / b
    else:
        w, h = short, short * b / a
    return int(round(w / 2)) * 2, int(round(h / 2)) * 2


def preview_size(W, H, short=540):
    """Previews stay small whatever the final resolution (4K previews would defeat the point)."""
    f = short / min(W, H)
    return int(W * f) // 2 * 2, int(H * f) // 2 * 2


def blur_radius(W, H):
    return max(10, int(min(W, H) / 54))


def concat_line(p):
    """One line for an ffmpeg concat list. Paths with apostrophes ("Naji's clips") must be escaped
    as '\\'' or ffmpeg can't read the list."""
    s = Path(p).resolve().as_posix().replace("'", "'\\''")
    return f"file '{s}'"


def safe_copy(p, folder, name=None):
    """Copy a file into a temp folder under a plain name, for ffmpeg filters that take a path
    (subtitles, fonts): quotes, colons and emoji in real folder names break filter parsing."""
    import shutil as _sh

    dst = Path(folder) / (name or ("f" + Path(p).suffix.lower()))
    _sh.copyfile(p, dst)
    return dst


def smooth(x, k):
    """Moving average with the same length as the input. The ends are padded with the edge values,
    not zeros, so the first and last moments aren't dragged toward silence (or, in dB, toward loud)."""
    import numpy as np

    x = np.asarray(x, dtype=float)
    k = max(1, min(int(k), len(x)))
    if k == 1:
        return x.copy()
    padded = np.pad(x, (k // 2, k - 1 - k // 2), mode="edge")
    return np.convolve(padded, np.ones(k) / k, mode="valid")


def ff_path(p):
    """Escape a filesystem path for use inside an ffmpeg filter argument (handles Windows drive colons)."""
    s = str(Path(p).resolve()).replace("\\", "/")
    return s.replace(":", "\\:").replace("'", "\\'")
