"""Sound effects: find the moments that need one, pick the sound, land its hit on the frame.

Three layers (after a workflow shared by creators: a sound library, something that listens and
picks, something that watches the edit and places):

  spot   VIDEO [--out events.json] [--all]
         Watches the edit and lists the moments that want a sound: hard cuts, things popping in
         (cards, images, text), things leaving. Each with a suggested sound and a confidence.
  search QUERY [--n 8] [--dir sounds]           (needs internet)
         Free sounds from Openverse (CC0 / CC BY, credits saved to sounds/CREDITS.md).
  pick   DIR --for pop|whoosh|impact|click|ding|...
         Measures every sound in a folder (yours, or from search) and ranks it for that job:
         length, how sharp the hit is, brightness, noise vs tone, leading silence.
  add    VIDEO --events events.json | --auto  [--sounds DIR] [--volume 0.5] --out OUT
         Mixes the effects under the video's own audio, each one's loudest point exactly on its
         frame (the attack is measured, so the file starts that much earlier).
  preview KIND [--out x.wav]

Built-in sounds are synthesized (no licensing issues): whoosh, swish, impact, riser, pop, click,
tick, ding. Fewer is better: every effect sits on something visible, at most about one per second.
"""

import numpy as np

SR = 48000


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _onepole_lowpass(x, cutoff_hz):
    """Time-varying one-pole lowpass; cutoff_hz is an array the length of x."""
    a = np.exp(-2 * np.pi * np.clip(cutoff_hz, 20, SR / 2 - 100) / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def whoosh(dur=0.45, seed=1):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t**1.6) ** 2  # swells, peaks late, drops off
    cutoff = 250 + 2600 * np.sin(np.pi * t**1.4)  # sweep up then down
    x = _onepole_lowpass(_onepole_lowpass(_noise(n, seed), cutoff), cutoff)  # 12 dB/oct: airy, not hissy
    x = x - _onepole_lowpass(x, np.full(n, 180.0))  # remove rumble
    x = x / (np.abs(x).max() or 1) * env
    pan = 0.5 + 0.35 * np.sin(np.pi * t)  # slight left->right movement
    return np.stack([x * (1 - pan) * 1.4, x * pan * 1.4], axis=1)


def impact(dur=0.9, seed=2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 5) + 38  # pitch drops 150 -> 38 Hz
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    crack = _noise(n, seed) * np.exp(-t * 60)
    crack = _onepole_lowpass(crack - _onepole_lowpass(crack, np.full(n, 900.0)), np.full(n, 4000.0))
    x = np.tanh(2.4 * boom + 0.35 * crack / (np.abs(crack).max() or 1))  # soft clip = punch
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def riser(dur=2.0, seed=3):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = t**2.2
    tone = np.sin(2 * np.pi * np.cumsum(220 + 1400 * t**2) / SR)
    hiss = _noise(n, seed)
    cut = 200 + 5000 * t**2  # filter opens up as it rises
    hiss = _onepole_lowpass(_onepole_lowpass(hiss, cut), cut)
    x = (0.6 * tone + 0.4 * hiss / (np.abs(hiss).max() or 1)) * env
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def swish(dur=0.22, seed=4):
    return whoosh(dur, seed) * 0.8


