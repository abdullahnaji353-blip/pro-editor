"""/talk: hear everything in a video (or a voice note) and turn what was said into edit decisions.

Commands
  hear VIDEO [--transcript T] [--model auto] [--language en] [--hotwords "Naji, Rocket League"]
             [--multilingual] [--audio-track N] [--no-sounds] [--pre 12] [--export-dir clips] [--out-dir talk]
      Listens to the whole thing and writes:
        <name>.talk.md      what it heard, readable: spoken instructions, funny/loud moments, transcript
        <name>.talk.json    the same as data (commands, sound events, loud moments, edit suggestions)
        <name>.highlights.json  moments ready for build_montage.py --highlights
                            ("clip that" callouts, laughter, shouting, cheering)
      It understands spoken instructions in the footage:
        "clip that" / "clip it" / "that's a clip"   -> the moment just before becomes a highlight
        "Claude, zoom in here" / "editor, cut this"  -> an edit instruction at that time
        "cut that" / "scratch that"                  -> remove the sentence before
        "let me redo that" / "one more time"         -> retake: drop the flubbed take
      and the spoken commands themselves are listed for removal, so they don't end up in the video.
  prompt VOICE_NOTE [--model auto] [--language en] [--out prompt.txt]
      Transcribes a voice message (any audio or video file) so it can be used as the instructions.

Sound events use Google's YAMNet sound classifier through MediaPipe (521 everyday sounds; the 4 MB
model downloads once). Without MediaPipe it still hears speech and loudness.
"""

import argparse
import re
import subprocess
from pathlib import Path

import numpy as np

from common import die, get_model, load_json, need, probe, quiet_native_logs, save_json, smooth

YAMNET_URL = "https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/latest/yamnet.tflite"
SR = 16000

# group: (YAMNet labels, score that always counts, lower score that counts when it's a top-3 sound)
GROUPS = {
    "laughter": ({"Laughter", "Giggle", "Snicker", "Belly laugh", "Chuckle, chortle", "Baby laughter"}, 0.22, 0.1),
    "shouting": ({"Shout", "Yell", "Screaming", "Battle cry", "Whoop", "Bellow", "Children shouting"}, 0.28, 0.12),
    "cheering": ({"Cheering", "Applause", "Clapping", "Crowd"}, 0.3, 0.15),
    "music": (
        {
            "Music",
            "Singing",
            "Song",
            "Rapping",
            "Choir",
            "Pop music",
            "Hip hop music",
            "Electronic music",
            "Rock music",
            "Techno",
            "Dubstep",
            "Drum and bass",
            "House music",
            "Orchestra",
            "Ambient music",
        },
        0.3,
        0.2,
    ),
    "gunfire": ({"Gunshot, gunfire", "Machine gun", "Fusillade", "Artillery fire", "Cap gun"}, 0.25, 0.12),
    "explosion": ({"Explosion", "Boom", "Eruption", "Fireworks", "Firecracker"}, 0.25, 0.12),
    "engine": (
        {"Vehicle", "Car", "Engine", "Race car, auto racing", "Accelerating, revving, vroom", "Motorcycle"},
        0.35,
        0.2,
    ),
    "crying": ({"Crying, sobbing", "Baby cry, infant cry", "Whimper"}, 0.25, 0.1),
    "gasp": ({"Gasp"}, 0.3, 0.15),
    "animal": ({"Dog", "Bark", "Cat", "Meow", "Bird"}, 0.4, 0.25),
}
EVENT_WORDS = {
    "laughter": "laughing",
    "shouting": "shouting/screaming",
    "cheering": "cheering/applause",
    "music": "music",
    "gunfire": "gunfire",
    "explosion": "explosion",
    "engine": "engine/car sounds",
    "crying": "crying",
    "gasp": "gasp",
    "animal": "animal sounds",
}

