"""Put an animated avatar in your hand (or anywhere in the shot) and keep it there as you move.

Commands
  look  [--style solid|hologram] [--color #hex] [--accent #hex] [--out look.png]
        A sheet of the built-in avatar (expressions, both styles) to show before rendering.
  check VIDEO [--out-dir avatar]
        Finds hands (MediaPipe), says how often a hand is visible and how big it is, and writes a
        sheet of frames with the tracking drawn on. Saves the track so `render` can reuse it.
  render VIDEO [--out avatar.mp4] [options]
        Avatar:   --avatar builtin|FILE   (FILE: PNG with transparency, GIF/WebP, a video with alpha,
                                           or a green/blue-screen video, keyed with --key)
                  --style solid|hologram  --color #hex  --accent #hex  --size 1.0
        Where:    --anchor palm|above|finger|fixed  [--pos 0.5,0.8 for fixed]  --hand auto|left-side|right-side
                  --start S  --end E  --tilt 0.5
        Life:     --no-wave  --no-boop (poke it with your other hand)  --summon (open hand = appear,
                  fist = vanish)  --voice line.wav --voice-at S (it talks)  --say "Hi!@1.0-2.5" (bubble)
        Look:     --shadow 0.45  --match 0.3 (blend into the scene's light)  --soften 0.6  --no-grain
        Output:   --preview (small, fast)  --debug (draw the tracking)  --track track.json (reuse)
        Also writes <out>_check.jpg (frames to check the placement) and <out>.track.json.

How it stays believable: hand landmarks from MediaPipe, One Euro smoothing (no jitter at rest, no
lag when you move), a soft contact shadow on the palm, the avatar tinted toward the scene's light,
matching film grain, motion blur on fast moves, and a short hold when tracking drops for a moment.
The hand-tracking model (about 7.5 MB) downloads once on first use.
"""

import argparse
import math
import subprocess
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import avatar_art as art
from common import (
    dec_args,
    die,
    find_font,
    get_model,
    hw_encoder,
    hw_video_args,
    load_json,
    need,
    preview_size,
    probe,
    quiet_native_logs,
    save_json,
)

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/"
    "float16/latest/hand_landmarker.task"
)
MCP = [5, 9, 13, 17]
TIPS = [8, 12, 16, 20]
BONES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
]
SIZES = [96, 120, 150, 188, 235, 294, 367, 459, 574, 717, 896]  # renders above 896 px are upscaled


def cv2_or_die():
    try:
        import cv2

        return cv2
    except ImportError:
        die('The avatar needs OpenCV:  python -m pip install "opencv-python-headless<5"')


def even(x):
    return max(2, int(round(x / 2)) * 2)


# ------------------------------------------------------------------ video in / out
def read_frames(path, fps, w, h, start=None, dur=None):
    cmd = [need("ffmpeg"), "-hide_banner", "-loglevel", "error", *dec_args()]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-an", "-vf", f"fps={fps},scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    err = tempfile.TemporaryFile()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
    n = w * h * 3
    got = 0
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            got += 1
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.wait()
        if got == 0:
            err.seek(0)
            tail = err.read().decode(errors="replace").strip().splitlines()[-5:]
            print("ffmpeg couldn't decode the video:\n  " + "\n  ".join(tail))
        err.close()


def open_writer(out, w, h, fps, src, has_audio, voice=None, voice_at=0.0, preview=False, enc=None):
    cmd = [
        need("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        f"{fps}",
        "-i",
        "-",
        "-i",
        str(src),
    ]
    if voice:
        cmd += ["-i", str(voice)]
        ms = max(0, int(voice_at * 1000))
        if has_audio:
            cmd += [
                "-filter_complex",
                f"[2:a]adelay={ms}|{ms},volume=1.0[v];[1:a:0][v]amix=inputs=2:normalize=0:dropout_transition=0[aout]",
                "-map",
                "0:v",
                "-map",
                "[aout]",
            ]
        else:
            cmd += ["-filter_complex", f"[2:a]adelay={ms}|{ms}[aout]", "-map", "0:v", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a:0?"]
    if preview:
        vargs = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24"]
    elif enc:
        vargs = hw_video_args(enc, 18, "medium")
    else:
        vargs = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    cmd += vargs + [
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out),
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def video_fps(info):
    f = info.get("fps") or 30
    return 30 if (f < 5 or f > 120) else round(f, 3)


# ------------------------------------------------------------------ hand tracking
def run_tracking(video, info, fps, win=(0.0, None)):
    with quiet_native_logs():
        return _run_tracking(video, info, fps, win)


def _run_tracking(video, info, fps, win=(0.0, None)):
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
    except ImportError:
        die(
            "Hand tracking needs MediaPipe:  python -m pip install mediapipe\n"
            "(or skip tracking with --anchor fixed --pos 0.5,0.8)"
        )
    model = get_model("hand_landmarker.task", HAND_MODEL_URL, "PRO_EDITOR_HAND_MODEL", "hand-tracking")
    W, H = info["width"], info["height"]
    f = min(1.0, 640 / max(W, H))
    dw, dh = even(W * f), even(H * f)
    t0, t1 = win
    t1 = t1 if t1 is not None else info["duration"]
    opts = vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=model),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.4,
        min_hand_presence_confidence=0.4,
        min_tracking_confidence=0.4,
    )
    det = vision.HandLandmarker.create_from_options(opts)
    first = int(round(t0 * fps))
    frames = [[] for _ in range(first)]
    total = max(1, int((t1 - t0) * fps))
    try:
        for k, img in enumerate(read_frames(video, fps, dw, dh, start=t0 or None, dur=t1 - t0)):
            r = det.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img)),
                int((first + k) * 1000 / fps),
            )
            hands = []
            for lm, hd in zip(r.hand_landmarks, r.handedness):
                hands.append({"lm": [[round(p.x, 4), round(p.y, 4)] for p in lm], "s": round(hd[0].score, 3)})
            frames.append(hands)
            if k % max(1, int(fps * 5)) == 0:
                print(f"  tracking hands {100 * k / total:3.0f}%", end="\r")
    finally:
        det.close()
    print("  tracking hands 100%")
    return {"fps": fps, "width": W, "height": H, "window": [t0, t1], "frames": frames}


def load_or_track(video, info, fps, path, win):
    if path and Path(path).exists():
        tr = load_json(path)
        w = tr.get("window", [0, None])
        ok = (
            abs(tr.get("fps", 0) - fps) < 0.01
            and tr.get("width") == info["width"]
            and w[0] <= win[0] + 0.01
            and (
                w[1] is None
                or win[1] is None
                and w[1] >= info["duration"] - 0.1
                or win[1] is not None
                and w[1] >= win[1] - 0.01
            )
        )
        if ok:
            print(f"Reusing hand track {path}")
            return tr
    tr = run_tracking(video, info, fps, win)
    if path:
        save_json(tr, path)
    return tr


