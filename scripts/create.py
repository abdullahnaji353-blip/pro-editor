"""/create: make a video from scratch: code-drawn scenes, a voiceover, music and captions.

Commands
  voice  PROJECT.json [--engine auto|say|sapi|espeak|piper|none] [--voice NAME] [--force]
         Writes a voiceover for every scene that has "narration" (vo/<id>.wav) with the computer's
         own voices, then sizes each scene to its narration. Scenes with an "audio" file use it.
  sheet  PROJECT.json [--out sheet.jpg]
         Three stills per scene (just in, middle, about to leave) in one image: check this before
         the slow render.
  render PROJECT.json [--preview] [--out video.mp4] [--only ID]
         Records every scene frame by frame in a hidden browser, joins them, mixes voice and music
         (the music ducks under the voice), burns word-by-word captions and normalises loudness.

PROJECT.json
  {"title": "...", "size": "1080x1920", "fps": 30,
   "music": "song.mp3", "music_volume": 0.18, "captions": true,
   "voice": {"engine": "auto", "voice": null},
   "scenes": [{"id": "01-hook", "html": "scenes/01-hook.html", "narration": "...", "min_duration": 2.5}]}

Each scene is an HTML file that defines window.render = (t, d) => {...} and draws everything from t
(seconds into the scene). The kit in create_kit/ (kit.css, kit.js: K.reveal, K.count, K.type,
K.grow, K.draw...) is loaded into every scene. Paths are relative to PROJECT.json.
"""

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import die, load_json, need, probe, save_json

HERE = Path(__file__).resolve().parent
KIT = HERE / "create_kit"
WPS = 2.6  # speaking rate used to size scenes when there is no voice


# ------------------------------------------------------------------ project
def load_project(path):
    path = Path(path).resolve()
    pj = load_json(path)
    if not pj.get("scenes"):
        die(f"{path} has no scenes.")
    try:
        W, H = (int(v) for v in str(pj.get("size", "1080x1920")).lower().split("x"))
    except ValueError:
        die('size must look like "1080x1920"')
    for i, s in enumerate(pj["scenes"]):
        s.setdefault("id", f"{i + 1:02d}")
        if not s.get("html"):
            die(f"Scene {s['id']} has no html file.")
    return path, pj, W, H, int(pj.get("fps", 30))


def scene_duration(s):
    if s.get("duration"):
        return float(s["duration"])
    words = len((s.get("narration") or "").split())
    return max(float(s.get("min_duration", 2.5)), words / WPS + 0.6)


# ------------------------------------------------------------------ voice
def pick_engine(want):
    if want != "auto":
        return want
    if platform.system() == "Darwin" and shutil.which("say"):
        return "say"
    if platform.system() == "Windows":
        return "sapi"
    if shutil.which("piper") and __import__("os").environ.get("PRO_EDITOR_PIPER_MODEL"):
        return "piper"
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "espeak"
    return "none"


def speak(engine, text, voice, dst):
    """Text to a 48 kHz mono wav at dst. Returns False when the engine isn't available."""
    import os

    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw.aiff"
        if engine == "say":
            cmd = ["say", "-o", str(raw)] + (["-v", voice] if voice else []) + [text]
        elif engine == "sapi":
            raw = raw.with_suffix(".wav")
            txt = Path(td) / "t.txt"
            txt.write_text(text, encoding="utf-8")
            pick = f"$s.SelectVoice('{voice}');" if voice else ""
            ps = (
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                f"{pick}$s.SetOutputToWaveFile('{raw}');$s.Speak([IO.File]::ReadAllText('{txt}'));$s.Dispose()"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps]
        elif engine == "espeak":
            raw = raw.with_suffix(".wav")
            exe = shutil.which("espeak-ng") or "espeak"
            cmd = [exe, "-w", str(raw)] + (["-v", voice] if voice else []) + [text]
        elif engine == "piper":
            raw = raw.with_suffix(".wav")
            cmd = ["piper", "--model", os.environ["PRO_EDITOR_PIPER_MODEL"], "--output_file", str(raw)]
            r = subprocess.run(cmd, input=text, text=True, capture_output=True)
            if r.returncode or not raw.exists():
                return False
            cmd = None
        else:
            return False
        if cmd:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode or not raw.exists():
                return False
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "48000", "-ac", "1", str(dst)], check=True
        )
    return True