# spoken instructions --------------------------------------------------------------------------------
WAKE_STRONG = {"claude", "claud", "klaude", "claudes", "editor", "كلود"}
WAKE_WEAK = {"cloud", "clod", "clawed", "clode", "clyde", "claw"}  # common mishearings: need a verb right after
ACTIONS = [  # (action, phrases) checked in order; phrases are normalised word sequences
    (
        "slowmo",
        [
            "slow mo",
            "slowmo",
            "slow motion",
            "slow it down",
            "slow down",
            "slow that",
            "slow this",
            "سلو موشن",
            "سلو",
            "بطيء",
            "بطء",
        ],
    ),
    (
        "speedup",
        [
            "speed up",
            "speed it up",
            "speed this up",
            "speed that up",
            "fast forward",
            "time lapse",
            "timelapse",
            "سرع",
            "اسرع",
            "تسريع",
        ],
    ),
    ("zoom", ["zoom", "punch in", "push in", "closer", "close up", "closeup", "زوم", "قرب", "كبر"]),
    ("freeze", ["freeze", "pause on", "hold on that frame"]),
    (
        "remove",
        [
            "cut",
            "delete",
            "remove",
            "get rid of",
            "edit out",
            "take out",
            "dont use",
            "do not use",
            "skip",
            "قص",
            "احذف",
            "شيل",
            "امسح",
            "لا تحط",
        ],
    ),
    (
        "keep",
        [
            "keep",
            "use this",
            "use that",
            "highlight",
            "best part",
            "remember",
            "mark",
            "marker",
            "bookmark",
            "important",
            "خلي هذا",
            "مهم",
            "ثبت",
            "حط علامة",
        ],
    ),
    ("music", ["music", "song", "beat", "drop", "track", "موسيقى", "اغنية", "الاغنية", "اغنيه", "بيت"]),
    ("sfx", ["sound effect", "sfx", "whoosh", "boom", "ding", "airhorn", "vine boom"]),
    ("censor", ["bleep", "censor", "mute", "blur"]),
    (
        "text",
        [
            "text",
            "caption",
            "title",
            "subtitle",
            "write",
            "words on screen",
            "on screen",
            "اكتب",
            "نص",
            "عنوان",
            "كابشن",
        ],
    ),
    ("thumbnail", ["thumbnail", "ثمبنيل", "الصورة المصغرة"]),
    (
        "start",
        [
            "start here",
            "start from",
            "begin here",
            "intro",
            "start the video",
            "ابدا من هنا",
            "البداية من هنا",
            "البداية",
        ],
    ),
    ("end", ["end here", "stop here", "end the video", "outro", "the end", "النهاية", "خلاص هنا", "وقف هنا"]),
    ("avatar", ["avatar", "robot", "hologram", "character", "mascot"]),
    ("color", ["color", "colour", "brighter", "darker", "grade", "filter", "look"]),
    ("transition", ["transition", "fade", "swipe", "whip"]),
]
CLIP_NEXT = {"that", "it", "this", "dat", "thats", "dis"}
REMOVE_PREV = [
    "cut that",
    "cut that out",
    "edit that out",
    "delete that",
    "scratch that",
    "dont use that",
    "take that out",
    "strike that",
    "cut this out",
]
RETAKE = [
    "let me redo that",
    "let me do that again",
    "let me start over",
    "lets start over",
    "start over",
    "one more time",
    "take two",
    "let me try that again",
    "lets try that again",
    "again from the top",
    "let me say that again",
    "redo that",
    "from the top",
]


def norm(w):
    w = w.lower().replace("’", "'")
    w = re.sub("[^a-z0-9'\u0621-\u063a\u0641-\u064a\u0660-\u0669\u066e-\u06d3\u06f0-\u06f9]", "", w)
    return w.replace("'", "")


def fmt(t):
    m, s = divmod(max(t, 0), 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:04.1f}" if h else f"{m:02d}:{s:04.1f}"


# ------------------------------------------------------------------ audio
def load_audio(path, track=0):
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            f"0:a:{track}",
            "-ac",
            "1",
            "-ar",
            str(SR),
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
    )
    x = np.frombuffer(res.stdout, np.float32)
    return x.copy()


def loudness_curve(x, hop=0.1):
    n = int(SR * hop)
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    rms = np.sqrt(np.mean(x[: k * n].reshape(k, n) ** 2, axis=1) + 1e-10)
    return 20 * np.log10(rms)


