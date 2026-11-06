"""/create: make a video from scratch: code-drawn scenes, a voiceover, music and captions.

Commands
  voice  PROJECT.json [--engine auto|kokoro|say|sapi|espeak|piper|elevenlabs|none] [--voice NAME] [--force]
         Writes a voiceover for every scene that has "narration" (vo/<id>.wav), then sizes each
         scene to its narration. Scenes with an "audio" file use it. With "voiceover": "vo.mp3"
         (one recording of the whole script: an AI voice from ElevenLabs or another tool, or the
         user's own) it is cut at the pauses between scenes instead. elevenlabs needs
         ELEVENLABS_API_KEY; --voice is then a voice id. kokoro is a free neural voice that runs
         locally (pip install kokoro-onnx soundfile; voices like am_michael, af_heart, bm_george).
  sheet  PROJECT.json [--out sheet.jpg]
         Three stills per scene (just in, middle, about to leave) in one image: check this before
         the slow render.
  render PROJECT.json [--preview] [--out video.mp4] [--only ID]
         Records every scene frame by frame in a hidden browser, joins them, mixes voice and music
         (the music ducks under the voice), burns word-by-word captions and normalises loudness.

PROJECT.json
  {"title": "...", "size": "1080x1920", "fps": 30,
   "look": "collage | editorial | news | hype | minimal | tech | pop",
   "music": "song.mp3", "music_volume": 0.18, "captions": true, "sfx": true, "sfx_volume": 0.22,
   "voice": {"engine": "auto", "voice": null}, "voiceover": null,
   "scenes": [{"id": "01-hook", "html": "scenes/01-hook.html", "narration": "...", "min_duration": 2.5}]}

Each scene is an HTML file that defines window.render = (t, d) => {...} and draws everything from t
(seconds into the scene). The kit in create_kit/ (kit.css, kit.js: K.reveal, K.count, K.type,
K.grow, K.draw...) and host.js (K.host: an animated presenter that lip-syncs to the voice; K.talk(t)
is the voice's loudness right now, 0-1) are loaded into every scene. Paths are relative to PROJECT.json.
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
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


def kokoro_dir():
    import os

    return Path(os.environ.get("PRO_EDITOR_KOKORO_DIR") or Path.home() / ".cache" / "pro-editor" / "kokoro")


def has_kokoro():
    import importlib.util

    return importlib.util.find_spec("kokoro_onnx") is not None


def kokoro(text, voice, dst):
    """Kokoro: a free, open neural voice that runs on the computer (about 120 MB, downloaded once)."""
    import urllib.request

    import numpy as np
    import soundfile as sf

    if not has_kokoro():
        die("Kokoro needs:  python -m pip install kokoro-onnx soundfile")
    d = kokoro_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in KOKORO_FILES:
        if not (d / f).exists():
            print(f"  downloading the Kokoro voice model ({f}, once) ...")
            urllib.request.urlretrieve(KOKORO_URL + f, d / (f + ".part"))
            (d / (f + ".part")).replace(d / f)
    from kokoro_onnx import Kokoro

    global _KOKORO
    if "_KOKORO" not in globals():
        _KOKORO = Kokoro(str(d / KOKORO_FILES[0]), str(d / KOKORO_FILES[1]))
    v = voice or "am_michael"
    lang = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "i": "it", "p": "pt-br", "j": "ja", "z": "cmn"}
    audio, sr = _KOKORO.create(text, voice=v, speed=1.05, lang=lang.get(v[0], "en-us"))
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / "k.wav"
        sf.write(w, np.asarray(audio), sr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(w), "-ar", "48000", "-ac", "1", str(dst)], check=True)
    return True


def pick_engine(want):
    if want != "auto":
        return want
    if has_kokoro():
        return "kokoro"
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
        elif engine == "elevenlabs":
            return elevenlabs(text, voice, dst)
        elif engine == "kokoro":
            return kokoro(text, voice, dst)
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


def elevenlabs(text, voice, dst):
    """ElevenLabs text to speech over its HTTP API (ELEVENLABS_API_KEY). Costs the user's credits."""
    import json
    import os
    import urllib.request

    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        die("Set ELEVENLABS_API_KEY to use --engine elevenlabs, or make the voiceover with the ElevenLabs connector.")
    vid = voice or "JBFqnCBsd6RMkjVDRZzb"
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
        data=json.dumps(
            {"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")}
        ).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with tempfile.TemporaryDirectory() as td:
        mp3 = Path(td) / "a.mp3"
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                mp3.write_bytes(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"ElevenLabs: {e}", file=sys.stderr)
            return False
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "1", str(dst)], check=True
        )
    return True


