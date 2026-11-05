"""Sound effects for edits, synthesized on the fly (no sample packs, no licensing issues).

whoosh  - airy swish that peaks exactly on a cut
impact  - low boom + crack for drops and big hits
riser   - 2s rising tension that slams into a drop

build_sfx_track(events, length, path) writes one stereo WAV with every effect placed in time,
ready to mix under the song. Used by build_montage.py (recipe.audio.sfx) and clip_fx.py.
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
    env = np.sin(np.pi * t ** 1.6) ** 2                     # swells, peaks late, drops off
    cutoff = 250 + 2600 * np.sin(np.pi * t ** 1.4)          # sweep up then down
    x = _onepole_lowpass(_onepole_lowpass(_noise(n, seed), cutoff), cutoff)  # 12 dB/oct: airy, not hissy
    x = x - _onepole_lowpass(x, np.full(n, 180.0))          # remove rumble
    x = x / (np.abs(x).max() or 1) * env
    pan = 0.5 + 0.35 * np.sin(np.pi * t)                     # slight left->right movement
    return np.stack([x * (1 - pan) * 1.4, x * pan * 1.4], axis=1)


def impact(dur=0.9, seed=2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 5) + 38                            # pitch drops 150 -> 38 Hz
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    crack = _noise(n, seed) * np.exp(-t * 60)
    crack = _onepole_lowpass(crack - _onepole_lowpass(crack, np.full(n, 900.0)), np.full(n, 4000.0))
    x = np.tanh(2.4 * boom + 0.35 * crack / (np.abs(crack).max() or 1))   # soft clip = punch
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def riser(dur=2.0, seed=3):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = t ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(220 + 1400 * t ** 2) / SR)
    hiss = _noise(n, seed)
    cut = 200 + 5000 * t ** 2                                # filter opens up as it rises
    hiss = _onepole_lowpass(_onepole_lowpass(hiss, cut), cut)
    x = (0.6 * tone + 0.4 * hiss / (np.abs(hiss).max() or 1)) * env
    x = x / (np.abs(x).max() or 1)
    return np.stack([x, x], axis=1)


def build_sfx_track(events, length, path, volume=0.5):
    """events: list of (kind, time_sec). Whoosh peaks at the time, riser ends at it,
    impact starts at it. Writes a 48k stereo WAV of `length` seconds."""
    import soundfile as sf

    out = np.zeros((int(length * SR) + 1, 2))
    cache = {}
    for kind, t in events:
        if kind not in cache:
            cache[kind] = {"whoosh": whoosh, "impact": impact, "riser": riser}[kind]()
        s = cache[kind]
        if kind == "whoosh":
            start = int((t - len(s) / SR * 0.78) * SR)      # peak lands on the cut
            gain = 0.55
        elif kind == "riser":
            start = int(t * SR) - len(s)
            gain = 0.45
        else:
            start = int(t * SR)
            gain = 0.9
        a, b = max(0, start), min(len(out), start + len(s))
        if b > a:
            out[a:b] += s[a - start:b - start] * gain
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


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Render a single effect to preview it")
    ap.add_argument("kind", choices=["whoosh", "impact", "riser"])
    ap.add_argument("--out", default="sfx_preview.wav")
    a = ap.parse_args()
    length = {"whoosh": 1.0, "impact": 1.2, "riser": 2.5}[a.kind]
    t = {"whoosh": 0.6, "impact": 0.1, "riser": 2.3}[a.kind]
    build_sfx_track([(a.kind, t)], length, a.out, volume=0.9)
    print(f"-> {a.out}")
