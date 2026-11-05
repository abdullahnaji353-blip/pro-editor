"""Footage health check: finds the problems that break edits BEFORE you spend time editing.

Usage: python checkup.py VIDEO_OR_FOLDER... [--fix] [--tests] [--out-dir checkup]

Checks each file for:
  - variable frame rate (phones, screen recorders): audio slowly drifts out of sync after cuts
  - HDR (iPhone HLG / Dolby Vision, some Android): colours look grey and washed out when edited
  - audio tracks: is your mic on its own track? is there audio at all?
  - keyframe spacing: how precise fast frame-sampling will be (clip library)
  - loudness and clipping
  - resolution, frame rate, rotation, codec
--fix     writes <name>_fixed.mp4 (constant frame rate, SDR colours) when a file needs it.
          Edit the fixed copy; the original is never touched.
--tests   also tries face detection and a 20-second transcript on the footage, so you find
          out now whether those features will work on your machine.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from common import VIDEO_EXTS, audio_tracks, collect_media, ffmpeg, measure_lufs, need, probe, run, save_json


def stream_info(path):
    res = run([need("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
               "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,color_transfer,color_primaries,"
               "pix_fmt:stream_side_data=rotation,side_data_type", "-of", "json", str(path)])
    s = (json.loads(res.stdout).get("streams") or [{}])[0]
    side = s.get("side_data_list") or []
    s["rotation"] = next((d.get("rotation") for d in side if "rotation" in d), 0)
    s["dolby_vision"] = any("DOVI" in str(d.get("side_data_type", "")) or "Dolby" in str(d.get("side_data_type", ""))
                            for d in side)
    return s


def rate(r):
    try:
        n, d = r.split("/")
        return float(n) / float(d) if float(d) else 0.0
    except Exception:
        return 0.0


def frame_timing(path, seconds=30):
    res = run([need("ffprobe"), "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+{seconds}",
               "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", str(path)])
    pts, keys = [], []
    for line in res.stdout.splitlines():
        parts = line.split(",")
        if parts and parts[0] not in ("", "N/A"):
            t = float(parts[0])
            pts.append(t)
            if len(parts) > 1 and "K" in parts[1]:
                keys.append(t)
    pts = np.sort(np.array(pts))
    d = np.diff(pts) if len(pts) > 2 else np.array([0.0])
    d = d[d > 0]
    vfr_score = float(np.std(d) / np.mean(d)) if len(d) else 0.0
    kgap = float(np.median(np.diff(sorted(keys)))) if len(keys) > 2 else None
    return vfr_score, kgap


def has_filter(name):
    res = subprocess.run([need("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True)
    return re.search(rf"\s{name}\s", res.stdout) is not None


def fix(path, out, vfr, hdr, fps):
    vf = []
    if hdr:
        vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                  "zscale=t=bt709:m=bt709:r=tv")
    if vfr:
        vf.append(f"fps={fps}")
    vf.append("format=yuv420p")
    ffmpeg(["-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-vf", ",".join(vf), "-c:v", "libx264",
            "-preset", "medium", "-crf", "16", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)], hw=True)


def quick_tests(path, info):
    notes = []
    try:
        import cv2
        xml = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if not xml.exists():
            notes.append("Face tracking: OpenCV is missing its face files. Fix: pip install \"opencv-python-headless<5\"")
        else:
            det = cv2.CascadeClassifier(str(xml))
            hits = 0
            for t in np.linspace(0, max(0.0, info["duration"] - 0.5), 10):
                res = subprocess.run([need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i",
                                      str(path), "-frames:v", "1", "-vf", "scale=640:-2,format=gray", "-f", "rawvideo",
                                      "-"], capture_output=True)
                h = len(res.stdout) // 640
                if h:
                    img = np.frombuffer(res.stdout[:640 * h], np.uint8).reshape(h, 640)
                    hits += len(det.detectMultiScale(img, 1.12, 5, minSize=(int(h * 0.07),) * 2)) > 0
            notes.append(f"Face tracking: a face was found in {hits}/10 sample frames"
                         + (" - reframe.py will follow it." if hits >= 5 else
                            " - for this footage use --keyframes or a centre/blurred crop."))
    except ImportError:
        notes.append("Face tracking: not installed (pip install \"opencv-python-headless<5\") - only needed for vlogs.")
    try:
        import tempfile
        from faster_whisper import WhisperModel
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "a.wav"
            ffmpeg(["-t", "20", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav)])
            model = WhisperModel("tiny", device="auto", compute_type="int8")
            segs, _ = model.transcribe(str(wav))
            text = " ".join(s.text.strip() for s in segs)[:120]
        notes.append(f"Transcripts: working. First 20s heard as: \"{text or '(no speech)'}\"")
    except ImportError:
        notes.append("Transcripts: not installed (pip install faster-whisper) - only needed for vlogs/captions.")
    except Exception as e:
        notes.append(f"Transcripts: installed but the speech model couldn't load ({type(e).__name__}). It downloads on "
                     "first use, so check the internet connection, then run vlog_cut.py transcribe once.")
    return notes


def check(path, a):
    info = probe(path)
    s = stream_info(path)
    problems, notes = [], []
    if not info["has_video"]:
        return {"file": str(path), "problems": ["No video stream."], "notes": []}
    fps = rate(s.get("avg_frame_rate", "0/1")) or info["fps"] or 30
    vfr_score, kgap = frame_timing(path)
    r, avg = rate(s.get("r_frame_rate", "0/1")), rate(s.get("avg_frame_rate", "0/1"))
    vfr = vfr_score > 0.08 or (r and avg and abs(r - avg) / r > 0.02)
    transfer = (s.get("color_transfer") or "").lower()
    hdr = transfer in ("arib-std-b67", "smpte2084") or s.get("dolby_vision")
    notes.append(f"{info['width']}x{info['height']} @ {fps:.2f} fps, {s.get('codec_name', '?')}, "
                 f"{info['duration'] / 60:.1f} min" + (f", rotated {s['rotation']}°" if s.get("rotation") else ""))
    if vfr:
        problems.append("Variable frame rate (common on phones and screen recorders). Cuts can make the audio drift "
                        "out of sync. Fix: edit a constant-frame-rate copy (--fix).")
    if hdr:
        kind = "HLG" if transfer == "arib-std-b67" else ("Dolby Vision/PQ" if s.get("dolby_vision") or transfer == "smpte2084" else "HDR")
        msg = f"HDR video ({kind}). Edited as-is, colours come out grey and washed out. Fix: an SDR copy (--fix)."
        if not has_filter("zscale"):
            msg += " Your ffmpeg lacks 'zscale', which the fix needs: install the full build (Windows: gyan.dev 'full')."
        problems.append(msg)
    tracks = audio_tracks(path) if info["has_audio"] else []
    if not tracks:
        problems.append("No audio track.")
    elif len(tracks) > 1:
        names = ", ".join(f"#{t['track']} {t['title'] or 'untitled'}" for t in tracks)
        notes.append(f"{len(tracks)} audio tracks ({names}). Good: game and mic can be handled separately "
                     "(--audio-track N).")
    else:
        notes.append("1 audio track: if you talk while recording, your voice is mixed with the game sound.")
    if kgap and kgap > 4:
        notes.append(f"Keyframes every {kgap:.1f}s: the clip library's fast mode samples that sparsely; "
                     "use library.py index --accurate for short clips.")
    if tracks:
        lufs, peak = measure_lufs(path) if info["duration"] < 900 else (None, None)
        if lufs is not None:
            notes.append(f"Loudness {lufs} LUFS, peak {peak} dBFS (exports are set to -14 automatically).")
            if peak is not None and peak > -0.3:
                problems.append("Audio hits 0 dB: the recording itself clipped. Lower the game/mic volume when recording.")
    if a.tests:
        notes += quick_tests(path, info)
    rep = {"file": str(Path(path).resolve()), "fps": round(fps, 3), "vfr": bool(vfr), "hdr": bool(hdr),
           "problems": problems, "notes": notes}
    if a.fix and (vfr or hdr):
        if hdr and not has_filter("zscale"):
            rep["fixed"] = None
        else:
            out = Path(a.out_dir) / f"{Path(path).stem}_fixed.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            print(f"  fixing -> {out.name} ...")
            fix(path, out, vfr, hdr, round(fps) if fps > 1 else 30)
            rep["fixed"] = str(out.resolve())
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--tests", action="store_true")
    ap.add_argument("--out-dir", default="checkup")
    a = ap.parse_args()
    reports = []
    for v in collect_media(a.inputs, VIDEO_EXTS):
        print(f"\n{v.name}")
        r = check(v, a)
        reports.append(r)
        for p in r["problems"]:
            print(f"  PROBLEM  {p}")
        for n in r["notes"]:
            print(f"  ok       {n}")
        if r.get("fixed"):
            print(f"  FIXED -> {r['fixed']}  (edit this copy)")
        if not r["problems"]:
            print("  Ready to edit.")
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    save_json({"files": reports}, Path(a.out_dir) / "checkup.json")