def load_mono(path, sr=16000):
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def pauses(x, sr, min_gap=0.22):
    """Midpoints and lengths of the quiet stretches between words, in seconds."""
    import numpy as np

    hop = sr // 50
    n = len(x) // hop
    if n == 0:
        return []
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    quiet = rms < max(np.percentile(rms, 95) * 0.06, 1e-4)
    out, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) / 50 >= min_gap and i > 0 and j < n:
                out.append(((i + j) / 100, (j - i) / 50))
            i = j
        else:
            i += 1
    return out


def split_points(gaps, weights, total):
    """One cut per scene boundary: the pause nearest where the words say it should be, longer pauses preferred."""
    cuts, cum, last = [], 0.0, 0.0
    tw = sum(weights) or 1
    for w in weights[:-1]:
        cum += w
        want = total * cum / tw
        ok = [g for g in gaps if g[0] > last + 0.3]
        if not ok:
            cut = max(want, last + 0.3)
        else:
            cut = min(ok, key=lambda g: abs(g[0] - want) / (0.5 + g[1]))[0]
        cuts.append(cut)
        last = cut
    return cuts


def split_voiceover(base, pj):
    """Cut one whole-script recording into per-scene lines at the pauses between them."""
    src = base / pj["voiceover"]
    if not src.exists():
        die(f"voiceover file not found: {src}")
    scenes = [s for s in pj["scenes"] if s.get("narration")]
    if not scenes:
        die('"voiceover" needs "narration" on the scenes it covers.')
    x, sr = load_mono(src)
    total = len(x) / sr
    cuts = split_points(pauses(x, sr), [len(s["narration"].split()) for s in scenes], total)
    edges = [0.0, *cuts, total]
    for s, a, b in zip(scenes, edges, edges[1:]):
        dst = base / "vo" / f"{s['id']}.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(src),
                "-ss",
                f"{a:.3f}",
                "-to",
                f"{b:.3f}",
                "-af",
                "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                "-ar",
                "48000",
                "-ac",
                "1",
                str(dst),
            ],
            check=True,
        )
        s["audio"] = str(dst.relative_to(base))
    return len(scenes)


def amp_envelope(path, fps, lead=0.15):
    """Voice loudness 0-1 per video frame (lead = when the line starts in the scene), for lip-sync."""
    import numpy as np

    x, sr = load_mono(path)
    hop = sr / fps
    n = int(len(x) / hop)
    if n == 0:
        return []
    env = np.array([np.sqrt(np.mean(x[int(i * hop) : int((i + 1) * hop)] ** 2)) for i in range(n)])
    env = np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1)
    return [0.0] * int(round(lead * fps)) + [round(float(v), 3) for v in env]


def cmd_voice(a):
    path, pj, W, H, fps = load_project(a.project)
    base = path.parent
    vcfg = pj.get("voice") or {}
    engine = pick_engine(a.engine or vcfg.get("engine", "auto"))
    voice = a.voice or vcfg.get("voice")
    (base / "vo").mkdir(exist_ok=True)
    made = 0
    if pj.get("voiceover"):
        made = split_voiceover(base, pj)
        engine = "voiceover file"
        print(f"Cut {pj['voiceover']} into {made} line(s) at its pauses: listen to vo/ to check the cuts")
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
            s["duration"] = round(max(float(s.get("min_duration", 2.0)), dur + 0.3), 3)
        else:
            s.pop("audio_duration", None)
            s["duration"] = round(scene_duration({**s, "duration": None}), 3)
    if engine != "voiceover file":
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
    if not music or music == "bed":
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
def scene_page(browser, W, H, scale=1):
    """A browser page where the kit (and three.js for K3 scenes) loads before each scene's own script,
    so scenes can use K, ART and K3 at the top level as well as inside render()."""
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=scale)
    for f in ("kit.js", "host.js", "art.js", "icons.js", "collage.js"):
        page.add_init_script(path=str(KIT / f))
    src = (KIT / "vendor" / "three.cjs").read_text(encoding="utf-8")
    page.add_init_script(
        f"(function(){{var module={{exports:{{}}}},exports=module.exports;\n{src}\nwindow.THREE=module.exports;}})();"
    )
    page.add_init_script(path=str(KIT / "three3d.js"))
    return page