def loud_moments(db, hop=0.1, top=12, min_gap=5.0):
    if len(db) < 20:
        return []
    sm = smooth(db, int(1.0 / hop))
    base = np.median(sm)
    thr = max(np.percentile(sm, 92), base + 8)
    order = np.argsort(-sm)
    picks = []
    for i in order:
        if sm[i] < thr or len(picks) >= top:
            break
        t = i * hop
        if all(abs(t - p["t"]) >= min_gap for p in picks):
            picks.append({"t": round(t, 2), "db_above_typical": round(float(sm[i] - base), 1)})
    return sorted(picks, key=lambda p: p["t"])


def sound_events(x, chunk_s=30.0):
    with quiet_native_logs():
        return _sound_events(x, chunk_s)


def _sound_events(x, chunk_s=30.0):
    """YAMNet through MediaPipe -> per-window scores for the groups above, merged into events.
    Runs twice, half a window apart, so short sounds aren't split across two windows."""
    try:
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import audio
        from mediapipe.tasks.python.components.containers import audio_data as ad
    except ImportError:
        return None, "Sound events skipped: MediaPipe isn't installed (python -m pip install mediapipe)."
    model = get_model("yamnet.tflite", YAMNET_URL, "PRO_EDITOR_YAMNET_MODEL", "sound-recognition")
    opts = audio.AudioClassifierOptions(
        base_options=mpt.BaseOptions(model_asset_path=model), max_results=-1, running_mode=audio.RunningMode.AUDIO_CLIPS
    )
    clf = audio.AudioClassifier.create_from_options(opts)
    step = 0.975
    windows = []  # (t, {group: counted score})
    try:
        n = int(chunk_s * SR)
        for off in (0.0, step / 2):
            o = int(off * SR)
            for c0 in range(o, len(x), n):
                part = x[c0 : c0 + n]
                if len(part) < SR // 2:
                    break
                for r in clf.classify(ad.AudioData.create_from_array(part.astype(np.float32), SR)):
                    cats = r.classifications[0].categories
                    scores = {c.category_name: c.score for c in cats}
                    top3 = {c.category_name for c in sorted(cats, key=lambda c: -c.score)[:3]}
                    g = {}
                    for name, (labels, hi, lo) in GROUPS.items():
                        best = max(((scores.get(lbl, 0.0), lbl) for lbl in labels), default=(0.0, ""))
                        sc, lbl = best
                        g[name] = sc if (sc >= hi or (sc >= lo and lbl in top3)) else 0.0
                    windows.append((c0 / SR + r.timestamp_ms / 1000.0, g))
                done = (0.5 if off else 0.0) + 0.5 * min(c0 + n, len(x)) / max(len(x), 1)
                print(f"  listening for sounds {100 * done:3.0f}%", end="\r")
    finally:
        clf.close()
    print("  listening for sounds 100%")
    windows.sort(key=lambda w: w[0])
    events = []
    for name in GROUPS:
        cur = None
        for t, g in windows:
            sc = g[name]
            if sc <= 0:
                continue
            if cur and t - cur["end"] <= step * 1.2:
                cur["end"] = max(cur["end"], t + step)
                cur["peak"] = max(cur["peak"], sc)
            else:
                if cur:
                    events.append(cur)
                cur = {"type": name, "start": t, "end": t + step, "peak": sc}
        if cur:
            events.append(cur)
    for e in events:
        e["start"], e["end"], e["peak"] = round(e["start"], 2), round(e["end"], 2), round(float(e["peak"]), 2)
    events.sort(key=lambda e: e["start"])
    return events, None


# ------------------------------------------------------------------ spoken instructions
def flat_words(tr):
    out = []
    for s in tr["segments"]:
        ws = s.get("words") or []
        if not ws:  # no word timings: spread the line evenly
            toks = s["text"].split()
            dur = (s["end"] - s["start"]) / max(len(toks), 1)
            ws = [
                {"w": w, "start": s["start"] + i * dur, "end": s["start"] + (i + 1) * dur} for i, w in enumerate(toks)
            ]
        for w in ws:
            n = norm(w["w"])
            if n:
                out.append({"n": n, "raw": w["w"], "start": float(w["start"]), "end": float(w["end"]), "seg": s["id"]})
    return out