def metrics(lm, W, H):
    P = np.asarray(lm, np.float32) * np.float32([W, H])
    knuck = P[MCP].mean(0)
    c = 0.45 * P[0] + 0.55 * knuck
    size = max(float(np.linalg.norm(P[0] - P[9])), 1.2 * float(np.linalg.norm(P[5] - P[17])), 1.0)
    ang = math.degrees(math.atan2(P[17, 1] - P[5, 1], P[17, 0] - P[5, 0]))
    while ang > 90:
        ang -= 180
    while ang <= -90:
        ang += 180
    # a finger is extended when its tip is clearly further from the wrist than its middle joint
    ext = [float(np.linalg.norm(P[t] - P[0]) / max(np.linalg.norm(P[t - 2] - P[0]), 1e-3)) for t in TIPS]
    n_ext = sum(e > 1.2 for e in ext)
    n_curl = sum(e < 1.0 for e in ext)
    return {
        "c": c,
        "size": size,
        "ang": ang,
        "top": float(P[:, 1].min()),
        "n_ext": n_ext,
        "n_curl": n_curl,
        "is_open": n_ext >= 3,
        "is_fist": n_curl >= 3,
        "tip": P[8],
        "P": P,
    }


def choose(hands, prev_c, mode, diag):
    if not hands:
        return None
    if mode == "left-side":
        return min(range(len(hands)), key=lambda i: hands[i]["c"][0])
    if mode == "right-side":
        return max(range(len(hands)), key=lambda i: hands[i]["c"][0])
    if prev_c is not None:
        i = min(range(len(hands)), key=lambda i: np.linalg.norm(hands[i]["c"] - prev_c))
        if np.linalg.norm(hands[i]["c"] - prev_c) < 0.35 * diag:
            return i
    return max(range(len(hands)), key=lambda i: hands[i]["size"] * (0.7 + 0.1 * hands[i]["n_ext"]))


class OneEuro:
    """One Euro filter (Casiez et al. 2012): heavy smoothing when still, light when moving fast."""

    def __init__(self, min_cutoff, beta, d_cutoff=1.0):
        self.mc, self.beta, self.dc = min_cutoff, beta, d_cutoff
        self.x = None
        self.dx = 0.0

    @staticmethod
    def _a(dt, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self):
        self.x = None
        self.dx = 0.0

    def __call__(self, x, dt):
        if self.x is None:
            self.x = x
            return x
        dx = (x - self.x) / dt
        ad = self._a(dt, self.dc)
        self.dx = ad * dx + (1 - ad) * self.dx
        a = self._a(dt, self.mc + self.beta * abs(self.dx))
        self.x = a * x + (1 - a) * self.x
        return self.x


# ------------------------------------------------------------------ where the avatar goes, frame by frame
def plan_frames(track, n, W, H, fps, a):
    dt = 1.0 / fps
    diag = math.hypot(W, H)
    k = 1080 / min(W, H)  # filter tuning is resolution independent
    fx, fy = OneEuro(1.0, 0.004 / k), OneEuro(1.0, 0.004 / k)
    fs, fr = OneEuro(0.5, 0.001 / k), OneEuro(0.8, 0.01)
    hold = int(round(0.4 * fps))
    start = a.start or 0.0
    end = a.end if a.end is not None else n / fps + 1
    frames = (track or {}).get("frames", [])
    plans = []
    prev_c, last_i, ref_ang = None, -(10**9), None
    shown, appear_t, exit_t = False, None, None
    open_state, open_run, closed_run = (not a.summon), 0, 0
    last_boop = -10.0
    px = py = ps = pr = None
    for i in range(n):
        t = i * dt
        hands = [metrics(h["lm"], W, H) for h in (frames[i] if i < len(frames) else [])]
        sel = None if a.anchor == "fixed" else choose(hands, prev_c, a.hand, diag)
        found = sel is not None
        m = hands[sel] if found else None
        if a.anchor == "fixed":
            tx, ty = a.pos[0] * W, a.pos[1] * H
            ts_ = a.size * 0.30 * min(W, H) * (1.4 if H > W else 1.0)
            found = True
        elif found:
            if a.anchor == "palm":
                tx, ty, ts_ = m["c"][0], m["c"][1], a.size * 1.35 * m["size"]
            elif a.anchor == "above":
                tx, ty, ts_ = m["c"][0], m["top"] - 0.12 * m["size"], a.size * 1.35 * m["size"]
            else:  # finger
                tx, ty, ts_ = m["tip"][0], m["tip"][1] - 0.04 * m["size"], a.size * 0.8 * m["size"]
            if ref_ang is None:
                ref_ang = m["ang"]
            prev_c, last_i = m["c"], i
            # summon gesture: open hand shows the avatar, a fist hides it (with hysteresis)
            if a.summon:
                if m["is_open"]:
                    open_run, closed_run = open_run + 1, 0
                elif m["is_fist"]:
                    closed_run, open_run = closed_run + 1, 0
                if open_run >= int(0.2 * fps):
                    open_state = True
                if closed_run >= int(0.15 * fps):
                    open_state = False
        holding = (not found) and (i - last_i) <= hold
        available = found or holding
        want = (start <= t <= end) and available and open_state
        if want and not shown:
            shown, appear_t = True, t
            if (i - last_i) > hold or px is None:
                for f_ in (fx, fy, fs, fr):
                    f_.reset()
        elif not want and shown:
            shown, exit_t = False, t
        if found:
            px, py = fx(float(tx), dt), fy(float(ty), dt)
            ps = fs(float(ts_), dt)
            roll = 0.0
            if a.anchor != "fixed" and a.tilt and m is not None and ref_ang is not None:
                roll = float(np.clip((m["ang"] - ref_ang) * a.tilt, -25, 25))
            pr = fr(roll, dt)
        # poke ("boop") with the other hand's index fingertip
        if a.boop and shown and px is not None and len(hands) > 1 and sel is not None:
            for j, h in enumerate(hands):
                if j == sel:
                    continue
                tipx, tipy = h["tip"]
                if abs(tipx - px) < 0.36 * ps and (py - 1.0 * ps) < tipy < (py - 0.15 * ps) and t - last_boop > 1.2:
                    last_boop = t
        plans.append(
            {
                "t": t,
                "x": px,
                "y": py,
                "h": ps,
                "roll": pr or 0.0,
                "shown": shown,
                "found": found,
                "appear": appear_t,
                "exit": exit_t,
                "boop": last_boop,
                "hands": hands,
                "sel": sel,
            }
        )
    # velocity for motion blur
    for i, p in enumerate(plans):
        q = plans[i - 1] if i else p
        p["vx"] = (p["x"] - q["x"]) if (p["x"] is not None and q["x"] is not None) else 0.0
        p["vy"] = (p["y"] - q["y"]) if (p["y"] is not None and q["y"] is not None) else 0.0
    return plans


