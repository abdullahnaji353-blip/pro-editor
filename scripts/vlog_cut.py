"""Talking-video editing: transcripts, automatic jump cuts, and editing by deleting text.

Commands:
  transcribe VIDEO [--model auto] [--language en] [--hotwords "Naji, Rocket League"] [--multilingual]
             [--audio-track N] [--out transcript.json]
      Word-level transcript with timestamps (faster-whisper; first run downloads the model). auto =
      large-v3-turbo on an NVIDIA GPU, small on a CPU. --hotwords helps it spell names, slang and
      game terms. --multilingual for speakers who switch languages mid-sentence.
  script VIDEO TRANSCRIPT [--out script.txt]
      One numbered line per sentence. Delete a line (or start it with #) to cut it. Lines that look
      like a retake of a later line are flagged, so the bad take is easy to spot.
  cut VIDEO [--transcript T] [--script EDITED.txt] [--no-silences] [--fillers]
            [--min-silence 0.45] [--pad 0.12] [--noise auto|-38] [--audio-track N] [--out cut.mp4] [--preview]
            [--punch-in 1.12] [--punch-center 0.5] [--remove "12.3-14.0,..." | --remove-file talk.json]
      Removes silences (and filler words / deleted script lines when given), renders with tiny audio
      fades so cuts don't click, and writes cut.map.json (old->new times, for captions) and cut.xml
      (the same edit as a Premiere/Resolve timeline, video + audio).
      --punch-in zooms every other piece in (e.g. 1.12 = 12%), the YouTube trick that makes jump
      cuts feel deliberate instead of glitchy. --punch-center sets where it zooms (0 = left, 1 = right
      of the frame, e.g. where the face is). --punch-mode emphasis zooms the pieces said with the most
      energy instead (punch in on the punchline), never two in a row.
"""

import argparse
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import concat_line, die, ffmpeg, load_json, need, normalize_loudness, probe, save_json

FILLERS = {"um", "uh", "umm", "uhh", "uhm", "er", "erm", "ah", "ahh", "hmm", "hm", "mm", "mhm", "mmm"}