def cmd_voice(a):
    path, pj, W, H, fps = load_project(a.project)
    base = path.parent
    vcfg = pj.get("voice") or {}
    engine = pick_engine(a.engine or vcfg.get("engine", "auto"))
    voice = a.voice or vcfg.get("voice")
    (base / "vo").mkdir(exist_ok=True)
    made = 0
    for s in pj["scenes"]:
        audio = s.get("audio")
        if not audio and s.get("narration") and engine != "none":
            dst = base / "vo" / f"{s['id']}.wav"
            if a.force or not dst.exists():
                if not speak(engine, s["narration"], voice, dst):
                    die(f"The {engine} voice failed on scene {s['id']}. Try --engine none, or another --voice.")
                made += 1
            s["audio"] = audio = str(dst.relative_to(base))
        if audio:
            dur = probe(base / audio)["duration"]
            s["audio_duration"] = round(dur, 3)
            s["duration"] = round(max(float(s.get("min_duration", 2.0)), dur + 0.45), 3)
        else:
            s.pop("audio_duration", None)
            s["duration"] = round(scene_duration({**s, "duration": None}), 3)
    pj.setdefault("voice", {})["engine"] = engine
    if pj.get("sync") in ("beats", "bars"):
        if snap_durations(pj, song_beats(base, pj)):
            print(f"Scenes snapped to the music's {pj['sync']}")
        else:
            print('sync needs "music" in the project; scenes keep their own timing')
    save_json(pj, path)
    total = sum(s["duration"] for s in pj["scenes"])
    print(f"Voice: {engine}" + (f" ({voice})" if voice else "") + f", {made} line(s) recorded")
    for s in pj["scenes"]:
        print(f"  {s['id']:<20} {s['duration']:5.2f}s  {(s.get('narration') or '')[:60]}")
    print(f"Total {total:.1f}s -> {path}")
    if engine == "none":
        print("  (no voice engine: scenes are timed for reading. On a Mac `say` works out of the box.)")


# ------------------------------------------------------------------ music sync
def song_beats(base, pj):
    """Beats of the project's music, cached next to the project."""
    music = pj.get("music")
    if not music:
        return None
    cache = base / ".render" / "beats.json"
    src = (base / music).resolve()
    if cache.exists():
        b = load_json(cache)
        if b.get("song") == str(src):
            return b
    from beats import analyze

    b = analyze(src)
    b["song"] = str(src)
    cache.parent.mkdir(exist_ok=True)
    save_json(b, cache)
    return b


def snap_durations(pj, beats):
    """End every scene on a beat (sync: beats) or a bar start (sync: bars), never cutting it much short."""
    mode = pj.get("sync")
    if mode not in ("beats", "bars") or not beats:
        return False
    grid = beats["downbeats"] if mode == "bars" and len(beats.get("downbeats", [])) > 2 else beats["beats"]
    t = 0.0
    for s in pj["scenes"]:
        want = t + scene_duration(s)
        floor = t + max(0.8, scene_duration(s) * 0.85)  # don't cut the narration or the animation short
        ok = [g for g in grid if g >= floor]
        end = min(ok, key=lambda g: abs(g - want)) if ok else want
        s["duration"] = round(end - t, 3)
        t = end
    return True


def scene_beats(pj, beats, durs):
    """Beat, downbeat and drop times relative to each scene's start."""
    out, t = [], 0.0
    for d in durs:
        out.append(
            {
                k: [round(x - t, 3) for x in (beats or {}).get(k, []) if t <= x < t + d]
                for k in ("beats", "downbeats", "drops")
            }
        )
        t += d
    return out