# ------------------------------------------------------------------ animation
def smoothstep(e0, e1, x):
    t = min(max((x - e0) / max(e1 - e0, 1e-6), 0.0), 1.0)
    return t * t * (3 - 2 * t)


class Life:
    """Blinks, glances and idle motion on a fixed schedule (deterministic, so re-renders match)."""

    def __init__(self, seed=7, dur=3600):
        rng = np.random.default_rng(seed)
        self.blinks, t = [], 1.2
        while t < dur:
            self.blinks.append(t)
            t += rng.uniform(2.2, 4.8)
        self.glances, t = [], 3.5
        while t < dur:
            self.glances.append((t, rng.choice([-1.0, 1.0])))
            t += rng.uniform(4.0, 8.0)

    def blink(self, t):
        i = np.searchsorted(self.blinks, t) - 1
        if i < 0:
            return 0.0
        d = t - self.blinks[i]
        if d > 0.16:
            return 0.0
        v = 1 - abs(2 * d / 0.16 - 1)
        return 1.0 if v > 0.66 else (0.55 if v > 0.2 else 0.0)

    def look(self, t):
        for g, side in self.glances:
            if g <= t <= g + 1.0:
                return side * smoothstep(g, g + 0.15, t) * (1 - smoothstep(g + 0.85, g + 1.0, t))
            if g > t:
                break
        return 0.0


def anim(t, p, a, life, mouth_env):
    """state for avatar_art.render + extra transform (scale, squash, alpha) for this frame."""
    tl = t - (p["appear"] or 0.0)
    st = {"accent": a.accent_rgb, "color": a.color_rgb}
    scale, sq, alpha = 1.0, 1.0, 1.0
    # entrance: elastic pop
    if tl < 0.5:
        q = max(tl, 0) / 0.5
        scale = 1 - (1 - q) ** 2 * math.cos(4.5 * q)
        sq = 1 + 0.22 * math.sin(q * math.pi) * (1 - q)
        st["expr"] = "surprised" if q < 0.6 else "normal"
    # exit: shrink away
    if not p["shown"] and p["exit"] is not None:
        q = min((t - p["exit"]) / 0.3, 1.0)
        scale *= max(1 - q * q, 0.0)
        alpha = 1 - q
    # wave hello
    if a.wave and 0.45 <= tl <= 2.35:
        w = smoothstep(0.45, 0.7, tl) * (1 - smoothstep(2.1, 2.35, tl))
        st["wave"] = round(w * 4) / 4
        st["wave_phase"] = round(((tl - 0.45) * 2.2 % 1.0) * 12) / 12 / 2.2
        st.setdefault("expr", "happy")
        if st["expr"] == "normal":
            st["expr"] = "happy"
    # boop reaction
    db = t - p["boop"]
    if 0 <= db < 1.4:
        if db < 0.6:
            sq = 1 - 0.25 * math.exp(-6 * db) * math.cos(18 * db)
        st["expr"] = "squeeze" if db < 0.45 else "heart"
    # idle life
    st["blink"] = 0.0 if st.get("expr") in ("happy", "squeeze", "heart") else life.blink(t)
    st["look"] = round(life.look(t) * 2) / 2
    sway = math.sin(2 * math.pi * t / 1.7 - 1.0) * 0.5 - float(np.clip(p["vx"] / max(0.15 * (p["h"] or 1), 1), -1, 1))
    st["antenna"] = round(float(np.clip(sway, -1, 1)) * 2) / 2
    if mouth_env is not None:
        st["mouth"] = round(float(mouth_env) * 5) / 5
    st["squash"] = round(sq * 20) / 20
    breath = 1 + 0.018 * math.sin(2 * math.pi * t / 1.7)
    return st, scale, breath, alpha


def state_key(st):
    return tuple(sorted((k, v if not isinstance(v, list) else tuple(v)) for k, v in st.items()))


# ------------------------------------------------------------------ avatar sources
class BuiltinAvatar:
    def __init__(self):
        self.cache = OrderedDict()
        self.bytes = 0

    def sprite(self, st, height):
        hq = next((s for s in SIZES if s >= height), SIZES[-1])
        key = (hq, state_key(st))
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        img = art.render(st, hq)
        spr = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        anc = art.anchor_px(hq)
        self.cache[key] = (spr, anc)
        self.bytes += spr.nbytes
        while self.bytes > 350e6 and len(self.cache) > 1:
            _, (old, _) = self.cache.popitem(last=False)
            self.bytes -= old.nbytes
        return spr, anc