def _phrase_ends(words, j):
    """True when the phrase stops at word j: punctuation, a pause, a new line, or a tag like "please"."""
    if j + 1 >= len(words) or re.search(r"[.!?,]$", words[j]["raw"]):
        return True
    nxt = words[j + 1]
    return (
        nxt["seg"] != words[j]["seg"]
        or nxt["start"] - words[j]["end"] > 0.35
        or nxt["n"] in ("please", "bro", "now", "rn", "dude", "yo", "clip", "bruh", "omg")
    )


def match_at(words, i, phrase):
    toks = phrase.split()
    if i + len(toks) > len(words):
        return False
    return all(words[i + k]["n"] == t for k, t in enumerate(toks))


def classify(instr):
    text = " " + " ".join(instr) + " "
    for action, phrases in ACTIONS:
        for ph in phrases:
            if f" {ph} " in text or (" " not in ph and f" {ph}" in text):
                return action
    return "instruction"


def seg_bounds(tr, seg_id):
    for s in tr["segments"]:
        if s["id"] == seg_id:
            return s["start"], s["end"]
    return None


def prev_seg(tr, seg_id):
    ids = [s["id"] for s in tr["segments"]]
    k = ids.index(seg_id) if seg_id in ids else -1
    return tr["segments"][k - 1] if k > 0 else None


def next_seg(tr, seg_id):
    ids = [s["id"] for s in tr["segments"]]
    k = ids.index(seg_id) if seg_id in ids else -1
    return tr["segments"][k + 1] if 0 <= k < len(ids) - 1 else None


def find_commands(tr, pre=12.0, loud=None):
    cmds = _find_commands(tr, pre, loud)
    # a "cut that" right after another command means the line before that command
    cmd_lines = {}
    for c in cmds:
        for s in tr["segments"]:
            if s["start"] - 0.15 <= c["cmd"][0] and c["cmd"][1] <= s["end"] + 0.3:
                said = " ".join(norm(w) for w in s["text"].split())
                if len(said.split()) <= len(c["said"].split()) + 2:
                    cmd_lines[s["id"]] = s
    for c in cmds:
        if c["type"] in ("remove", "retake"):
            a0, a1 = c["applies_to"]
            hit = next(
                (s for s in cmd_lines.values() if abs(s["start"] - a0) < 0.05 and abs(s["end"] - a1) < 0.3), None
            )
            if hit:
                ps = prev_seg(tr, hit["id"])
                while ps is not None and ps["id"] in cmd_lines:
                    ps = prev_seg(tr, ps["id"])
                if ps is not None:
                    c["applies_to"] = [round(ps["start"], 2), round(ps["end"], 2)]
                    c["note"] += " (skipped the spoken command before it)"
    return cmds