# ------------------------------------------------------------------ drawing
def open_scene(page, base, scene, W, H, beat_info=None):
    page.goto((base / scene["html"]).resolve().as_uri())
    page.add_style_tag(path=str(KIT / "kit.css"))
    page.add_script_tag(path=str(KIT / "kit.js"))
    page.evaluate(f"document.body.classList.add('{'v' if H > W else 'h'}')")
    page.evaluate(
        "(b) => { window.BEATS = b.beats; window.DOWNBEATS = b.downbeats; window.DROPS = b.drops; }",
        beat_info or {"beats": [], "downbeats": [], "drops": []},
    )
    # scenes may load the kit themselves; if render is defined inline it runs after the kit is present
    page.evaluate("document.fonts.ready")
    if not page.evaluate("typeof window.render === 'function'"):
        die(f"{scene['html']} doesn't define window.render = (t, d) => {{...}}")


def draw(page, t, d):
    page.evaluate(f"window.render({t:.5f}, {d:.5f})")


def cmd_sheet(a):
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright

    path, pj, W, H, fps = load_project(a.project)
    base = path.parent
    tw = 360 if H > W else 480
    th = int(tw * H / W)
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=tw / W)
        per = scene_beats(pj, song_beats(base, pj), [scene_duration(x) for x in pj["scenes"]])
        for s, bi in zip(pj["scenes"], per):
            d = scene_duration(s)
            open_scene(page, base, s, W, H, bi)
            tiles = []
            for t in (min(0.5, d / 4), d / 2, max(0, d - 0.3)):
                draw(page, t, d)
                with tempfile.NamedTemporaryFile(suffix=".png") as f:
                    page.screenshot(path=f.name)
                    im = Image.open(f.name).convert("RGB").resize((tw, th))
                ImageDraw.Draw(im).text((10, 8), f"{s['id']}  {t:.1f}s", fill=(255, 80, 80))
                tiles.append(im)
            rows.append(tiles)
        browser.close()
    sheet = Image.new("RGB", (3 * tw + 40, len(rows) * (th + 10) + 10), (40, 40, 40))
    for r, tiles in enumerate(rows):
        for c, im in enumerate(tiles):
            sheet.paste(im, (10 + c * (tw + 10), 10 + r * (th + 10)))
    out = Path(a.out or path.with_name(path.stem + "_sheet.jpg"))
    sheet.save(out, quality=88)
    print(f"Sheet -> {out}  ({len(rows)} scenes, 3 stills each)")


def render_scene(page, base, s, W, H, fps, dst, preview, beat_info=None):
    d = scene_duration(s)
    n = max(1, round(d * fps))
    open_scene(page, base, s, W, H, beat_info)
    tmp = dst.with_name(dst.stem + ".part.mp4")
    ow, oh = (W // 2 // 2 * 2, H // 2 // 2 * 2) if preview else (W, H)
    ff = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "image2pipe",
            "-c:v",
            "mjpeg",
            "-framerate",
            str(fps),
            "-i",
            "-",
            "-vf",
            f"scale={ow}:{oh}:flags=lanczos,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if preview else "medium",
            "-crf",
            "20" if preview else "17",
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            str(tmp),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for i in range(n):
            draw(page, i / fps, d)
            ff.stdin.write(page.screenshot(type="jpeg", quality=92))
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode:
        die(f"Encoding scene {s['id']} failed.")
    tmp.replace(dst)
    return n / fps


def build_audio(base, pj, durs, total, out_wav):
    """Voice lines placed at their scenes' starts, music under them ducking while someone talks."""
    inputs, chains, labels = [], [], []
    t = 0.0
    for s, d in zip(pj["scenes"], durs):
        if s.get("audio"):
            k = len(inputs)
            inputs += ["-i", str(base / s["audio"])]
            ms = int(round((t + 0.15) * 1000))
            chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
            labels.append(f"[v{k}]")
        t += d
    music = pj.get("music")
    has_voice = bool(labels)
    if not has_voice and not music:
        return False
    if has_voice:
        chains.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{total:.3f}[voice]"
        )
    if music:
        k = len(inputs)
        inputs += ["-stream_loop", "-1", "-i", str((base / music).resolve())]
        vol = float(pj.get("music_volume", 0.18 if has_voice else 0.8))
        chains.append(
            f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},atrim=0:{total:.3f},"
            f"afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mus]"
        )
        if has_voice:
            chains.append("[voice]asplit[vo][key]")
            chains.append("[mus][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[duck]")
            chains.append("[vo][duck]amix=inputs=2:duration=first:normalize=0[mix]")
        else:
            chains.append("[mus]anull[mix]")
    else:
        chains.append("[voice]anull[mix]")
    chains.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(chains),
            "-map",
            "[out]",
            "-ar",
            "48000",
            "-t",
            f"{total:.3f}",
            str(out_wav),
        ],
        check=True,
    )
    return True