def norm_word(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


# ------------------------------------------------------------------ transcribe
def pick_model(model):
    """'auto' = large-v3-turbo on an NVIDIA GPU (fast and accurate), small on a CPU."""
    device, compute = "cpu", "int8"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "int8_float16"
    except Exception:
        pass
    if model in (None, "auto"):
        model = "large-v3-turbo" if device == "cuda" else "small"
    return model, device, compute


def transcribe(
    video, model="auto", language=None, track=0, hotwords=None, prompt=None, multilingual=False, quiet=False
):
    """Word-level transcript. Tuned against Whisper's known failure modes: voice-activity filtering so
    silence and music don't turn into invented sentences, no feeding of previous text (stops repetition
    loops), skipping hallucinated text inside long silences, and hotwords for names and game terms."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("Transcripts need faster-whisper:  python -m pip install faster-whisper")
    import inspect

    model, device, compute = pick_model(model)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        ffmpeg(["-i", str(video), "-map", f"0:a:{track}", "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        print(f"Loading the '{model}' speech model on the {device.upper()} (first run downloads it) ...")
        try:
            m = WhisperModel(model, device=device, compute_type=compute)
        except Exception:
            if device == "cpu":
                raise
            print("  (GPU speech model failed to load; using the CPU)")
            model, device, compute = pick_model("small" if model == "large-v3-turbo" else model)[0], "cpu", "int8"
            m = WhisperModel(model, device="cpu", compute_type="int8")
        opts = dict(
            language=language,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
            hallucination_silence_threshold=2.0,
            beam_size=5,
            hotwords=hotwords or None,
            initial_prompt=prompt or None,
            multilingual=multilingual,
        )
        allowed = set(inspect.signature(m.transcribe).parameters)
        opts = {k: v for k, v in opts.items() if k in allowed and (v is not None or k == "language")}
        segs, info = m.transcribe(str(wav), **opts)
        out = []
        for i, s in enumerate(segs, 1):
            words = [
                {"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3), "p": round(w.probability, 3)}
                for w in (s.words or [])
            ]
            out.append(
                {"id": i, "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(), "words": words}
            )
            if not quiet:
                print(f"  [{i:04d}] {s.start:7.2f}s  {s.text.strip()[:70]}", end="\r")
    if not quiet:
        print()
    return {
        "video": str(Path(video).resolve()),
        "language": info.language,
        "language_probability": round(getattr(info, "language_probability", 0) or 0, 3),
        "model": model,
        "segments": out,
    }


# ------------------------------------------------------------------ script (edit by text)
def retake_flags(segs):
    """Flag a line whose words mostly repeat in one of the next 3 lines (a redo)."""
    flags = {}
    bags = [set(norm_word(w["w"]) for w in s["words"]) - {""} for s in segs]
    for i, a in enumerate(bags):
        if len(a) < 3:
            continue
        for j in range(i + 1, min(i + 4, len(bags))):
            b = bags[j]
            # most of this line's words come back in a line just after it -> it was redone there
            if b and len(a & b) / len(a) >= 0.7 and len(b) >= len(a) * 0.7:
                flags[segs[i]["id"]] = segs[j]["id"]
                break
    return flags


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:04.1f}"


def write_script(tr, out):
    flags = retake_flags(tr["segments"])
    lines = [
        "# EDIT BY TRANSCRIPT",
        "# Delete a line, or put # at its start, to cut that part. Keep the [number] tags.",
        "# Lines marked RETAKE? look like a take you redo right after: usually cut the first one.",
        "",
    ]
    for s in tr["segments"]:
        tag = f"   <- RETAKE? (redone in [{flags[s['id']]:04d}])" if s["id"] in flags else ""
        lines.append(f"[{s['id']:04d}] {fmt(s['start'])}-{fmt(s['end'])}  {s['text']}{tag}")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(flags)


def read_script_ids(path):
    keep = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[(\d+)\]", line)
        if m and not line.lstrip().startswith("#"):
            keep.add(int(m.group(1)))
    return keep


# ------------------------------------------------------------------ cut planning
def mean_volume(video, track):
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-i",
            str(video),
            "-map",
            f"0:a:{track}",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        errors="replace",
    )
    m = re.search(r"mean_volume:\s+(-?[\d.]+) dB", res.stderr)
    return float(m.group(1)) if m else -30.0


def silences(video, track, noise_db, min_sil):
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-i",
            str(video),
            "-map",
            f"0:a:{track}",
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_sil}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        errors="replace",
    )
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", res.stderr)]
    out = list(zip(starts, ends))
    if len(starts) > len(ends):  # silent until the end
        out.append((starts[-1], float("inf")))
    return out


def subtract(ranges, cut):
    a, b = cut
    out = []
    for s, e in ranges:
        if b <= s or a >= e:
            out.append((s, e))
            continue
        if a > s:
            out.append((s, a))
        if b < e:
            out.append((b, e))
    return out


def plan_cut(video, info, a, tr=None):
    dur = info["duration"]
    keep = [(0.0, dur)]
    removed = {"silence": 0.0, "fillers": 0, "lines": 0}
    if a.script:
        if not tr:
            die("--script needs --transcript (the same one the script was made from)")
        ids = read_script_ids(a.script)
        segs = tr["segments"]
        keep = []
        for s in segs:
            if s["id"] in ids:
                keep.append((max(0.0, s["start"] - 0.12), min(dur, s["end"] + 0.18)))
        removed["lines"] = len(segs) - len([s for s in segs if s["id"] in ids])
        keep = merge(keep, 0.15)
    if not a.no_silences:
        noise = a.noise
        if noise == "auto":
            noise = max(-55.0, min(-28.0, mean_volume(video, a.audio_track) - 14))
        for s, e in silences(video, a.audio_track, float(noise), a.min_silence):
            s2, e2 = s + a.pad, min(e, dur) - a.pad
            if e2 - s2 > 0.05:
                before = sum(y - x for x, y in keep)
                keep = subtract(keep, (s2, e2))
                removed["silence"] += before - sum(y - x for x, y in keep)
    extra = []
    if getattr(a, "remove", None):
        for part in a.remove.split(","):
            try:
                x, y = [float(v) for v in part.strip().split("-")]
                extra.append((x, y))
            except ValueError:
                die(f"--remove takes START-END pairs in seconds, got '{part}'")
    if getattr(a, "remove_file", None):
        data = load_json(a.remove_file)
        rng = data.get("edit", {}).get("remove", []) if isinstance(data, dict) else data
        extra += [
            (float(r["start"]), float(r["end"])) if isinstance(r, dict) else (float(r[0]), float(r[1])) for r in rng
        ]
    for x, y in extra:
        keep = subtract(keep, (x, y))
    removed["ranges"] = len(extra)
    if a.fillers and tr:
        for s in tr["segments"]:
            for w in s["words"]:
                if norm_word(w["w"]) in FILLERS:
                    keep = subtract(keep, (w["start"] - 0.02, w["end"] + 0.03))
                    removed["fillers"] += 1
    keep = [(x, y) for x, y in merge(keep, 0.06) if y - x >= 0.2]
    return keep, removed


def merge(ranges, gap):
    out = []
    for s, e in sorted(ranges):
        if out and s - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


# ------------------------------------------------------------------ render
def punch_set(video, keep, track, mode):
    """Which pieces get the punch-in: every other one, or the ones said with the most energy."""
    if mode != "emphasis":
        return {k for k in range(len(keep)) if k % 2 == 1}
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-map",
            f"0:a:{track}",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
    )
    import numpy as np

    x = np.frombuffer(res.stdout, np.float32)
    if not len(x) or len(keep) < 3:
        return {k for k in range(len(keep)) if k % 2 == 1}
    db = []
    for s, e in keep:
        seg = x[int(s * 8000) : int(e * 8000)]
        db.append(10 * np.log10(np.mean(seg**2) + 1e-10) if len(seg) else -100)
    thr = np.percentile(db, 65)
    chosen = {k for k, d in enumerate(db) if d >= thr}
    # never zoom two pieces in a row: it reads as one long zoomed shot
    out, prev = set(), False
    for k in range(len(keep)):
        if k in chosen and not prev:
            out.add(k)
            prev = True
        else:
            prev = False
    return out


def render(video, info, keep, out, track, preview, punch=0.0, punch_center=0.5, punch_mode="alternate"):
    fps = int(round(info["fps"] or 30))
    W, H = info["width"], info["height"]
    if preview:
        W, H, fps = W // 4 * 2, H // 4 * 2, min(fps, 30)
    # snap to frames so audio and video pieces are exactly the same length
    keep = [(round(s * fps) / fps, round(e * fps) / fps) for s, e in keep]
    keep = [(s, e) for s, e in keep if e - s >= 1 / fps]
    punched = punch_set(video, keep, track, punch_mode) if punch > 1 else set()
    with tempfile.TemporaryDirectory() as td:

        def one(k):
            s, e = keep[k]
            n = round((e - s) * fps)
            D = n / fps
            v, aw = Path(td) / f"v{k:05d}.mp4", Path(td) / f"a{k:05d}.wav"
            look = f"scale={W}:{H}"
            if punch > 1 and k in punched:
                zw, zh = int(W * punch) // 2 * 2, int(H * punch) // 2 * 2
                cx = min(max(punch_center, 0.0), 1.0)
                look = f"scale={zw}:{zh},crop={W}:{H}:(iw-{W})*{cx:.3f}:(ih-{H})/2"
            ffmpeg(
                [
                    "-ss",
                    f"{s:.4f}",
                    "-t",
                    f"{D + 0.1:.4f}",
                    "-i",
                    str(video),
                    "-an",
                    "-vf",
                    f"{look},fps={fps},tpad=stop_mode=clone:stop=-1,format=yuv420p",
                    "-frames:v",
                    str(n),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "17",
                    str(v),
                ]
            )
            # (veryfast/17: about half the temp disk space of ultrafast/16 at near-identical quality,
            #  which matters when a 45-minute recording is cut into hundreds of pieces)
            if info["has_audio"]:
                f = min(0.008, D / 4)
                ffmpeg(
                    [
                        "-ss",
                        f"{s:.4f}",
                        "-t",
                        f"{D + 0.1:.4f}",
                        "-i",
                        str(video),
                        "-map",
                        f"0:a:{track}",
                        "-af",
                        f"aresample=48000,apad,atrim=0:{D:.5f},afade=t=in:d={f:.4f},"
                        f"afade=t=out:st={max(D - f, 0):.4f}:d={f:.4f}",
                        "-ac",
                        "2",
                        "-c:a",
                        "pcm_s16le",
                        str(aw),
                    ]
                )
            return v, aw

        with ThreadPoolExecutor(max(1, min(6, (__import__("os").cpu_count() or 2) // 2))) as ex:
            parts = list(ex.map(one, range(len(keep))))
        (Path(td) / "v.txt").write_text("\n".join(concat_line(v) for v, _ in parts), encoding="utf-8")
        args = ["-f", "concat", "-safe", "0", "-i", str(Path(td) / "v.txt")]
        if info["has_audio"]:
            (Path(td) / "a.txt").write_text("\n".join(concat_line(a) for _, a in parts), encoding="utf-8")
            args += [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(Path(td) / "a.txt"),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]
        enc = ["-preset", "veryfast", "-crf", "26"] if preview else ["-preset", "medium", "-crf", "18"]
        ffmpeg([*args, "-c:v", "libx264", *enc, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], hw=True)
    return keep, fps, punched


def write_outputs(video, info, keep, fps, out, punch=0.0, punched=None):
    from xml_timeline import write_xmeml

    segs, t = [], 0
    mapping = []
    for i, (s, e) in enumerate(keep):
        n = round((e - s) * fps)
        segs.append(
            {
                "index": i,
                "tl_start_frame": t,
                "tl_end_frame": t + n,
                "source": str(Path(video).resolve()),
                "src_in": s,
                "speed": 1.0,
                "effects": [f"punch-in {int(round((punch - 1) * 100))}%"]
                if punch > 1 and i in (punched if punched is not None else {j for j in range(len(keep)) if j % 2})
                else [],
            }
        )
        mapping.append({"src_start": round(s, 4), "src_end": round(e, 4), "out_start": round(t / fps, 4)})
        t += n
    save_json({"video": str(Path(video).resolve()), "fps": fps, "ranges": mapping}, Path(out).with_suffix(".map.json"))
    write_xmeml(
        {
            "name": Path(out).stem,
            "fps": fps,
            "width": info["width"],
            "height": info["height"],
            "segments": segs,
            "song": None,
            "source_audio": info["has_audio"],
        },
        Path(out).with_suffix(".xml"),
    )
    return t / fps


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("transcribe")
    p.add_argument("video")
    p.add_argument("--model", default="auto")
    p.add_argument("--language")
    p.add_argument("--audio-track", type=int, default=0)
    p.add_argument("--hotwords", help='names and terms it should expect, e.g. "Naji, Rocket League, flip reset"')
    p.add_argument("--prompt", help="a sentence of context in the speaker's style (helps spelling and punctuation)")
    p.add_argument("--multilingual", action="store_true", help="speaker switches languages (e.g. Arabic + English)")
    p.add_argument("--out", default="transcript.json")
    p = sub.add_parser("script")
    p.add_argument("video")
    p.add_argument("transcript")
    p.add_argument("--out", default="script.txt")
    p = sub.add_parser("cut")
    p.add_argument("video")
    p.add_argument("--transcript")
    p.add_argument("--script")
    p.add_argument("--no-silences", action="store_true")
    p.add_argument("--fillers", action="store_true")
    p.add_argument("--min-silence", type=float, default=0.45, help="shortest pause to cut (s)")
    p.add_argument("--pad", type=float, default=0.12, help="breathing room kept at each side of a cut (s)")
    p.add_argument("--noise", default="auto", help="silence threshold in dB, or auto")
    p.add_argument("--audio-track", type=int, default=0)
    p.add_argument("--out", default="cut.mp4")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--lufs", type=float, default=-14.0)
    p.add_argument("--remove", help='extra time ranges to cut, e.g. "12.3-14.0,55.1-57.9"')
    p.add_argument("--remove-file", help="JSON with ranges to cut (the edit.remove list that listen.py writes)")
    p.add_argument("--punch-in", type=float, default=0.0, help="zoom every other piece, e.g. 1.12")
    p.add_argument("--punch-center", type=float, default=0.5, help="where to zoom: 0 left .. 1 right")
    p.add_argument(
        "--punch-mode",
        choices=["alternate", "emphasis"],
        default="alternate",
        help="alternate = every other piece (two-camera look); emphasis = the pieces said with the most energy",
    )
    a = ap.parse_args()

    if a.cmd == "transcribe":
        tr = transcribe(a.video, a.model, a.language, a.audio_track, a.hotwords, a.prompt, a.multilingual)
        save_json(tr, a.out)
        print(f"{len(tr['segments'])} lines ({tr['language']}) -> {a.out}")
    elif a.cmd == "script":
        n = write_script(load_json(a.transcript), a.out)
        print(f"Script -> {a.out}" + (f"  ({n} possible retake(s) flagged)" if n else ""))
    else:
        info = probe(a.video)
        if not info["has_video"]:
            die("Input has no video.")
        tr = load_json(a.transcript) if a.transcript else None
        keep, removed = plan_cut(a.video, info, a, tr)
        if not keep:
            die("Everything would be cut. Check --noise / --min-silence or the script.")
        keep, fps, punched = render(
            a.video, info, keep, a.out, a.audio_track, a.preview, a.punch_in, a.punch_center, a.punch_mode
        )
        new_len = write_outputs(a.video, info, keep, fps, a.out, a.punch_in, punched)
        if info["has_audio"] and a.lufs:
            normalize_loudness(a.out, a.lufs)
        print(
            f"{info['duration']:.1f}s -> {new_len:.1f}s ({len(keep)} pieces, "
            f"{info['duration'] - new_len:.1f}s removed: silences {removed['silence']:.1f}s, "
            f"fillers {removed['fillers']}, deleted lines {removed['lines']}, ranges {removed.get('ranges', 0)})"
        )
        print(
            f"Done -> {a.out}  (+ {Path(a.out).with_suffix('.map.json').name}, {Path(a.out).with_suffix('.xml').name})"
        )
