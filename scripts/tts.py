"""Text to speech for any edit: a voiceover file, or voice lines laid onto a video.

Usage:
  python tts.py say "text" [--file script.txt] [--engine auto] [--voice NAME] [--speed 1.0] --out voice.wav
  python tts.py voices [--engine kokoro|say|sapi|espeak]
  python tts.py onto VIDEO (--text "..." [--at 2.0] | --file script.txt | --lines lines.json)
                [--engine auto] [--voice NAME] [--speed 1.0] [--duck 0.25] [--captions] --out OUT.mp4

Engines, best first (same as /create):
  elevenlabs  ELEVENLABS_API_KEY set; --voice is a voice id. Or make the audio with the ElevenLabs
              connector and use `onto --audio file.mp3` instead.
  kokoro      free, natural, runs locally (pip install kokoro-onnx soundfile; model downloads once).
              Voices: am_michael, am_adam, af_heart, af_bella, bm_george, bf_emma ...
  say         macOS voices (say -v ?)      sapi  Windows voices      espeak / piper  Linux
--speed 1.1 talks 10% faster (pitch kept).

onto: lines.json is [{"at": 1.5, "text": "first line"}, {"at": 6.0, "text": "..."}]. Each line is
spoken at its time, the video's own sound ducks under the voice, the result ends at -14 LUFS, and
--captions burns word-by-word captions for the lines.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import die, need, probe  # noqa: E402
from create import has_kokoro, kokoro_dir, pick_engine, speak  # noqa: E402

KOKORO_VOICES = ["am_michael", "am_adam", "am_eric", "am_liam", "af_heart", "af_bella", "af_nicole", "af_sarah",
                 "bm_george", "bm_lewis", "bf_emma", "bf_isabella"]  # fmt: skip


def chunks(text, limit=380):
    """Split long text at sentence ends so every engine gets a comfortable length."""
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text.strip()):
        if cur and len(cur) + len(s) + 1 > limit:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts


def duration(path):
    return probe(path)["duration"]


def synth(text, engine, voice, speed, dst):
    """Speak text (any length) into a 48 kHz mono wav. Returns the engine used."""
    engine = pick_engine(engine)
    if engine == "none":
        die("No voice engine found. Install Kokoro (pip install kokoro-onnx soundfile) or pass --engine.")
    with tempfile.TemporaryDirectory() as td:
        pieces = []
        for k, part in enumerate(chunks(text)):
            f = Path(td) / f"p{k}.wav"
            if not speak(engine, part, voice, f):
                die(f"The {engine} voice failed on: {part[:60]}...")
            pieces.append(f)
        lst = Path(td) / "list.txt"
        gap = Path(td) / "gap.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.28",
                        str(gap)], check=True)  # fmt: skip
        lst.write_text("".join(f"file '{p}'\nfile '{gap}'\n" for p in pieces[:-1]) + f"file '{pieces[-1]}'\n")
        tempo = f",atempo={speed:.3f}" if abs(speed - 1) > 1e-3 else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-af", f"aresample=48000{tempo}", "-ac", "1", str(dst)], check=True)  # fmt: skip
    return engine


def voices(engine):
    engine = pick_engine(engine)
    if engine == "kokoro":
        if not has_kokoro():
            die("Kokoro isn't installed: pip install kokoro-onnx soundfile")
        print("Kokoro voices (a = US, b = British; f = female, m = male):")
        print("  " + ", ".join(KOKORO_VOICES))
        print(f"  model folder: {kokoro_dir()}")
    elif engine == "say":
        print(subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout)
    elif engine == "sapi":
        ps = ("Add-Type -AssemblyName System.Speech;(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
              ".GetInstalledVoices()|%{$_.VoiceInfo.Name}")  # fmt: skip
        print(subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout)
    elif engine == "espeak":
        print(subprocess.run(["espeak-ng", "--voices"], capture_output=True, text=True).stdout)
    else:
        print(f"{engine}: pass --voice with the voice name or id the service gives you.")


def lines_from(a):
    if a.lines:
        lines = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    elif a.file:
        lines = [{"at": a.at, "text": Path(a.file).read_text(encoding="utf-8")}]
    elif a.text:
        lines = [{"at": a.at, "text": a.text}]
    else:
        lines = []
    for ln in lines:
        if "at" not in ln or "text" not in ln:
            die('Every line needs "at" (seconds) and "text".')
    return sorted(lines, key=lambda ln: ln["at"])


def transcript(lines_with_dur):
    """Even word timing inside each spoken line, for captions.py."""
    segs = []
    for i, (at, text, d) in enumerate(lines_with_dur, 1):
        words = text.split()
        step = d / max(1, len(words))
        ws = [{"w": w, "start": round(at + k * step, 3), "end": round(at + (k + 1) * step - 0.02, 3), "p": 1.0}
              for k, w in enumerate(words)]  # fmt: skip
        segs.append({"id": i, "start": at, "end": round(at + d, 3), "text": text, "words": ws})
    return {"language": "en", "segments": segs}


def onto(a):
    need("ffmpeg")
    video = Path(a.video)
    info = probe(video)
    D = info["duration"]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        placed = []
        if a.audio:
            placed.append((a.at, Path(a.audio), None))
        else:
            lines = lines_from(a)
            if not lines:
                die("Give --text, --file, --lines or --audio.")
            for k, ln in enumerate(lines):
                f = td / f"l{k}.wav"
                synth(ln["text"], a.engine, a.voice, a.speed, f)
                placed.append((float(ln["at"]), f, ln["text"]))
        for (at, f, _), nxt in zip(placed, placed[1:] + [(None, None, None)]):
            end = at + duration(f)
            if nxt[0] is not None and end > nxt[0] + 0.05:
                print(f"  warning: the line at {at:.1f}s runs to {end:.1f}s, over the next one at {nxt[0]:.1f}s")
            if end > D + 0.05:
                print(f"  warning: the line at {at:.1f}s ends at {end:.1f}s, after the video ends ({D:.1f}s)")
        inputs, chains, labels = ["-i", str(video)], [], []
        for k, (at, f, _) in enumerate(placed, 1):
            inputs += ["-i", str(f)]
            ms = int(at * 1000)
            chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
            labels.append(f"[v{k}]")
        n = len(labels)
        chains.append(f"{''.join(labels)}amix=inputs={n}:duration=longest:normalize=0,apad,atrim=0:{D:.3f}[voice]")
        if info["has_audio"]:
            chains.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={a.duck_level:.3f}[bed]")
            chains.append("[voice]asplit[vo][key]")
            ratio = 1 / max(a.duck, 0.05)
            chains.append(f"[bed][key]sidechaincompress=threshold=0.02:ratio={ratio:.1f}:attack=15:release=350[ducked]")
            chains.append("[vo][ducked]amix=inputs=2:duration=first:normalize=0[mix]")
        else:
            chains.append("[voice]anull[mix]")
        chains.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.79:level=disabled[out]")
        mixed = td / "mixed.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains), "-map", "0:v",
                        "-map", "[out]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(mixed)],
                       check=True)  # fmt: skip
        out = Path(a.out)
        if a.captions and any(t for *_, t in placed):
            tr = td / "tr.json"
            tr.write_text(json.dumps(transcript([(at, t, duration(f)) for at, f, t in placed if t])))
            subprocess.run([sys.executable, str(HERE / "captions.py"), str(mixed), str(tr), "--out", str(out)],
                           check=True)  # fmt: skip
        else:
            out.write_bytes(mixed.read_bytes())
    print(f"{len(placed)} voice line(s) -> {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    eng = ["auto", "kokoro", "elevenlabs", "say", "sapi", "espeak", "piper"]
    p = sub.add_parser("say")
    p.add_argument("text", nargs="?")
    p.add_argument("--file")
    p.add_argument("--engine", default="auto", choices=eng)
    p.add_argument("--voice")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--out", required=True)
    p = sub.add_parser("voices")
    p.add_argument("--engine", default="auto", choices=eng)
    p = sub.add_parser("onto")
    p.add_argument("video")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--lines", help='JSON list of {"at": seconds, "text": "..."}')
    p.add_argument("--audio", help="an existing voice recording to lay on instead (ElevenLabs, your own)")
    p.add_argument("--at", type=float, default=0.3, help="when the line starts, for --text/--file/--audio")
    p.add_argument("--engine", default="auto", choices=eng)
    p.add_argument("--voice")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--duck", type=float, default=0.25, help="how far the video's sound dips under the voice")
    p.add_argument("--duck-level", type=float, default=1.0, help="the video's sound level overall")
    p.add_argument("--captions", action="store_true", help="burn word-by-word captions for the lines")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "say":
        text = Path(a.file).read_text(encoding="utf-8") if a.file else a.text
        if not text:
            die("Give the text, or --file.")
        need("ffmpeg")
        used = synth(text, a.engine, a.voice, a.speed, Path(a.out))
        print(f"{used}: {duration(a.out):.1f}s -> {a.out}")
    elif a.cmd == "voices":
        voices(a.engine)
    else:
        onto(a)


if __name__ == "__main__":
    main()