def caption_transcript(pj, durs):
    """Word timings for the narration: spread over each line's own audio (or its scene)."""
    segs, t = [], 0.0
    for s, d in zip(pj["scenes"], durs):
        words = (s.get("narration") or "").split()
        if words:
            span = float(s.get("audio_duration") or (d - 0.4))
            start = t + 0.15
            weights = [len(w) + 2 for w in words]
            unit = span / sum(weights)
            ws, x = [], start
            for w, k in zip(words, weights):
                ws.append({"w": w, "start": round(x, 3), "end": round(x + k * unit * 0.92, 3), "p": 1.0})
                x += k * unit
            segs.append(
                {
                    "id": len(segs) + 1,
                    "start": ws[0]["start"],
                    "end": ws[-1]["end"],
                    "text": " ".join(words),
                    "words": ws,
                }
            )
        t += d
    return {"language": "en", "segments": segs}


def cmd_render(a):
    from playwright.sync_api import sync_playwright

    need("ffmpeg")
    path, pj, W, H, fps = load_project(a.project)
    base = path.parent
    out = Path(a.out or base / f"{path.stem}.mp4").resolve()
    work = base / ".render"
    work.mkdir(exist_ok=True)
    scenes = pj["scenes"]
    files, durs = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        per = scene_beats(pj, song_beats(base, pj), [round(scene_duration(x) * fps) / fps for x in scenes])
        for s, bi in zip(scenes, per):
            dst = work / f"{s['id']}{'_p' if a.preview else ''}.mp4"
            if a.only and s["id"] != a.only and dst.exists():
                durs.append(round(scene_duration(s) * fps) / fps)
            else:
                print(f"  drawing {s['id']} ({scene_duration(s):.1f}s)")
                durs.append(render_scene(page, base, s, W, H, fps, dst, a.preview, bi))
            files.append(dst)
        browser.close()
    total = sum(durs)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files))
    silent = work / "video.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)],
        check=True,
    )
    wav = work / "mix.wav"
    has_audio = build_audio(base, pj, durs, total, wav)
    joined = work / "joined.mp4"
    if has_audio:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(silent),
                "-i",
                str(wav),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(joined),
            ],
            check=True,
        )
    else:
        shutil.copyfile(silent, joined)
    if pj.get("captions") and any(s.get("narration") for s in scenes):
        tr = work / "narration.json"
        save_json(caption_transcript(pj, durs), tr)
        args = [sys.executable, str(HERE / "captions.py"), str(joined), str(tr), "--out", str(out)]
        if pj.get("caption_position"):
            args += ["--position", pj["caption_position"]]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    else:
        shutil.copyfile(joined, out)
    info = probe(out)
    sound = [k for k, on in (("voice", any(x.get("audio") for x in scenes)), ("music", bool(pj.get("music")))) if on]
    size = f"{info['width']}x{info['height']}"
    print(f"Done -> {out}  ({size}, {info['duration']:.1f}s, {' + '.join(sound) or 'silent'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("voice")
    v.add_argument("project")
    v.add_argument("--engine", choices=["auto", "say", "sapi", "espeak", "piper", "none"])
    v.add_argument("--voice")
    v.add_argument("--force", action="store_true", help="record again even if the file exists")
    s = sub.add_parser("sheet")
    s.add_argument("project")
    s.add_argument("--out")
    r = sub.add_parser("render")
    r.add_argument("project")
    r.add_argument("--out")
    r.add_argument("--preview", action="store_true", help="half resolution, fast")
    r.add_argument("--only", help="redraw just this scene id, reuse the others")
    a = ap.parse_args()
    {"voice": cmd_voice, "sheet": cmd_sheet, "render": cmd_render}[a.cmd](a)


if __name__ == "__main__":
    main()