def _find_commands(tr, pre=12.0, loud=None):
    words = flat_words(tr)
    cmds = []
    used = set()
    i = 0
    while i < len(words):
        w = words[i]
        # --- "clip that" callouts
        if (
            w["n"] == "clip"
            and i + 1 < len(words)
            and words[i + 1]["n"] in CLIP_NEXT
            and words[i + 1]["start"] - w["end"] < 0.8
            and _phrase_ends(words, i + 1)
        ):
            j = i + 1
            if j + 1 < len(words) and words[j + 1]["n"] in ("please", "bro", "now", "rn", "dude", "yo"):
                j += 1
            t = w["start"]
            if cmds and cmds[-1]["type"] == "clip" and t - cmds[-1]["t"] < 4.0:  # "clip that, clip that!"
                cmds[-1]["cmd"][1] = round(words[j]["end"] + 0.1, 2)
            else:
                cmds.append(_clip(words, i, j, t, pre, loud, "clip that"))
            used.update(range(i, j + 1))
            i = j + 1
            continue
        if w["n"] in ("thats", "that") and i + 2 < len(words):
            k = i + 1 + (1 if words[i + 1]["n"] in ("a", "the", "so") else 0)
            k2 = k + (1 if k < len(words) and words[k]["n"] == "is" else 0)
            if (
                k2 < len(words)
                and words[k2]["n"] == "clip"
                and (k2 + 1 >= len(words) or words[k2 + 1]["n"] not in ("art", "board", "studio"))
            ):
                cmds.append(_clip(words, i, k2, w["start"], pre, loud, "that's a clip"))
                used.update(range(i, k2 + 1))
                i = k2 + 1
                continue
        # --- wake word + instruction ("Claude, zoom in here")
        if w["n"] in WAKE_STRONG or w["n"] in WAKE_WEAK:
            j = i + 1
            if j < len(words) and words[j]["n"] in ("please", "can", "could", "you", "uh", "um"):
                j += 1
            instr_words = []
            k, last = j, j - 1
            while k < len(words) and len(instr_words) < 14 and words[k]["start"] - words[k - 1]["end"] < 1.2:
                instr_words.append(words[k]["n"])
                last = k
                if re.search(r"[.!?؟]$", words[k]["raw"]):
                    break
                k += 1
            action = classify(instr_words)
            comma = bool(re.search(r"[,:]$", w["raw"]))
            is_editor = w["n"] == "editor"
            ok = (w["n"] in WAKE_STRONG and not is_editor) or comma or action != "instruction"
            if is_editor and not (
                comma or action != "instruction" or (i and words[i - 1]["n"] in ("hey", "yo", "note"))
            ):
                ok = False
            if w["n"] in WAKE_WEAK and action == "instruction":
                ok = False
            if ok and instr_words:
                end_k = max(last, i)
                cmd_start = (
                    words[i - 1]["start"]
                    if i and words[i - 1]["n"] in ("hey", "yo", "ok", "okay", "note")
                    else w["start"]
                )
                cmds.append(_instruction(tr, words, i, end_k, cmd_start, action, instr_words))
                used.update(range(i, end_k + 1))
                i = end_k + 1
                continue
        # --- "cut that" / "scratch that" (no wake word)
        hit = next((ph for ph in REMOVE_PREV if match_at(words, i, ph)), None)
        if hit and not (set(range(i, i + len(hit.split()))) & used):
            k = i + len(hit.split()) - 1
            seg = seg_bounds(tr, w["seg"])
            short = seg and (seg[1] - seg[0]) < 4.0
            ps = prev_seg(tr, w["seg"])
            target = (ps["start"], ps["end"]) if ps and short else (max(0.0, w["start"] - 6.0), w["start"])
            cmds.append(
                {
                    "type": "remove",
                    "said": " ".join(x["raw"] for x in words[i : k + 1]),
                    "t": round(w["start"], 2),
                    "cmd": [round(words[i]["start"] - 0.05, 2), round(words[k]["end"] + 0.1, 2)],
                    "applies_to": [round(target[0], 2), round(target[1], 2)],
                    "confidence": "high" if short else "check",
                    "note": "cut the sentence before" + ("" if short else " (said mid-sentence: confirm)"),
                }
            )
            i = k + 1
            continue
        # --- retakes
        hit = next((ph for ph in RETAKE if match_at(words, i, ph)), None)
        if hit:
            k = i + len(hit.split()) - 1
            ps = prev_seg(tr, w["seg"])
            this = seg_bounds(tr, w["seg"])
            start = ps["start"] if ps and this and this[0] - ps["end"] < 4.0 else max(0.0, w["start"] - 5.0)
            if this and words[i]["start"] - this[0] > 1.5:  # the flub is earlier in this same line
                start = this[0]
            cmds.append(
                {
                    "type": "retake",
                    "said": " ".join(x["raw"] for x in words[i : k + 1]),
                    "t": round(w["start"], 2),
                    "cmd": [round(words[i]["start"] - 0.05, 2), round(words[k]["end"] + 0.1, 2)],
                    "applies_to": [round(start, 2), round(words[k]["end"] + 0.1, 2)],
                    "confidence": "check",
                    "note": "drop the flubbed take and the cue; keep the redo that follows",
                }
            )
            i = k + 1
            continue
        i += 1
    return cmds