def open_scene(page, base, scene, W, H, beat_info=None, fps=30, look=None, caps=None):
    page.goto((base / scene["html"]).resolve().as_uri())
    page.add_style_tag(path=str(KIT / "kit.css"))
    looks = (KIT / "looks.css").read_text(encoding="utf-8").replace('url("fonts/', f'url("{(KIT / "fonts").as_uri()}/')
    page.add_style_tag(content=looks)
    if look and not page.evaluate("document.body.dataset.look"):
        page.evaluate("(l) => { document.body.dataset.look = l; }", look)
    page.evaluate("(c) => { window.CAPS = c; window.__capGroups = null; }", caps)
    amp = amp_envelope(base / scene["audio"], fps) if scene.get("audio") else None
    page.evaluate(f"(a) => {{ window.AMP = a; window.AMP_FPS = {fps}; }}", amp)
    page.evaluate(f"document.body.classList.add('{'v' if H > W else 'h'}')")
    page.evaluate(
        "(b) => { window.BEATS = b.beats; window.DOWNBEATS = b.downbeats; window.DROPS = b.drops; }",
        beat_info or {"beats": [], "downbeats": [], "drops": []},
    )
    # scenes may load the kit themselves; if render is defined inline it runs after the kit is present
    page.evaluate("document.fonts.ready")
    # fonts fail silently (the video ships in a fallback face): load every face in use and check
    missing = page.evaluate(
        """async () => {
          const fams = new Set();
          for (const n of document.querySelectorAll('body *')) {
            const f = getComputedStyle(n).fontFamily.split(',')[0].replace(/["']/g, '').trim();
            if (f) fams.add(f);
          }
          const bad = [];
          for (const f of fams) {
            const decl = [...document.fonts].some((ff) => ff.family.replace(/["']/g, '') === f);
            if (!decl) continue;
            try { await document.fonts.load(`40px "${f}"`); } catch (e) {}
            if (!document.fonts.check(`40px "${f}"`)) bad.push(f);
          }
          return bad;
        }"""
    )
    if missing:
        print(f"  warning: {scene['id']}: font(s) didn't load: {', '.join(missing)}")
    if not page.evaluate("typeof window.render === 'function'"):
        die(f"{scene['html']} doesn't define window.render = (t, d) => {{...}}")


def draw(page, t, d):
    # waits for any K.clip video to land on its frame; K.__post adds grain/vignette for the look
    page.evaluate(
        f"(async () => {{ window.__pending = []; window.render({t:.5f}, {d:.5f});"
        f" if (window.K && K.__post) {{ K.__post({t:.5f}); K.__captions({t:.5f}); }}"
        " if (window.__pending.length) await Promise.all(window.__pending); })()"
    )


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
        page = scene_page(browser, W, H, tw / W)
        est = [scene_duration(x) for x in pj["scenes"]]
        per = scene_beats(pj, song_beats(base, pj), est)
        caps = scene_captions(pj, est) if in_scene_captions(pj) else {}
        for s, bi in zip(pj["scenes"], per):
            d = scene_duration(s)
            open_scene(page, base, s, W, H, bi, fps, pj.get("look"), caps.get(s["id"]))
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


def render_scene(page, base, s, W, H, fps, dst, preview, beat_info=None, look=None, caps=None):
    d = scene_duration(s)
    n = max(1, round(d * fps))
    open_scene(page, base, s, W, H, beat_info, fps, look, caps)
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
            "20" if preview else "18",
            # grain and fine texture can balloon the file: cap it near what social apps re-encode to
            "-maxrate",
            "6M" if preview else ("16M" if max(W, H) > 2000 else "10M"),
            "-bufsize",
            "20M",
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
        # moments the kit animated (pops, reveals, drawn lines) for "sfx": true
        s["_sfx"] = [e for e in (page.evaluate("Object.values(window.__sfx || {})") or []) if 0 <= e["t"] < d]
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode:
        die(f"Encoding scene {s['id']} failed.")
    tmp.replace(dst)
    return n / fps


def sfx_events(pj, durs):
    """Where sound effects go: a whoosh on every scene change, a pop or swish on what the kit
    animated, thinned to about one a second (scene changes and pops win)."""
    from sfx import thin

    ev, t = [], 0.0
    for i, (s, d) in enumerate(zip(pj["scenes"], durs)):
        if i:
            ev.append({"t": t, "kind": "whoosh", "strength": 1.0})
        for e in s.get("_sfx") or []:
            ev.append({"t": round(t + e["t"], 3), "kind": e["kind"], "strength": 0.8 if e["kind"] == "pop" else 0.5})
        t += d
    return thin(ev, per_sec=float(pj.get("sfx_per_sec", 0.9)))