class CustomAvatar:
    """A PNG / GIF / WebP / video (with alpha, or keyed green/blue screen), looped."""

    def __init__(self, path, key="auto", fps=30, max_h=1024):
        info = probe(path)
        if not info.get("has_video"):
            die(f"Can't read the avatar file {path}")
        still = Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
        w, h = info["width"], info["height"]
        f = min(1.0, max_h / h)
        w2, h2 = even(w * f), even(h * f)
        pre = []
        if (
            Path(path).suffix.lower() == ".webm"
            and "libvpx-vp9"
            in subprocess.run([need("ffmpeg"), "-hide_banner", "-decoders"], capture_output=True, text=True).stdout
        ):
            pre = ["-c:v", "libvpx-vp9"]  # the built-in VP9 decoder drops the alpha channel
        keycol = None
        if key != "none":
            first = self._decode(path, pre, f"scale={w2}:{h2}", w2, h2, 1, still)[0]
            if first[..., 3].min() < 250:
                keycol = None  # already has transparency
            elif key in ("green", "blue"):
                keycol = "0x00FF00" if key == "green" else "0x0000FF"
                keycol = self._corner_color(first) or keycol
            else:
                keycol = self._corner_color(first, strict=True)
        vf = f"scale={w2}:{h2}"
        if keycol:
            vf += f",chromakey=color={keycol}:similarity=0.14:blend=0.07"
            g = int(keycol[4:6], 16) > int(keycol[6:8], 16)
            vf += f",despill=type={'green' if g else 'blue'}"
            print(f"  keyed out the {'green' if g else 'blue'} background ({keycol})")
        n = 1 if still else min(int((info["duration"] or 1) * fps) + 1, 450)
        frames = self._decode(path, pre, vf, w2, h2, n, still, fps)
        if not frames:
            die(f"Couldn't decode {path}")
        alpha = np.max([fr[..., 3] for fr in frames], axis=0)
        ys, xs = np.nonzero(alpha > 12)
        if len(xs) == 0:
            die("The avatar is fully transparent after keying. Try --key none.")
        if keycol is None and alpha.min() > 250:
            print(
                "  Note: this avatar has no transparent background, so it will show as a rectangle. "
                "Use a PNG with transparency or a green-screen video (--key green)."
            )
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        self.frames = []
        for fr in frames:
            c = fr[y0:y1, x0:x1].astype(np.float32) / 255
            c[..., :3] *= c[..., 3:]
            self.frames.append((c * 255 + 0.5).astype(np.uint8))
        bottom = np.nonzero(alpha[y0:y1, x0:x1][-max(2, (y1 - y0) // 12) :].max(0) > 12)[0]
        ax = (bottom.min() + bottom.max()) / 2 if len(bottom) else (x1 - x0) / 2
        self.anchor = (float(ax), float(y1 - y0))
        self.fps = fps
        self.h = y1 - y0

    @staticmethod
    def _corner_color(img, strict=False):
        h, w = img.shape[:2]
        k = max(2, min(h, w) // 20)
        patches = [img[:k, :k], img[:k, -k:], img[-k:, :k], img[-k:, -k:]]
        cols = np.array([p[..., :3].reshape(-1, 3).mean(0) for p in patches])
        c = np.median(cols, axis=0)
        spread = np.abs(cols - c).max()
        r, g, b = c
        is_g = g > 90 and g > r * 1.35 and g > b * 1.35
        is_b = b > 90 and b > r * 1.35 and b > g * 1.2
        if (is_g or is_b) and (spread < 60 or not strict):
            return f"0x{int(r):02X}{int(g):02X}{int(b):02X}"
        return None

    @staticmethod
    def _decode(path, pre, vf, w, h, n, still, fps=30):
        cmd = [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            *pre,
            "-i",
            str(path),
            "-vf",
            vf if still else f"fps={fps},{vf}",
            "-frames:v",
            str(n),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True)
        size = w * h * 4
        return [
            np.frombuffer(res.stdout[i : i + size], np.uint8).reshape(h, w, 4).copy()
            for i in range(0, len(res.stdout) - size + 1, size)
        ]

    def sprite(self, tl):
        i = int(max(tl, 0) * self.fps) % len(self.frames)
        return self.frames[i], self.anchor


# ------------------------------------------------------------------ compositing
def place(cv2, spr, anc, at, h_t, roll, stretch, bounds, pad=2):
    """Warp a premultiplied uint8 sprite so its anchor lands on `at` (x, y), h_t pixels tall, rotated
    by `roll` degrees and stretched by (sx, sy), clipped to `bounds` (W, H).
    Returns (roi, warped float RGBA), or (None, None) when nothing is visible."""
    x, y = at
    sx_extra, sy_extra = stretch
    W, H = bounds
    hs = spr.shape[0]
    k = h_t / hs
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    a11, a12 = k * sx_extra * cr, -k * sy_extra * sr
    a21, a22 = k * sx_extra * sr, k * sy_extra * cr
    tx = x - (a11 * anc[0] + a12 * anc[1])
    ty = y - (a21 * anc[0] + a22 * anc[1])
    hh, ww = spr.shape[:2]
    corners = np.array([[0, 0], [ww, 0], [0, hh], [ww, hh]], np.float32)
    px = a11 * corners[:, 0] + a12 * corners[:, 1] + tx
    py = a21 * corners[:, 0] + a22 * corners[:, 1] + ty
    x0, x1 = int(max(math.floor(px.min()) - pad, 0)), int(min(math.ceil(px.max()) + pad, W))
    y0, y1 = int(max(math.floor(py.min()) - pad, 0)), int(min(math.ceil(py.max()) + pad, H))
    if x1 <= x0 + 1 or y1 <= y0 + 1:
        return None, None
    M = np.float32([[a11, a12, tx - x0], [a21, a22, ty - y0]])
    src = spr.astype(np.float32) / 255
    flags = cv2.INTER_AREA if k < 0.6 else cv2.INTER_LINEAR
    if k < 0.6:  # pre-shrink so big reductions don't alias
        src = cv2.resize(src, (max(1, int(ww * k * 1.25)), max(1, int(hh * k * 1.25))), interpolation=cv2.INTER_AREA)
        f2 = src.shape[0] / hh
        M[:, :2] /= f2
        flags = cv2.INTER_LINEAR
    warped = cv2.warpAffine(
        src, M, (x1 - x0, y1 - y0), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
    )
    return (y0, y1, x0, x1), warped


def contact_shadow(frame_f, x, y, w_body, strength):
    """Soft dark ellipse under the feet, so the avatar sits on the palm instead of floating over it."""
    H, W = frame_f.shape[:2]
    rx, ry = max(w_body * 0.42, 2), max(w_body * 0.11, 1.5)
    x0, x1 = int(max(x - rx * 1.6, 0)), int(min(x + rx * 1.6, W))
    y0, y1 = int(max(y - ry * 2.2, 0)), int(min(y + ry * 2.8, H))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d = ((xx - x) / rx) ** 2 + ((yy - (y + ry * 0.25)) / ry) ** 2
    core = np.exp(-d * 2.0) * strength + np.exp(-d * 9.0) * strength * 0.5
    frame_f[y0:y1, x0:x1] *= (1 - np.clip(core, 0, 0.85))[..., None]


_NOISE = {}


def noise_patch(h, w, seed):
    """Film grain from a fixed tile at a random offset (fast; looks the same as fresh noise)."""
    if "tile" not in _NOISE:
        _NOISE["tile"] = np.random.default_rng(1).normal(0, 1, (256, 256)).astype(np.float32)
    tile = _NOISE["tile"]
    rng = np.random.default_rng(seed)
    oy, ox = int(rng.integers(0, 256)), int(rng.integers(0, 256))
    reps = (h + oy) // 256 + 1, (w + ox) // 256 + 1
    big = np.tile(tile, reps)
    return big[oy : oy + h, ox : ox + w]


def scene_match(region, roi, warped, match, grain, seed):
    """Tint/brighten the avatar toward the light around it, and add the footage's own grain."""
    sur = region[::4, ::4]
    m = sur.reshape(-1, 3).mean(0)
    lum = float(m @ np.float32([0.299, 0.587, 0.114]))
    if match > 0:
        tint = m / max(float(m.mean()), 1e-3)
        tint = 1 + np.clip(tint - 1, -0.3, 0.3) * match * 1.6
        bright = 1 + (float(np.clip(0.72 + 0.6 * lum, 0.7, 1.12)) - 1) * min(match / 0.3, 1.5)
        warped[..., :3] *= (tint * bright).astype(np.float32)
    if grain:
        y0, y1, x0, x1 = roi
        g = region[y0:y1:2, x0:x1:2].mean(2)
        if g.shape[0] > 3 and g.shape[1] > 3:
            hp = g[1:, 1:] - 0.25 * (g[:-1, 1:] + g[1:, :-1] + g[:-1, :-1] + g[1:, 1:])
            sigma = float(np.clip(np.std(hp) * 0.9, 0.0, 0.035))
            if sigma > 0.003:
                warped[..., :3] += (noise_patch(*warped.shape[:2], seed) * sigma)[..., None] * warped[..., 3:]
    np.clip(warped, 0, None, out=warped)


def motion_blur(cv2, warped, vx, vy):
    sp = math.hypot(vx, vy)
    if sp < 4:
        return warped
    L = int(min(sp * 0.6, 31)) | 1
    kern = np.zeros((L, L), np.float32)
    c = L // 2
    ang = math.atan2(vy, vx)
    for s in np.linspace(-c, c, L * 2):
        kern[int(round(c + s * math.sin(ang))), int(round(c + s * math.cos(ang)))] = 1
    kern /= kern.sum()
    return cv2.filter2D(warped, -1, kern, borderType=cv2.BORDER_CONSTANT)


def hologram(cv2, warped, roi, t, accent, h_t, reveal=1.0, y_feet=None):
    a = warped[..., 3]
    rgb = warped[..., :3] / np.maximum(a, 1e-4)[..., None]
    lum = rgb @ np.float32([0.3, 0.59, 0.11])
    acc = np.asarray(accent, np.float32)
    # parts drawn in the accent colour (eyes, mouth, lights) become the brightest bits of the hologram
    accentness = np.clip(1 - np.abs(rgb - np.asarray(accent, np.float32)).sum(-1) / 0.9, 0, 1)
    col = acc * (0.3 + 0.95 * lum + 0.9 * accentness)[..., None] + np.clip(lum - 0.72, 0, 1)[..., None] * 2.2
    col += accentness[..., None] * 0.55
    flick = 0.88 + 0.12 * math.sin(t * 37.0) * math.sin(t * 13.0 + 1.3)
    al = a * (0.5 + 0.4 * lum + 0.4 * accentness) * flick
    y0, y1, x0, x1 = roi
    yy = np.arange(y0, y1, dtype=np.float32)
    scan = np.where(((yy + t * 45.0) % 5.0) < 1.6, 0.45, 1.0).astype(np.float32)
    al *= scan[:, None]
    if reveal < 1.0 and y_feet is not None:  # materialize from the feet up
        edge = y_feet - h_t * 1.05 * reveal
        al *= yy[:, None] >= edge
        col = col + (np.exp(-np.abs(yy - edge) / 3.0)[:, None, None] * 1.5) * acc
    prem = col * al[..., None]
    s = max(1, int(round(h_t / 260)))
    prem[..., 0] = np.roll(prem[..., 0], s, axis=1)
    prem[..., 2] = np.roll(prem[..., 2], -s, axis=1)
    glow = cv2.GaussianBlur(prem, (0, 0), sigmaX=max(2.0, h_t / 32))
    return prem + glow * 0.75


def projector(frame_f, x, y, h_t, accent, strength, t):
    """Glowing ring on the palm + a soft beam up through the hologram (additive)."""
    H, W = frame_f.shape[:2]
    rx, ry = h_t * 0.34, h_t * 0.085
    x0, x1 = int(max(x - rx * 1.5, 0)), int(min(x + rx * 1.5, W))
    y0, y1 = int(max(y - h_t * 0.95, 0)), int(min(y + ry * 2.5, H))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    acc = np.asarray(accent, np.float32)
    r = np.sqrt(((xx - x) / rx) ** 2 + ((yy - y) / ry) ** 2)
    ring = np.exp(-(((r - 1.0) / 0.12) ** 2)) * (0.75 + 0.25 * math.sin(t * 6)) + np.exp(-((r / 0.75) ** 2)) * 0.25
    rise = np.clip((y - yy) / (h_t * 0.95), 0, 1)
    halfw = rx * (1 + 0.35 * rise)
    beam = np.clip(1 - np.abs(xx - x) / halfw, 0, 1) ** 1.5 * (1 - rise) ** 1.2 * 0.22 * (yy <= y)
    light = (ring + beam) * strength
    frame_f[y0:y1, x0:x1] += (light[..., None] * acc) * (1 - frame_f[y0:y1, x0:x1])


def sparkles(cv2, frame_f, cx, cy, h_t, q, accent, seed=3):
    if not 0 <= q <= 1:
        return
    rng = np.random.default_rng(seed)
    acc = tuple(float(c) for c in accent)
    for _ in range(12):
        ang = rng.uniform(0, 2 * math.pi)
        r = h_t * (0.15 + rng.uniform(0.45, 0.8) * (1 - (1 - q) ** 2))
        x, y = cx + r * math.cos(ang), cy + r * math.sin(ang) * 0.8
        s = max(1.5, h_t * 0.045 * (1 - q) * rng.uniform(0.6, 1.2))
        a = (1 - q) * 0.9
        col = tuple(min(1.0, c * a + (1 - c) * a * 0.6) for c in acc)
        th = max(1, int(s / 3))
        cv2.line(frame_f, (int(x - s), int(y)), (int(x + s), int(y)), col, th, cv2.LINE_AA)
        cv2.line(frame_f, (int(x), int(y - s)), (int(x), int(y + s)), col, th, cv2.LINE_AA)


_BUBBLES = {}


def bubble(text, h_t, tail_side="left"):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        die("Speech bubbles need Pillow:  python -m pip install pillow")
    size = max(14, int(h_t * 0.11))
    key = (text, size, tail_side)
    if key in _BUBBLES:
        return _BUBBLES[key]
    fp = find_font()
    try:
        font = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
    except OSError:
        font = ImageFont.load_default()
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 18 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    probe_img = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = max(probe_img.textlength(line, font=font) for line in lines)
    lh = int(size * 1.25)
    pad = int(size * 0.6)
    bw, bh = int(tw + pad * 2), lh * len(lines) + pad * 2
    tail = int(size * 0.8)
    img = Image.new("RGBA", (bw + 4, bh + tail + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        [2, 2, bw, bh],
        radius=int(size * 0.7),
        fill=(255, 255, 255, 245),
        outline=(30, 30, 40, 255),
        width=max(2, size // 9),
    )
    if tail_side == "left":
        t0, t1, tip = int(size * 0.7), int(size * 0.7) + tail, int(size * 0.35)
    else:
        t0, t1, tip = bw - int(size * 0.7) - tail, bw - int(size * 0.7), bw - int(size * 0.35)
    d.polygon([(t0, bh - 2), (t1, bh - 2), (tip, bh + tail)], fill=(255, 255, 255, 245), outline=(30, 30, 40, 255))
    d.line([(t0 + 2, bh - 1), (t1 - 2, bh - 1)], fill=(255, 255, 255, 245), width=max(2, size // 9) + 1)
    for i, line in enumerate(lines):
        d.text((pad + 2, pad + 2 + i * lh), line, font=font, fill=(20, 20, 28, 255))
    arr = np.asarray(img).astype(np.float32) / 255
    arr[..., :3] *= arr[..., 3:]
    _BUBBLES[key] = arr
    return arr


def draw_debug(cv2, frame_u8, p, scale):
    for j, h in enumerate(p["hands"]):
        P = h["P"] * scale
        col = (255, 60, 60) if j == p["sel"] else (255, 220, 0)
        for a_, b_ in BONES:
            cv2.line(frame_u8, tuple(int(v) for v in P[a_]), tuple(int(v) for v in P[b_]), col, 2, cv2.LINE_AA)
    if p["x"] is not None:
        cv2.circle(frame_u8, (int(p["x"] * scale), int(p["y"] * scale)), 6, (0, 255, 120), -1, cv2.LINE_AA)


def voice_env(path, fps):
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "-",
        ],
        capture_output=True,
    )
    x = np.frombuffer(res.stdout, np.float32)
    if not len(x):
        die(f"Couldn't read audio from {path}")
    hop = int(16000 / fps)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    ref = np.percentile(rms, 95) or 1e-6
    env = np.clip((rms / ref) ** 0.7 * 1.15, 0, 1)
    env[env < 0.12] = 0
    return env


# ------------------------------------------------------------------ commands
def setup_args(a):
    a.color_rgb = art.hex_rgb(a.color, art.BODY) if a.color else None
    a.accent_rgb = art.hex_rgb(a.accent, art.ACCENT) if a.accent else art.ACCENT
    if a.style == "hologram" and not a.accent:
        a.accent_rgb = (0.35, 0.85, 1.0)
    if getattr(a, "anchor", None) == "fixed":
        try:
            a.pos = [float(v) for v in a.pos.split(",")][:2]
        except ValueError:
            die("--pos takes x,y as fractions of the frame, e.g. 0.5,0.8")
    a.says = []
    for s in getattr(a, "say", None) or []:
        if "@" not in s:
            die('--say takes "TEXT@START-END", e.g. "Hi!@1.0-2.5"')
        txt, rng_ = s.rsplit("@", 1)
        try:
            s0, s1 = [float(v) for v in rng_.split("-")]
        except ValueError:
            die(f"Bad --say times: {rng_}")
        a.says.append((txt.strip(), s0, s1))


def cmd_render(a):
    cv2 = cv2_or_die()
    setup_args(a)
    info = probe(a.video)
    if not info["has_video"]:
        die("No video stream.")
    W, H = info["width"], info["height"]
    fps = video_fps(info)
    n_est = int(info["duration"] * fps) + 2
    out = Path(a.out or Path(a.video).with_name(Path(a.video).stem + "_avatar.mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)
    track = None
    if a.anchor != "fixed":
        win = (max(0.0, (a.start or 0) - 1.0), (a.end + 0.5) if a.end is not None else None)
        track = load_or_track(a.video, info, fps, a.track or str(out.with_suffix(".track.json")), win)
        n_found = sum(1 for f in track["frames"] if f)
        if n_found == 0:
            die(
                "No hand found in this video. Tips: open palm toward the camera, good light, the whole hand "
                "in frame. Or place the avatar without tracking: --anchor fixed --pos 0.5,0.8"
            )
    n_plan = len(track["frames"]) if track and not a.end else n_est
    if track and a.end:
        n_plan = max(len(track["frames"]), int(a.end * fps) + 1)
    plans = plan_frames(track, n_plan, W, H, fps, a)
    if not any(p["shown"] for p in plans):
        die("The avatar never appears: check --start/--end (and with --summon, open your hand).")
    if a.preview:
        ow, oh = preview_size(W, H)
    else:
        ow, oh = W, H
    voice_at = a.voice_at if a.voice_at is not None else ((next(p["appear"] for p in plans if p["shown"]) or 0) + 0.6)
    scene = Scene(
        args=a,
        avatar=CustomAvatar(a.avatar, a.key, fps=fps) if a.avatar != "builtin" else BuiltinAvatar(),
        life=Life(dur=info["duration"] + 5),
        voice_env=voice_env(a.voice, fps) if a.voice else None,
        voice_at=voice_at,
        out_scale=ow / W,
        width=ow,
        height=oh,
        fps=fps,
    )
    enc = None if a.preview else hw_encoder()

    def render_pass(enc_):
        w = open_writer(out, ow, oh, fps, a.video, info["has_audio"], a.voice, voice_at, a.preview, enc_)
        n_done = 0
        try:
            for i, frame in enumerate(read_frames(a.video, fps, ow, oh)):
                p = plans[min(i, len(plans) - 1)]
                t = i / fps
                live = p["x"] is not None and (p["shown"] or (p["exit"] is not None and t - p["exit"] < 0.6))
                if live:
                    frame = frame.copy()
                    draw_frame(cv2, frame, i, p, scene)
                if a.debug:
                    frame = np.ascontiguousarray(frame) if frame.flags.writeable else frame.copy()
                    draw_debug(cv2, frame, p, scene.out_scale)
                w.stdin.write(np.ascontiguousarray(frame).tobytes())
                n_done += 1
                if i % max(1, int(fps * 5)) == 0:
                    print(f"  rendering {100 * i / max(len(plans), 1):3.0f}%", end="\r")
        except BrokenPipeError:
            pass
        finally:
            try:
                w.stdin.close()
            except BrokenPipeError:
                pass
            w.wait()
        print("  rendering 100%")
        return w.returncode == 0 and n_done > 0

    ok = render_pass(enc)
    if not ok and enc:
        print(f"  (GPU encoder {enc} failed on this render; using the CPU instead)")
        ok = render_pass(None)
    if not ok:
        die("Rendering failed.")
    check_sheet(cv2, out, plans, fps, Path(str(out.with_suffix("")) + "_check.jpg"))
    shown = [p for p in plans if p["shown"]]
    lost = sum(1 for p in shown[:-2] if not p["found"])
    print(f"Done -> {out}")
    print(
        f"  avatar on screen {len(shown) / fps:.1f}s"
        + (f", tracking held through {lost / fps:.1f}s of lost hand" if lost else "")
    )
    print(f"  check the placement: {Path(str(out.with_suffix('')) + '_check.jpg')}")


@dataclass
class Scene:
    """What draw_frame needs that stays the same for the whole render."""

    args: argparse.Namespace
    avatar: "BuiltinAvatar | CustomAvatar"
    life: "Life"
    voice_env: "np.ndarray | None"  # mouth openness per frame of the --voice line
    voice_at: float  # when the voice line starts, in seconds
    out_scale: float  # output pixels per source pixel (previews are smaller)
    width: int
    height: int
    fps: float


def draw_frame(cv2, frame, i, p, scene):
    """Draw the avatar (and its shadow, sparkles, bubble) into frame i, touching only the area around it.
    p is the frame's plan from plan_frames (position, size, motion, appear/exit times)."""
    a, sc, fps = scene.args, scene.out_scale, scene.fps
    ow, oh = scene.width, scene.height
    t = i / fps
    x, y, h_t = p["x"] * sc, p["y"] * sc, p["h"] * sc
    m_env = None
    if scene.voice_env is not None:
        k = int(round((t - scene.voice_at) * fps))
        m_env = scene.voice_env[k] if 0 <= k < len(scene.voice_env) else 0.0
    st, scale, breath, alpha = anim(t, p, a, scene.life, m_env)
    tl = t - (p["appear"] or 0)
    av = scene.avatar
    builtin = isinstance(av, BuiltinAvatar)
    spr, anc = av.sprite(st, h_t * max(scale, 0.05) * 1.05) if builtin else av.sprite(tl)
    sq = 1.0 if builtin else st.get("squash", 1.0)
    sxe = scale / math.sqrt(sq)
    sye = scale * breath * math.sqrt(sq)
    says = [(txt, s0, s1) for txt, s0, s1 in a.says if s0 <= t <= s1 and p["shown"]]
    bub = bubble(says[0][0], h_t) if says else None
    extra_h = bub.shape[0] if bub is not None else 0
    extra_w = bub.shape[1] if bub is not None else 0
    rx0 = int(max(x - 1.2 * h_t - extra_w, 0))
    rx1 = int(min(x + 1.2 * h_t + extra_w, ow))
    ry0 = int(max(y - 1.45 * h_t - extra_h, 0))
    ry1 = int(min(y + 0.45 * h_t, oh))
    if rx1 <= rx0 or ry1 <= ry0:
        return
    reg = frame[ry0:ry1, rx0:rx1].astype(np.float32) / 255
    RW, RH = rx1 - rx0, ry1 - ry0
    lx, ly = x - rx0, y - ry0
    if scale > 0.02 and alpha > 0.01:
        if a.style == "solid" and a.shadow > 0:
            contact_shadow(reg, lx, ly, h_t * 0.5 * scale, a.shadow * alpha)
        if a.style == "hologram":
            projector(reg, lx, ly, h_t * max(scale, 0.3), a.accent_rgb, alpha, t)
        if a.style == "solid":  # room for the motion blur
            pad = int(min(math.hypot(p["vx"], p["vy"]) * sc * 0.6, 31)) + 4
        else:  # room for the glow
            pad = int(h_t / 10) + 4
        roi, warped = place(cv2, spr, anc, (lx, ly), h_t, p["roll"], (sxe, sye), (RW, RH), pad=pad)
        if roi is not None:
            y0, y1, x0, x1 = roi
            if a.style == "hologram":
                reveal = min(max(tl, 0) / 0.6, 1.0) if p["shown"] else 1.0
                light = (
                    hologram(cv2, warped, (y0 + ry0, y1 + ry0, x0 + rx0, x1 + rx0), t, a.accent_rgb, h_t, reveal, y)
                    * alpha
                )
                region = reg[y0:y1, x0:x1]
                reg[y0:y1, x0:x1] = region + light * (1 - region)
            else:
                scene_match(reg, roi, warped, a.match, a.grain, i)
                soft = a.soften * min(ow, oh) / 1080
                if soft > 0.15:  # real footage is never perfectly crisp: avoid the pasted-on look
                    warped = cv2.GaussianBlur(warped, (0, 0), sigmaX=soft)
                warped = motion_blur(cv2, warped, p["vx"] * sc, p["vy"] * sc)
                warped *= alpha
                region = reg[y0:y1, x0:x1]
                reg[y0:y1, x0:x1] = warped[..., :3] + region * (1 - warped[..., 3:])
    if tl < 0.55:
        sparkles(cv2, reg, lx, ly - h_t * 0.45, h_t, tl / 0.55, a.accent_rgb)
    if not p["shown"] and p["exit"] is not None and t - p["exit"] < 0.55:
        sparkles(cv2, reg, lx, ly - h_t * 0.45, h_t, (t - p["exit"]) / 0.55, a.accent_rgb, seed=5)
    if bub is not None:
        txt, s0, s1 = says[0]
        pop = min((t - s0) / 0.15, 1.0) * min((s1 - t) / 0.15, 1.0)
        bh, bw = bub.shape[:2]
        bx = int(x + h_t * 0.3)
        if bx + bw > ow:  # no room on the right: put it on the left, tail pointing right
            bub = bubble(txt, h_t, "right")
            bx = int(x - h_t * 0.3 - bw)
        by_ = int(y - h_t * 1.02 - bh * 0.55)
        bx, by_ = min(max(bx, 0), ow - bw), min(max(by_, 0), oh - bh)
        lbx, lby = bx - rx0, by_ - ry0
        cx0, cy0 = max(lbx, 0), max(lby, 0)
        cx1, cy1 = min(lbx + bw, RW), min(lby + bh, RH)
        if cx1 > cx0 and cy1 > cy0:
            bb = bub[cy0 - lby : cy1 - lby, cx0 - lbx : cx1 - lbx] * max(pop, 0)
            r2 = reg[cy0:cy1, cx0:cx1]
            reg[cy0:cy1, cx0:cx1] = bb[..., :3] + r2 * (1 - bb[..., 3:])
    frame[ry0:ry1, rx0:rx1] = (np.clip(reg, 0, 1) * 255 + 0.5).astype(np.uint8)


def label(cv2, img, text):
    cv2.putText(img, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(img, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)


def check_sheet(cv2, video, plans, fps, out_path, n=8):
    idx = [i for i, p in enumerate(plans) if p["shown"] and i < len(plans) - 3] or list(range(len(plans)))
    picks = [idx[int(k * (len(idx) - 1) / max(n - 1, 1))] for k in range(n)] if idx else []
    tiles = []
    for i in picks:
        res = subprocess.run(
            [
                need("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{i / fps:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=-2:360",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            capture_output=True,
        )
        if res.stdout:
            img = cv2.imdecode(np.frombuffer(res.stdout, np.uint8), cv2.IMREAD_COLOR)
            label(cv2, img, f"{i / fps:.1f}s")
            tiles.append(img)
    if tiles:
        h = min(t.shape[0] for t in tiles)
        tiles = [t[:h] for t in tiles]
        rows = [np.concatenate(tiles[r : r + 4], axis=1) for r in range(0, len(tiles), 4)]
        wmax = max(r.shape[1] for r in rows)
        rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
        cv2.imwrite(str(out_path), np.concatenate(rows, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 88])


def cmd_check(a):
    cv2 = cv2_or_die()
    info = probe(a.video)
    W, H = info["width"], info["height"]
    fps = video_fps(info)
    od = Path(a.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    tr_path = od / (Path(a.video).stem + ".track.json")
    track = load_or_track(a.video, info, fps, str(tr_path), (0.0, None))
    fr = track["frames"]
    n = len(fr)
    with_hand = [i for i, f in enumerate(fr) if f]
    pct = 100 * len(with_hand) / max(n, 1)
    print(f"\nHand visible in {pct:.0f}% of the video ({len(with_hand) / fps:.1f}s of {n / fps:.1f}s).")
    if not with_hand:
        print("No hand found. Open palm toward the camera, good light, whole hand in frame; or use --anchor fixed.")
        return
    first, last = with_hand[0] / fps, with_hand[-1] / fps
    ms = [metrics(f[0]["lm"], W, H) for f in fr if f]
    sizes = np.array([m["size"] for m in ms])
    opens = np.array([m["is_open"] for m in ms])
    fists = np.array([m["is_fist"] for m in ms])
    two = sum(1 for f in fr if len(f) > 1)
    print(f"First seen at {first:.1f}s, last at {last:.1f}s. Two hands in {100 * two / max(n, 1):.0f}% of frames.")
    print(
        f"Palm size: about {100 * np.median(sizes) / H:.0f}% of the frame height, so the avatar will be about "
        f"{100 * 1.35 * np.median(sizes) / H:.0f}% tall at --size 1."
    )
    print(
        f"Open hand (3+ fingers out) {100 * np.mean(opens):.0f}% of the time, fist {100 * np.mean(fists):.0f}%."
        + (" --summon needs both: open to show the avatar, a fist to hide it." if not fists.any() else "")
    )
    # sheet of frames with the tracking drawn on
    a2 = argparse.Namespace(
        anchor="palm", hand=a.hand, size=1.0, start=0.0, end=None, summon=False, tilt=0.5, boop=False, pos="0.5,0.8"
    )
    plans = plan_frames(track, n, W, H, fps, a2)
    usable = [i for i in with_hand if i < n - 2] or with_hand
    picks = [usable[int(k * (len(usable) - 1) / 7)] for k in range(8)]
    tiles = []
    th = 360
    for i in picks:
        res = subprocess.run(
            [
                need("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{i / fps:.3f}",
                "-i",
                str(a.video),
                "-frames:v",
                "1",
                "-vf",
                f"scale=-2:{th}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            capture_output=True,
        )
        w2 = len(res.stdout) // (th * 3)
        if not w2:
            continue
        img = np.frombuffer(res.stdout[: w2 * th * 3], np.uint8).reshape(th, w2, 3).copy()
        draw_debug(cv2, img, plans[i], w2 / W)
        label(cv2, img, f"{i / fps:.1f}s")
        tiles.append(img)
    if tiles:
        h = min(t.shape[0] for t in tiles)
        rows = [np.concatenate([t[:h] for t in tiles[r : r + 4]], axis=1) for r in range(0, len(tiles), 4)]
        wmax = max(r.shape[1] for r in rows)
        rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
        sheet = od / (Path(a.video).stem + "_hands.jpg")
        cv2.imwrite(
            str(sheet), cv2.cvtColor(np.concatenate(rows, 0), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88]
        )
        print(f"Tracking sheet -> {sheet} (red = the hand the avatar follows, green dot = where it stands)")
    print(f"Track saved -> {tr_path} (pass --track to render to skip re-tracking)")


def cmd_look(a):
    cv2 = cv2_or_die()
    setup_args(a)
    states = [
        ({}, "hello"),
        ({"expr": "happy", "wave": 1, "wave_phase": 0.1}, "wave"),
        ({"mouth": 0.8}, "talk"),
        ({"blink": 1}, "blink"),
        ({"expr": "squeeze", "squash": 0.8}, "boop!"),
        ({"expr": "heart"}, "love"),
        ({"expr": "surprised", "squash": 1.12}, "wow"),
    ]
    tiles = []
    for st, label in states:
        st = dict(st, accent=a.accent_rgb, color=a.color_rgb)
        img = art.render(st, 300)
        h, w = img.shape[:2]
        if a.style == "hologram":
            bg = np.full((h + 40, w + 20, 3), (0.08, 0.09, 0.12), np.float32)
            roi = (20, 20 + h, 10, 10 + w)
            light = hologram(cv2, img.copy(), roi, 0.3, a.accent_rgb, h)
            region = bg[20 : 20 + h, 10 : 10 + w]
            bg[20 : 20 + h, 10 : 10 + w] = region + light * (1 - region)
        else:
            bg = np.zeros((h + 40, w + 20, 3), np.float32)
            bg[:] = np.linspace(0.62, 0.42, h + 40)[:, None, None] * np.float32([0.95, 0.9, 0.85])
            region = bg[20 : 20 + h, 10 : 10 + w]
            bg[20 : 20 + h, 10 : 10 + w] = img[..., :3] + region * (1 - img[..., 3:])
        u8 = (np.clip(bg, 0, 1) * 255).astype(np.uint8)
        cv2.putText(u8, label, (12, h + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(u8)
    sheet = np.concatenate(tiles, axis=1)
    cv2.imwrite(a.out, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(f"{Path(a.out).resolve()}")


def add_look_args(p):
    p.add_argument("--style", choices=["solid", "hologram"], default="solid")
    p.add_argument("--color", help="body colour, e.g. #F4F1EA")
    p.add_argument("--accent", help="accent colour (eyes, antenna, glow), e.g. #22D3EE")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("look")
    add_look_args(p)
    p.add_argument("--out", default="avatar_look.png")
    p = sub.add_parser("check")
    p.add_argument("video")
    p.add_argument("--out-dir", default="avatar")
    p.add_argument("--hand", choices=["auto", "left-side", "right-side"], default="auto")
    p = sub.add_parser("render")
    p.add_argument("video")
    p.add_argument("--out")
    p.add_argument("--avatar", default="builtin")
    add_look_args(p)
    p.add_argument("--size", type=float, default=1.0)
    p.add_argument("--anchor", choices=["palm", "above", "finger", "fixed"], default="palm")
    p.add_argument("--pos", default="0.5,0.8")
    p.add_argument("--hand", choices=["auto", "left-side", "right-side"], default="auto")
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--tilt", type=float, default=0.5)
    p.add_argument("--no-wave", dest="wave", action="store_false")
    p.add_argument("--no-boop", dest="boop", action="store_false")
    p.add_argument("--summon", action="store_true")
    p.add_argument("--voice")
    p.add_argument("--voice-at", type=float)
    p.add_argument("--say", nargs="*")
    p.add_argument("--key", choices=["auto", "green", "blue", "none"], default="auto")
    p.add_argument("--shadow", type=float, default=0.45)
    p.add_argument("--match", type=float, default=0.3)
    p.add_argument("--no-grain", dest="grain", action="store_false")
    p.add_argument(
        "--soften", type=float, default=0.6, help="blur the avatar slightly to match the footage (px at 1080p)"
    )
    p.add_argument("--preview", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--track")
    a = ap.parse_args()
    {"look": cmd_look, "check": cmd_check, "render": cmd_render}[a.cmd](a)