def _clip(words, i, j, t, pre, loud, said):
    win = [max(0.0, t - pre), max(0.0, t - 0.15)]
    peak = None
    if loud is not None and len(loud):
        a, b = int(win[0] / 0.1), int(win[1] / 0.1)
        if b > a:
            seg = loud[a:b]
            peak = round((a + int(np.argmax(smooth(seg, 5)))) * 0.1, 2)
    return {
        "type": "clip",
        "said": " ".join(x["raw"] for x in words[i : j + 1]),
        "t": round(t, 2),
        "cmd": [round(words[i]["start"] - 0.05, 2), round(words[j]["end"] + 0.1, 2)],
        "applies_to": [round(win[0], 2), round(win[1], 2)],
        "peak": peak,
        "confidence": "high",
        "note": "the moment right before the callout",
    }


def _instruction(tr, words, i, k, cmd_start, action, instr_words):
    w = words[i]
    text = " ".join(instr_words)
    here = any(
        x in instr_words
        for x in ("here", "this", "now", "next", "coming", "after", "هنا", "هذا", "هذي", "الحين", "بعدين", "الجاي")
    )
    back = any(
        x in instr_words
        for x in ("that", "there", "last", "previous", "before", "it", "ذاك", "ذيك", "قبل", "اللي", "فات")
    )
    if action == "remove" and not any(x in instr_words for x in ("next", "coming", "after")):
        here, back = False, True
    ps, ns = prev_seg(tr, w["seg"]), next_seg(tr, w["seg"])
    this = seg_bounds(tr, w["seg"])
    if back or not here:
        if this and w["start"] - this[0] > 1.0:
            target = (this[0], w["start"])
        elif ps:
            target = (ps["start"], ps["end"])
        else:
            target = (max(0.0, w["start"] - 5.0), w["start"])
        where = "before"
    else:
        if ns:
            target = (ns["start"], ns["end"])
        else:
            target = (words[k]["end"], words[k]["end"] + 5.0)
        where = "after"
    return {
        "type": action,
        "said": " ".join(x["raw"] for x in words[i : k + 1]),
        "t": round(w["start"], 2),
        "cmd": [round(cmd_start - 0.05, 2), round(words[k]["end"] + 0.1, 2)],
        "applies_to": [round(target[0], 2), round(target[1], 2)],
        "instruction": text,
        "where": where,
        "confidence": "high" if action != "instruction" else "check",
        "note": f"applies to the part {where} the command" + ("" if action != "instruction" else "; read it"),
    }


# ------------------------------------------------------------------ report
def write_report(video, info, tr, events, loud, cmds, notes, md_path):
    L = [f"# What I heard: {Path(video).name} ({fmt(info['duration'])})", ""]
    if tr:
        segs = tr["segments"]
        nwords = sum(len(s.get("words") or s["text"].split()) for s in segs)
        speech = sum(s["end"] - s["start"] for s in segs)
        wpm = nwords / max(speech / 60, 1e-6)
        L.append(
            f"Language: {tr.get('language', '?')}"
            + (f" ({100 * tr['language_probability']:.0f}% sure)" if tr.get("language_probability") else "")
            + f" · talking {100 * speech / max(info['duration'], 1):.0f}% of the time · {wpm:.0f} words/min"
        )
    for n in notes:
        L.append(f"Note: {n}")
    L += ["", f"## Spoken instructions ({len(cmds)})", ""]
    if not cmds:
        L.append('None found. (Say "clip that" right after a great moment, or "Claude, <instruction>" while filming.)')
    for c in cmds:
        a0, a1 = c["applies_to"]
        extra = f" (peak {fmt(c['peak'])})" if c.get("peak") is not None else ""
        L.append(
            f'- {fmt(c["t"])} "{c["said"]}" -> **{c["type"]}** {fmt(a0)}-{fmt(a1)}{extra}. {c["note"]}'
            + (" [confirm]" if c["confidence"] == "check" else "")
        )
    L += ["", "## Moments", ""]
    if events is None:
        L.append("(sound events not analysed)")
    else:
        by = {}
        for e in events:
            by.setdefault(e["type"], []).append(e)
        for k in (
            "laughter",
            "shouting",
            "cheering",
            "gasp",
            "crying",
            "gunfire",
            "explosion",
            "engine",
            "music",
            "animal",
        ):
            if k in by:
                spans = ", ".join(f"{fmt(e['start'])}-{fmt(e['end'])}" for e in by[k][:25])
                more = f" (+{len(by[k]) - 25} more)" if len(by[k]) > 25 else ""
                L.append(f"- {EVENT_WORDS[k].capitalize()}: {spans}{more}")
        if not by:
            L.append("- No laughing, shouting, cheering, music or game sounds stood out.")
    if loud:
        L.append("- Loudest moments: " + ", ".join(f"{fmt(p['t'])} (+{p['db_above_typical']} dB)" for p in loud))
    if tr:
        L += ["", "## Transcript", ""]
        for s in tr["segments"]:
            L.append(f"[{s['id']:04d}] {fmt(s['start'])}  {s['text']}")
    Path(md_path).write_text("\n".join(L) + "\n", encoding="utf-8")