def sfx_track(base, pj, durs, total, dst):
    if not pj.get("sfx"):
        return None
    from sfx import build_sfx_track

    ev = sfx_events(pj, durs)
    if not ev:
        return None
    sounds = base / pj["sfx_sounds"] if pj.get("sfx_sounds") else None
    build_sfx_track([(e["kind"], e["t"]) for e in ev], total, dst, float(pj.get("sfx_volume", 0.22)), sounds)
    print(f"  {len(ev)} sound effects")
    return dst


def build_audio(base, pj, durs, total, out_wav):
    """Voice lines placed at their scenes' starts, music under them ducking while someone talks."""
    inputs, chains, labels = [], [], []
    n_in = 0  # ffmpeg input index (inputs holds the command-line tokens)
    t = 0.0
    for s, d in zip(pj["scenes"], durs):
        if s.get("audio"):
            k = n_in
            n_in += 1
            inputs += ["-i", str(base / s["audio"])]
            ms = int(round((t + 0.15) * 1000))
            chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
            labels.append(f"[v{k}]")
        t += d
    sfx_wav = sfx_track(base, pj, durs, total, out_wav.with_name("sfx.wav"))
    music = pj.get("music")
    if music == "bed":  # a quiet documentary bed made on the spot (no licensing)
        from sfx import music_bed

        music = str(music_bed(total, out_wav.with_name("bed.wav"), bpm=float(pj.get("bed_bpm", 84))))
    has_voice = bool(labels)
    if not has_voice and not music and not sfx_wav:
        return False
    if has_voice:
        chains.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{total:.3f}[voice]"
        )
    if music:
        k = n_in
        n_in += 1
        inputs += ["-stream_loop", "-1", "-i", str((base / music).resolve())]
        vol = float(pj.get("music_volume", 0.18 if has_voice else 0.8))
        chains.append(
            f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},atrim=0:{total:.3f},"
            f"afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mus]"
        )
        if has_voice:
            chains.append("[voice]asplit[vo][key]")
            chains.append("[mus][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[duck]")
            chains.append("[vo][duck]amix=inputs=2:duration=first:normalize=0[base]")
        else:
            chains.append("[mus]anull[base]")
    elif has_voice:
        chains.append("[voice]anull[base]")
    if sfx_wav:  # effects sit on top: they never duck the music or get ducked themselves
        k = n_in
        inputs += ["-i", str(sfx_wav)]
        fx = f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{total:.3f}"
        if has_voice or music:
            chains.append(f"{fx}[fx]")
            chains.append("[base][fx]amix=inputs=2:duration=first:normalize=0[mix]")
        else:
            chains.append(f"{fx}[mix]")
    else:
        chains.append("[base]anull[mix]")
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


def in_scene_captions(pj):
    """With a look, captions are drawn in the scene in its own type; without one, burned in after."""
    return bool(pj.get("captions")) and bool(pj.get("look")) and pj.get("caption_mode") != "burn"


def scene_captions(pj, durs):
    """Each scene's caption words, timed from the scene's start."""
    tr = caption_transcript(pj, durs)
    out, t = {}, 0.0
    starts = []
    for d in durs:
        starts.append(t)
        t += d
    for s, a, d in zip(pj["scenes"], starts, durs):
        out[s["id"]] = [
            {"w": w["w"], "start": round(w["start"] - a, 3), "end": round(w["end"] - a, 3)}
            for seg in tr["segments"]
            for w in seg["words"]
            if a <= w["start"] < a + d
        ]
    return out


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
        page = scene_page(browser, W, H)
        est = [round(scene_duration(x) * fps) / fps for x in scenes]
        per = scene_beats(pj, song_beats(base, pj), est)
        caps = scene_captions(pj, est) if in_scene_captions(pj) else {}
        for s, bi in zip(scenes, per):
            dst = work / f"{s['id']}{'_p' if a.preview else ''}.mp4"
            if a.only and s["id"] != a.only and dst.exists():
                durs.append(round(scene_duration(s) * fps) / fps)
            else:
                print(f"  drawing {s['id']} ({scene_duration(s):.1f}s)")
                durs.append(
                    render_scene(page, base, s, W, H, fps, dst, a.preview, bi, pj.get("look"), caps.get(s["id"]))
                )
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
    if pj.get("captions") and not in_scene_captions(pj) and any(s.get("narration") for s in scenes):
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
    v.add_argument("--engine", choices=["auto", "kokoro", "say", "sapi", "espeak", "piper", "elevenlabs", "none"])
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