def pop(dur=0.12, seed=5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 40) + 260  # quick downward blip: a bubble/pop
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38)
    x[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def click(dur=0.05, seed=6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = _noise(n, seed) * np.exp(-t * 180)
    x = x - _onepole_lowpass(x, np.full(n, 1500.0))
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def tick(dur=0.04, seed=7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 160)
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1) * 0.8


def ding(dur=0.9, seed=8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((1320, 1.0), (2640, 0.35), (3960, 0.15)))
    x = x * np.exp(-t * 6)
    x[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def paper(dur=0.32, seed=9):
    """paper sliding onto a desk: a soft brushed swell"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    x = _noise(n, seed)
    x = _onepole_lowpass(x, np.full(n, 3500.0)) - _onepole_lowpass(x, np.full(n, 600.0))
    x = x * env
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x * 0.92], axis=1)


def stamp(dur=0.35, seed=10):
    """a rubber stamp: wooden thud plus a dry knock"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    thud = np.sin(2 * np.pi * (95 * t + 30 * np.exp(-t * 30) / 30)) * np.exp(-t * 22)
    knock = _onepole_lowpass(_noise(n, seed), np.full(n, 2500.0)) * np.exp(-t * 90)
    x = thud * 0.9 + knock * 0.8
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def tape(dur=0.28, seed=11):
    """tape pressed down: a crackly little rip"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    crack = (rng.random(n) < 0.02) * rng.uniform(-1, 1, n)
    x = _onepole_lowpass(crack + 0.25 * _noise(n, seed), np.full(n, 6000.0)) * np.sin(np.pi * t / dur)
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def type_(dur=0.36, seed=12):
    """a few typewriter keys"""
    n = int(dur * SR)
    x = np.zeros(n)
    rng = np.random.default_rng(seed)
    for k in range(4):
        at = int((0.012 + k * 0.08 + rng.uniform(-0.01, 0.01)) * SR)
        m = int(0.03 * SR)
        tt = np.arange(m) / SR
        hit = (_noise(m, seed + k) * 0.6 + np.sin(2 * np.pi * 1800 * tt)) * np.exp(-tt * 140)
        x[at : at + m] += hit[: max(0, min(m, n - at))]
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def marker(dur=0.42, seed=13):
    """a marker scribbling: scratchy, uneven"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = _noise(n, seed)
    x = x - _onepole_lowpass(x, np.full(n, 2200.0))
    x = x * (0.6 + 0.4 * np.sin(2 * np.pi * 11 * t)) * np.sin(np.pi * t / dur) ** 0.6
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def music_bed(length, path, bpm=84, seed=3, mood="documentary"):
    """A quiet documentary bed made on the spot (no licensing): a soft minor-key pad, a felt-piano
    pulse on each beat, a low root, a little vinyl dust. Sits under a voice; ducking does the rest."""
    import soundfile as sf

    n = int(length * SR)
    t = np.arange(n) / SR
    beat = 60 / bpm
    bar = beat * 4
    roots = [57, 53, 48, 55]  # A minor, F, C, G (MIDI)
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    out = np.zeros(n)
    for b in range(int(length / bar) + 1):
        a, e = int(b * bar * SR), int(min(n, (b + 1) * bar * SR + 0.6 * SR))
        if a >= n:
            break
        tt = np.arange(e - a) / SR
        env = np.minimum(1, tt / 0.9) * np.exp(-np.maximum(0, tt - bar) * 3)
        ch = chords[b % 4]
        pad = sum(np.sin(2 * np.pi * hz(m) * tt + 0.3 * np.sin(2 * np.pi * 0.2 * tt)) for m in ch) / 3
        out[a:e] += 0.16 * pad * env
        out[a:e] += 0.18 * np.sin(2 * np.pi * hz(roots[b % 4] - 24) * tt) * env
        for k in range(4):  # felt piano: one chord tone per beat, soft attack, short decay
            s0 = a + int(k * beat * SR)
            if s0 >= n:
                break
            m = int(1.4 * SR)
            pt = np.arange(m) / SR
            note = ch[(k + b) % 3] + 12
            p = (np.sin(2 * np.pi * hz(note) * pt) + 0.3 * np.sin(4 * np.pi * hz(note) * pt)) * np.exp(-pt * 3.2)
            p *= np.minimum(1, pt / 0.008)
            end = min(n, s0 + m)
            out[s0:end] += 0.12 * p[: end - s0]
    out = _onepole_lowpass(out, np.full(n, 3200.0))
    rng = np.random.default_rng(seed)
    out += (rng.random(n) < 0.0006) * rng.uniform(-0.15, 0.15, n)  # dust
    fade = np.minimum(1, np.minimum(t / 2.0, (length - t) / 2.5))
    out = out * np.clip(fade, 0, 1)
    out = out / (np.abs(out).max() or 1) * 0.6
    sf.write(str(path), np.stack([out, out * 0.97], axis=1), SR, subtype="PCM_16")
    return path


SYNTHS = {
    "paper": paper,
    "stamp": stamp,
    "tape": tape,
    "type": type_,
    "marker": marker,
    "whoosh": whoosh,
    "swish": swish,
    "impact": impact,
    "riser": riser,
    "pop": pop,
    "click": click,
    "tick": tick,
    "ding": ding,
}
GAIN = {
    "paper": 0.5,
    "stamp": 0.75,
    "tape": 0.45,
    "type": 0.4,
    "marker": 0.35,
    "whoosh": 0.55,
    "swish": 0.4,
    "riser": 0.45,
    "impact": 0.9,
    "pop": 0.6,
    "click": 0.5,
    "tick": 0.4,
    "ding": 0.45,
}  # fmt: skip


def load_sound(path):
    """Any audio file as 48 kHz stereo float, leading silence trimmed."""
    import subprocess

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-af", "silenceremove=start_periods=1:start_threshold=-45dB",
         "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def peak_time(s):
    """Where the sound hits hardest (seconds from its start): that's what lands on the frame."""
    env = np.abs(s).max(axis=1)
    hop = max(1, SR // 200)
    n = len(env) // hop
    if n == 0:
        return 0.0
    blocks = env[: n * hop].reshape(n, hop).max(axis=1)
    return float(np.argmax(blocks) * hop / SR)


def sound_for(kind, sounds=None):
    """A sound for this kind: the user's (sounds/<kind>*.wav|mp3) first, else the synthesized one."""
    if sounds:
        from pathlib import Path

        for f in sorted(Path(sounds).glob(f"{kind}*")):
            if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff"):
                return load_sound(f)
    if kind.startswith("file:"):
        return load_sound(kind[5:])
    return SYNTHS[kind]()


def build_sfx_track(events, length, path, volume=0.5, sounds=None):
    """events: list of (kind, time_sec). Each sound's loudest moment lands on its time (a riser ends
    on it, a whoosh peaks on it, a pop hits on it). Writes a 48k stereo WAV of `length` seconds."""
    import soundfile as sf

    out = np.zeros((int(length * SR) + 1, 2))
    cache = {}
    for kind, t in events:
        if kind not in cache:
            cache[kind] = sound_for(kind, sounds)
        s = cache[kind]
        start = int(t * SR) - (len(s) if kind == "riser" else int(peak_time(s) * SR))
        gain = GAIN.get(kind, 0.6)
        a, b = max(0, start), min(len(out), start + len(s))
        if b > a:
            out[a:b] += s[a - start : b - start] * gain
    peak = np.abs(out).max()
    if peak > 1:
        out /= peak
    sf.write(str(path), (out * volume).astype(np.float32), SR, subtype="PCM_16")
    return path


def montage_events(plan, sfx_cfg):
    """Pick where effects go in a montage plan."""
    ev = []
    on = sfx_cfg.get("whoosh_on", "effects")
    segs = plan["segments"]
    drop_times = sorted(set(round(d, 3) for d in plan.get("drops", [])))
    for s in segs[1:]:
        if any(abs(s["tl_start"] - d) < 0.05 for d in drop_times):
            continue  # drops get the impact instead
        fx = set(s["effects"]) - {"grade"}
        if on == "all" or (on == "effects" and fx & {"flash", "velocity", "rgb", "zoom"}):
            ev.append(("whoosh", s["tl_start"]))
    if sfx_cfg.get("impact_on_drops", True):
        ev += [("impact", d) for d in drop_times]
    if sfx_cfg.get("riser_before_drop", True) and drop_times and drop_times[0] >= 2.2:
        ev.append(("riser", drop_times[0]))
    return ev


# ------------------------------------------------------------------ spot: watch the edit
def frame_diffs(video, fps=30, w=72, h=128):
    """Per-frame change (0-255) overall and on an 8x4 grid, from a tiny grey copy of the video."""
    import subprocess

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True,
        check=True,
    ).stdout  # fmt: skip
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    return f, np.abs(np.diff(f, axis=0))


def spot_events(frames, d, fps=30, min_gap=0.45, all_events=False):
    """Moments that want a sound. A hard cut changes most of the frame at once; a card, image or
    text popping in changes one region. Something leaving (the region goes back to how it was
    before it arrived) gets a softer swish, or nothing unless all_events."""
    n, H, W = d.shape
    g = d.mean(axis=(1, 2))
    cells = d.reshape(n, 8, H // 8, 4, W // 4).mean(axis=(2, 4))
    med = float(np.median(g)) if n else 0.0
    thr = max(med * 4, 6.0)
    events, last, opened = [], -1e9, []
    for i in range(1, n - 1):
        if not (g[i] > thr and g[i] >= g[i - 1] and g[i] >= g[i + 1]):
            continue
        t = (i + 1) / fps
        if t - last < min_gap:
            continue
        mask = cells[i] > 25
        frac = float(mask.mean())
        strength = float(min(1.0, g[i] / (thr * 4)))
        if frac >= 0.6:
            kind, what = "whoosh", "cut"
        else:
            kind, what = "pop", "appears"
            pre, post = frames[max(0, i - 2)], frames[min(len(frames) - 1, i + 3)]
            # leaving: this region goes back to how it looked before something arrived there
            for o in reversed(opened[-4:]):
                if (o["mask"] & mask).sum() >= max(1, mask.sum() // 2) and t - o["t"] < 12:
                    m = np.kron(o["mask"] & mask, np.ones((H // 8, W // 4))).astype(bool)
                    back = np.abs(post[m] - o["pre"][m]).mean()
                    came = np.abs(post[m] - pre[m]).mean()
                    if back < came * 0.5:
                        kind, what = "swish", "leaves"
                        opened.remove(o)
                    break
            if what == "appears":
                opened.append({"t": t, "mask": mask, "pre": pre})
        if what == "leaves" and not all_events:
            last = t
            continue
        if frac < 0.06 and not all_events:
            continue  # tiny change: probably a jump cut on a talking head or a moving hand
        events.append({"t": round(t, 3), "kind": kind, "what": what, "area": round(frac, 2),
                       "strength": round(strength, 2)})  # fmt: skip
        last = t
    return events


def thin(events, per_sec=0.8):
    """At most about one effect per 1/per_sec seconds: keep the strongest."""
    keep = []
    for e in sorted(events, key=lambda e: -e.get("strength", 0.5)):
        if all(abs(e["t"] - k["t"]) >= 1 / per_sec for k in keep):
            keep.append(e)
    return sorted(keep, key=lambda e: e["t"])


# ------------------------------------------------------------------ pick: measure candidates
WANT = {  # length range (s), wants a sharp hit, brightness range (Hz), noisy (True) or tonal (False)
    "pop": ((0.05, 0.4), True, (300, 3000), False),
    "click": ((0.02, 0.2), True, (1500, 8000), True),
    "tick": ((0.02, 0.15), True, (1500, 8000), False),
    "ding": ((0.3, 2.0), True, (800, 5000), False),
    "whoosh": ((0.25, 1.2), False, (500, 4000), True),
    "swish": ((0.1, 0.5), False, (800, 6000), True),
    "impact": ((0.3, 2.5), True, (40, 800), None),
    "riser": ((1.0, 4.0), False, (300, 6000), None),
}


def measure(s):
    mono = s.mean(axis=1)
    dur = len(mono) / SR
    pk = peak_time(s)
    spec = np.abs(np.fft.rfft(mono[: SR * 2] * np.hanning(min(len(mono), SR * 2)))) + 1e-9
    freqs = np.fft.rfftfreq(min(len(mono), SR * 2), 1 / SR)
    centroid = float((freqs * spec).sum() / spec.sum())
    flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))
    return {"duration": round(dur, 3), "peak_at": round(pk, 3), "brightness_hz": round(centroid),
            "noisiness": round(flat, 3)}  # fmt: skip


def score_for(m, kind):
    (lo, hi), sharp, (blo, bhi), noisy = WANT[kind]
    sc, why = 1.0, []
    if not lo <= m["duration"] <= hi:
        sc -= 0.35
        why.append(f"length {m['duration']}s (want {lo}-{hi})")
    if sharp and m["peak_at"] > 0.06:
        sc -= 0.25
        why.append(f"slow attack ({m['peak_at']}s to its peak)")
    if not sharp and m["peak_at"] < 0.08 and kind != "riser":
        sc -= 0.15
        why.append("hits at once instead of swelling")
    if not blo <= m["brightness_hz"] <= bhi:
        sc -= 0.2
        why.append(f"brightness {m['brightness_hz']} Hz (want {blo}-{bhi})")
    if noisy is True and m["noisiness"] < 0.05:
        sc -= 0.15
        why.append("tonal, wanted airy")
    if noisy is False and m["noisiness"] > 0.3:
        sc -= 0.15
        why.append("noisy, wanted a clean tone")
    return round(max(0.0, sc), 2), why


# ------------------------------------------------------------------ search: Openverse
def openverse_results(j):
    out = []
    for r in j.get("results", []):
        if not r.get("url"):
            continue
        out.append({
            "id": r.get("id"), "title": r.get("title") or "untitled", "url": r["url"],
            "license": f"{r.get('license', '')} {r.get('license_version', '')}".strip(),
            "creator": r.get("creator") or "unknown", "source": r.get("foreign_landing_url") or "",
            "duration": (r.get("duration") or 0) / 1000, "filetype": r.get("filetype") or "mp3",
        })  # fmt: skip
    return out


def search(query, n, folder):
    import json
    import re
    import urllib.parse
    import urllib.request
    from pathlib import Path

    q = urllib.parse.urlencode({"q": query, "page_size": n * 2, "license": "cc0,by", "length": "short"})
    req = urllib.request.Request(f"https://api.openverse.org/v1/audio/?{q}", headers={"User-Agent": "pro-editor"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = openverse_results(json.loads(r.read()))[:n]
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    credits, got = [], []
    for k, r in enumerate(res):
        name = re.sub(r"[^a-z0-9]+", "-", f"{query} {k + 1} {r['title']}".lower()).strip("-")[:60]
        dst = folder / f"{name}.{r['filetype']}"
        try:
            urllib.request.urlretrieve(r["url"], dst)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {r['title']}: {e}")
            continue
        got.append(dst)
        credits.append(f'- {dst.name}: "{r["title"]}" by {r["creator"]}, {r["license"]}, {r["source"]}')
    if credits:
        with open(folder / "CREDITS.md", "a", encoding="utf-8") as f:
            f.write("\n".join(credits) + "\n")
    return got


# ------------------------------------------------------------------ add: mix under the video
def add_to_video(video, events, out, volume=0.5, sounds=None):
    import subprocess
    import tempfile
    from pathlib import Path

    from common import probe

    info = probe(video)
    with tempfile.TemporaryDirectory() as td:
        wav = build_sfx_track([(e["kind"], e["t"]) for e in events], info["duration"], Path(td) / "fx.wav",
                              volume, sounds)  # fmt: skip
        if info["has_audio"]:
            fc = "[0:a]aresample=48000[a];[a][1:a]amix=inputs=2:duration=first:normalize=0[m]"
            amap = ["-filter_complex", fc, "-map", "0:v", "-map", "[m]"]
        else:
            amap = ["-map", "0:v", "-map", "1:a"]
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(wav), *amap, "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)],
            check=True,
        )  # fmt: skip
    return out


def main():
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("spot")
    p.add_argument("video")
    p.add_argument("--out", default="sfx_events.json")
    p.add_argument("--all", action="store_true", help="also small changes and things leaving")
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--dir", default="sounds")
    p = sub.add_parser("pick")
    p.add_argument("dir")
    p.add_argument("--for", dest="kind", required=True, choices=sorted(WANT))
    p = sub.add_parser("add")
    p.add_argument("video")
    p.add_argument("--events")
    p.add_argument("--auto", action="store_true", help="spot the moments and add sounds in one go")
    p.add_argument("--sounds", help="folder of your own sounds named pop*.wav, whoosh*.mp3 ...")
    p.add_argument("--volume", type=float, default=0.5)
    p.add_argument("--out", required=True)
    p = sub.add_parser("preview")
    p.add_argument("kind", choices=sorted(SYNTHS))
    p.add_argument("--out", default="sfx_preview.wav")
    a = ap.parse_args()

    if a.cmd == "preview":
        s = SYNTHS[a.kind]()
        L = len(s) / SR + 0.6
        build_sfx_track([(a.kind, (L - 0.1) if a.kind == "riser" else 0.3 + peak_time(s))], L, a.out, 0.9)
        print(f"-> {a.out}")
    elif a.cmd == "spot" or (a.cmd == "add" and a.auto):
        frames, d = frame_diffs(a.video)
        ev = thin(spot_events(frames, d, all_events=getattr(a, "all", False)))
        if a.cmd == "spot":
            Path(a.out).write_text(json.dumps({"video": str(Path(a.video).resolve()), "events": ev}, indent=1))
            for e in ev:
                print(f"  {e['t']:7.2f}s  {e['kind']:<7} {e['what']:<8} area {e['area']:.2f}")
            print(f"{len(ev)} moments -> {a.out}  (edit the list, then: sfx.py add VIDEO --events {a.out})")
        else:
            add_to_video(a.video, ev, a.out, a.volume, a.sounds)
            print(f"{len(ev)} effects -> {a.out}")
    elif a.cmd == "add":
        if not a.events:
            raise SystemExit("add needs --events FILE or --auto")
        ev = json.loads(Path(a.events).read_text())["events"]
        add_to_video(a.video, ev, a.out, a.volume, a.sounds)
        print(f"{len(ev)} effects -> {a.out}")
    elif a.cmd == "search":
        got = search(a.query, a.n, a.dir)
        print(
            f"{len(got)} sound(s) in {a.dir}/ (credits in {a.dir}/CREDITS.md). Rank them: sfx.py pick {a.dir} --for ..."
        )
    elif a.cmd == "pick":
        rows = []
        for f in sorted(Path(a.dir).iterdir()):
            if f.suffix.lower() in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aiff"):
                m = measure(load_sound(f))
                sc, why = score_for(m, a.kind)
                rows.append((sc, f.name, m, why))
        for sc, name, m, why in sorted(rows, key=lambda r: -r[0]):
            print(f"  {sc:.2f}  {name:<40} {m['duration']:.2f}s peak@{m['peak_at']:.2f}s "
                  f"{m['brightness_hz']}Hz  {'; '.join(why) or 'fits'}")  # fmt: skip


if __name__ == "__main__":
    main()