def highlights_from(video, info, cmds, events, ctx=2.0):
    src = str(Path(video).resolve())
    out = []
    for c in cmds:
        if c["type"] == "clip":
            s, e = c["applies_to"]
            pk = c.get("peak") or (s + 0.7 * (e - s))
            out.append(
                {
                    "source": src,
                    "start": round(max(0, s), 2),
                    "end": round(e, 2),
                    "peak": round(pk, 2),
                    "score": 1.0,
                    "mode": "talk",
                    "label": f"callout: {c['said']}",
                }
            )
        elif c["type"] in ("keep", "slowmo", "zoom", "freeze"):
            s, e = c["applies_to"]
            out.append(
                {
                    "source": src,
                    "start": round(max(0, s - 1), 2),
                    "end": round(e, 2),
                    "peak": round((s + e) / 2, 2),
                    "score": 0.9,
                    "mode": "talk",
                    "label": f"you said: {c['said']}",
                }
            )
    for e in events or []:
        w = {"laughter": 0.8, "shouting": 0.7, "cheering": 0.75, "gasp": 0.6}.get(e["type"])
        if w:
            s = max(0.0, e["start"] - 6.0)  # the setup before the reaction
            end = min(info["duration"], e["end"] + ctx)
            out.append(
                {
                    "source": src,
                    "start": round(s, 2),
                    "end": round(end, 2),
                    "peak": round(e["start"], 2),
                    "score": round(w * (0.6 + 0.4 * e["peak"]), 3),
                    "mode": "talk",
                    "label": EVENT_WORDS[e["type"]],
                }
            )
    out.sort(key=lambda h: (-h["score"], h["start"]))
    kept = []
    for h in out:  # drop overlaps, keep the better one
        if all(h["end"] <= k["start"] or h["start"] >= k["end"] for k in kept):
            kept.append(h)
    return kept


