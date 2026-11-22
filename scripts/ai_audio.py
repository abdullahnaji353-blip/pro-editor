"""Realistic sound effects and music from ElevenLabs, saved where pro-editor uses them.

Usage:
  python ai_audio.py sfx "basketball bouncing on a driveway" --seconds 0.6 --out sounds/bounce.mp3
  python ai_audio.py pack sounds/ [--for story|montage|create|all] [--force]
  python ai_audio.py music "chill lo-fi beat, warm keys, 85 bpm" --seconds 40 --out song.mp3

Needs ELEVENLABS_API_KEY (elevenlabs.io > Profile > API keys). Uses your ElevenLabs credits:
each sound or song is one paid generation, so nothing here retries on its own.

Without a key, make the same sounds with the ElevenLabs connector in Claude (or on elevenlabs.io)
and drop the files into the sounds folder with the names below: the result is the same.

How the files get used: name each sound after its kind (bounce.mp3, swish.mp3, whoosh.wav,
pop.mp3 ...) in one folder, then point pro-editor at it:
  /create, /story    "sfx_sounds": "sounds" in project.json
  sfx.py add / clip  --sounds sounds
Your file replaces the built-in synthesized sound of the same name, and its loudest moment still
lands on the frame.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io/v1"

# kind -> (prompt, seconds). The names match the sound kinds the renderer asks for.
PACKS = {
    "story": {
        "bounce": ("a single basketball bounce on an outdoor concrete driveway, close, dry", 0.6),
        "swish": ("a basketball swishing cleanly through a chain net, no crowd", 0.9),
        "whoosh": ("a quick cinematic whoosh transition, short and clean", 0.7),
        "pop": ("a soft cartoon pop, bubbly and short", 0.4),
        "footsteps": ("sneaker footsteps on a sidewalk, three steps, close", 1.2),
        "door": ("a front door opening with muffled house party music spilling out", 1.6),
        "crowd": ("teenagers cheering at a house party, muffled through a wall", 3.0),
        "ding": ("a bright bell ding notification, single hit", 0.8),
    },
    "montage": {
        "whoosh": ("a fast cinematic whoosh for a video transition", 0.7),
        "impact": ("a deep cinematic boom impact with a crack, for a beat drop", 1.4),
        "riser": ("a two second tension riser that builds into a drop", 2.2),
        "swish": ("a short airy swish", 0.4),
        "click": ("a crisp camera shutter click", 0.3),
        "glitch": ("a short digital glitch stutter sound effect", 0.5),
    },
    "create": {
        "paper": ("a sheet of paper sliding onto a wooden desk", 0.5),
        "stamp": ("a rubber stamp hitting paper on a desk, one hit", 0.5),
        "tape": ("a strip of tape being pressed down on paper", 0.5),
        "type": ("four typewriter key strikes", 0.6),
        "marker": ("a marker scribbling a circle on paper", 0.7),
        "pop": ("a soft UI pop", 0.3),
        "whoosh": ("a quick clean whoosh transition", 0.6),
        "tick": ("a soft clock tick", 0.3),
    },
}


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        sys.exit(
            "Set ELEVENLABS_API_KEY to generate sounds here.\n"
            "Or make them with the ElevenLabs connector in Claude and save them in your sounds folder\n"
            "named after their kind (bounce.mp3, swish.mp3, whoosh.mp3 ...)."
        )
    return k


def post(path, body, out, timeout=180):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs said {e.code}: {e.read()[:300].decode(errors='replace')}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


def sfx(prompt, seconds, out, influence=0.45):
    body = {"text": prompt, "prompt_influence": influence}
    if seconds:
        body["duration_seconds"] = max(0.5, min(22.0, float(seconds)))
    return post("/sound-generation", body, out)


def music(prompt, seconds, out):
    return post("/music", {"prompt": prompt, "music_length_ms": int(max(10, min(300, seconds)) * 1000)}, out, 600)


def pack_items(which):
    if which == "all":
        merged = {}
        for p in PACKS.values():
            merged.update(p)
        return merged
    return PACKS[which]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sfx")
    p.add_argument("prompt")
    p.add_argument("--seconds", type=float)
    p.add_argument("--out", required=True)
    p = sub.add_parser("pack")
    p.add_argument("dir")
    p.add_argument("--for", dest="which", default="story", choices=[*PACKS, "all"])
    p.add_argument("--force", action="store_true", help="remake sounds that already exist")
    p.add_argument("--list", action="store_true", help="only show what would be made")
    p = sub.add_parser("music")
    p.add_argument("prompt")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "sfx":
        print(f"-> {sfx(a.prompt, a.seconds, a.out)}")
    elif a.cmd == "music":
        print(
            f"-> {music(a.prompt, a.seconds, a.out)}  (check the licence terms of your ElevenLabs plan before posting)"
        )
    else:
        d = Path(a.dir)
        items = pack_items(a.which)
        todo = {k: v for k, v in items.items() if a.force or not any(d.glob(f"{k}.*"))}
        for k, (prompt, _sec) in items.items():
            print(f"  {k + '.mp3':<16} {'make' if k in todo else 'have'}  {prompt}")
        if a.list or not todo:
            print("Nothing to make." if not todo else f"{len(todo)} sound(s) would be made.")
            return
        for k, (prompt, sec) in todo.items():
            sfx(prompt, sec, d / f"{k}.mp3")
            print(f"  made {k}.mp3")
        print(f'Done. Use it with "sfx_sounds": "{d}" in project.json, or --sounds {d}.')


if __name__ == "__main__":
    main()