def cmd_hear(a):
    info = probe(a.video)
    if not info["has_audio"]:
        die("This file has no audio to listen to.")
    od = Path(a.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    stem = Path(a.video).stem
    notes = []
    x = load_audio(a.video, a.audio_track)
    db = loudness_curve(x)
    loud = loud_moments(db)
    tr = None
    if a.transcript:
        tr = load_json(a.transcript)
    else:
        try:
            from vlog_cut import transcribe

            hot = ", ".join(v for v in [a.hotwords, "Claude, clip that"] if v)
            tr = transcribe(a.video, a.model, a.language, a.audio_track, hot, None, a.multilingual)
            save_json(tr, od / f"{stem}.transcript.json")
        except SystemExit:
            notes.append("No transcript: install faster-whisper (python -m pip install faster-whisper) to hear words.")
        except Exception as e:
            notes.append(f"No transcript: the speech model failed ({type(e).__name__}: {str(e)[:120]}).")
    events = None
    if not a.no_sounds:
        try:
            events, why = sound_events(x)
            if why:
                notes.append(why)
        except SystemExit:
            notes.append("Sound events skipped: the sound model couldn't be downloaded.")
        except Exception as e:
            notes.append(f"Sound events skipped ({type(e).__name__}: {str(e)[:120]}).")
    cmds = find_commands(tr, a.pre, db) if tr else []
    remove = sorted(
        [{"start": c["cmd"][0], "end": c["cmd"][1], "why": f"spoken command: {c['said']}"} for c in cmds]
        + [
            {"start": c["applies_to"][0], "end": c["applies_to"][1], "why": f"{c['type']}: {c['said']}"}
            for c in cmds
            if c["type"] in ("remove", "retake") and c["confidence"] == "high"
        ],
        key=lambda r: r["start"],
    )
    hl = highlights_from(a.video, info, cmds, events)
    if a.export_dir:
        from common import ffmpeg

        Path(a.export_dir).mkdir(parents=True, exist_ok=True)
        for i, h in enumerate(hl, 1):
            clip = Path(a.export_dir) / f"talk_{i:02d}_{stem}_{int(h['peak'])}s.mp4"
            ffmpeg(
                [
                    "-ss",
                    str(h["start"]),
                    "-i",
                    h["source"],
                    "-t",
                    str(h["end"] - h["start"]),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(clip),
                ]
            )
            h["clip"] = str(clip.resolve())
    data = {
        "video": str(Path(a.video).resolve()),
        "duration": info["duration"],
        "language": (tr or {}).get("language"),
        "notes": notes,
        "commands": cmds,
        "events": events or [],
        "loud": loud,
        "edit": {"remove": remove, "highlights": len(hl)},
    }
    save_json(data, od / f"{stem}.talk.json")
    save_json({"highlights": hl, "scored_track": a.audio_track}, od / f"{stem}.highlights.json")
    write_report(a.video, info, tr, events, loud, cmds, notes, od / f"{stem}.talk.md")
    print(f"\nHeard {len(cmds)} spoken instruction(s), {len(events or [])} sound event(s), {len(loud)} loud moment(s).")
    for c in cmds[:12]:
        print(
            f'  {fmt(c["t"])}  "{c["said"]}" -> {c["type"]} {fmt(c["applies_to"][0])}-{fmt(c["applies_to"][1])}'
            + ("  [confirm]" if c["confidence"] == "check" else "")
        )
    for n in notes:
        print(f"  note: {n}")
    print(f"Report -> {od / (stem + '.talk.md')}")
    print(f"Highlights ({len(hl)}) -> {od / (stem + '.highlights.json')}  (use with build_montage.py --highlights)")
    if remove:
        print(f"Spoken commands to cut -> {od / (stem + '.talk.json')} (vlog_cut.py cut --remove-file ...)")


def cmd_prompt(a):
    from vlog_cut import transcribe

    tr = transcribe(a.voice, a.model, a.language, 0, None, None, a.multilingual, quiet=True)
    text = " ".join(s["text"] for s in tr["segments"]).strip()
    out = Path(a.out or Path(a.voice).with_suffix(".prompt.txt"))
    out.write_text(text + "\n", encoding="utf-8")
    print(f"You said ({tr.get('language')}):\n\n{text}\n\nSaved -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("hear")
    p.add_argument("video")
    p.add_argument("--transcript")
    p.add_argument("--model", default="auto")
    p.add_argument("--language")
    p.add_argument("--hotwords")
    p.add_argument("--multilingual", action="store_true")
    p.add_argument("--audio-track", type=int, default=0)
    p.add_argument("--no-sounds", action="store_true")
    p.add_argument("--pre", type=float, default=12.0, help="seconds before a 'clip that' callout to include")
    p.add_argument("--export-dir", help="also save each highlight as its own clip")
    p.add_argument("--out-dir", default="talk")
    p = sub.add_parser("prompt")
    p.add_argument("voice")
    p.add_argument("--model", default="auto")
    p.add_argument("--language")
    p.add_argument("--multilingual", action="store_true")
    p.add_argument("--out")
    a = ap.parse_args()
    {"hear": cmd_hear, "prompt": cmd_prompt}[a.cmd](a)
