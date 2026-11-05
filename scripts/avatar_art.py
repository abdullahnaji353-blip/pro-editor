"""The built-in avatar: an original little TV-head robot, drawn from code (signed distance fields),
so it stays smooth at any size and can animate freely (blink, wave, talk, react, squash and stretch).

render(state, height) -> float32 RGBA image (premultiplied alpha), feet at the bottom centre.
state keys (all optional): bob, squash, wave, wave_phase, blink, look, mouth, expr, antenna,
color, accent (RGB tuples 0-1). expr: normal | happy | squeeze | surprised | heart.
"""

import math

import numpy as np

# default palette: warm white body, cyan accent (both can be overridden per render)
BODY = (0.95, 0.93, 0.89)
ACCENT = (0.13, 0.83, 0.93)
JOINT = (0.36, 0.38, 0.44)
SCREEN = (0.06, 0.08, 0.13)

ASPECT = 0.82  # sprite width / height
UNITS = 10.4  # sprite height in character units (leaves headroom for stretch and glow)
FEET_PAD = 0.035  # space below the feet, as a fraction of the height


def hex_rgb(s, default):
    if not s:
        return default
    s = s.strip().lstrip("#")
    if len(s) != 6:
        return default
    try:
        return tuple(int(s[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return default


# ------------------------------------------------------------------ distance functions (pixels)
def sd_round_box(X, Y, cx, cy, hw, hh, r):
    r = min(r, hw, hh)
    qx = np.abs(X - cx) - hw + r
    qy = np.abs(Y - cy) - hh + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_capsule(X, Y, ax, ay, bx, by, r):
    pax, pay, bax, bay = X - ax, Y - ay, bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / max(bax * bax + bay * bay, 1e-6), 0, 1)
    return np.hypot(pax - bax * h, pay - bay * h) - r


def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_ellipse(X, Y, cx, cy, rx, ry):
    k = np.hypot((X - cx) / max(rx, 1e-3), (Y - cy) / max(ry, 1e-3))
    return (k - 1) * min(rx, ry)


def cover(d, soft=1.0):
    return np.clip(0.5 - d / soft, 0, 1).astype(np.float32)


def shaded(d, Y, top, bottom, base, rim=0.22, light=0.18):
    """Toy-like shading: brighter toward the top and the middle, darker at the rim."""
    depth = np.clip(-d / max((bottom - top) * 0.35, 1), 0, 1)
    vert = np.clip((Y - top) / max(bottom - top, 1), 0, 1)
    lum = 1.0 - rim * (1 - np.sqrt(depth)) + light * (0.5 - vert)
    return np.clip(np.asarray(base, np.float32) * lum[..., None], 0, 1)


class Canvas:
    """Premultiplied RGB + alpha canvas that only touches the region a part covers.
    Glows are pure added light: they brighten without hiding what's behind them."""

    def __init__(self, w, h, fx, fy, sx, sy):
        self.w, self.h = w, h
        self.fx, self.fy, self.sx, self.sy = fx, fy, sx, sy
        self.p = np.zeros((h, w, 3), np.float32)
        self.a = np.zeros((h, w), np.float32)

    def region(self, x0, y0, x1, y1):
        """Character-space box -> (slice, X, Y) of the pixels it covers."""
        px0 = int(math.floor(self.fx + min(x0, x1) * self.sx)) - 2
        px1 = int(math.ceil(self.fx + max(x0, x1) * self.sx)) + 3
        py0 = int(math.floor(self.fy + min(y0, y1) * self.sy)) - 2
        py1 = int(math.ceil(self.fy + max(y0, y1) * self.sy)) + 3
        px0, py0 = max(px0, 0), max(py0, 0)
        px1, py1 = min(px1, self.w), min(py1, self.h)
        if px1 <= px0 or py1 <= py0:
            return None
        ys, xs = np.mgrid[py0:py1, px0:px1].astype(np.float32)
        return (slice(py0, py1), slice(px0, px1)), (xs - self.fx) / self.sx, (ys - self.fy) / self.sy

    def over(self, sl, alpha, color):
        alpha = np.clip(alpha, 0, 1)[..., None]
        col = np.asarray(color, np.float32)
        self.p[sl] = col * alpha + self.p[sl] * (1 - alpha)
        self.a[sl] = alpha[..., 0] + self.a[sl] * (1 - alpha[..., 0])

    def add(self, sl, alpha, color):
        alpha = np.clip(alpha, 0, 1)[..., None]
        self.p[sl] = self.p[sl] + np.asarray(color, np.float32) * alpha


def falloff(d, width, reach):
    """Soft glow that reaches exactly zero at `reach` (so it never shows a box edge)."""
    d = np.clip(d, 0, None)
    return np.exp(-d / width) * np.clip(1 - d / reach, 0, 1) ** 2


def render(state=None, height=480):
    s = dict(state or {})
    H = int(height)
    W = int(round(H * ASPECT))
    u = H / UNITS
    body_c = s.get("color") or BODY
    acc = s.get("accent") or ACCENT
    dark_acc = tuple(c * 0.55 for c in acc)
    outline = tuple(c * 0.5 for c in body_c)

    sq = float(s.get("squash", 1.0))  # <1 squashed, >1 stretched (volume kept)
    sx, sy = 1 / math.sqrt(sq), math.sqrt(sq)
    fx, fy = W / 2, H - FEET_PAD * H  # feet origin
    bob = float(s.get("bob", 0.0)) * u
    cv = Canvas(W, H, fx, fy, sx, sy)
    aa = 1.0 / min(sx, sy)

    def part(x0, y0, x1, y1):
        return cv.region(x0, y0, x1, y1)

    # ---- legs and feet (stay planted; the rest bobs above them)
    for side in (-1, 1):
        hip = (side * 0.62 * u, -1.75 * u + bob * 0.5)
        foot = (side * 0.62 * u, -0.45 * u)
        r = part(side * 0.62 * u - 0.4 * u, hip[1] - 0.4 * u, side * 0.62 * u + 0.4 * u, foot[1] + 0.4 * u)
        if r:
            sl, X, Y = r
            d = sd_capsule(X, Y, *hip, *foot, 0.30 * u)
            cv.over(sl, cover(d, aa), shaded(d, Y, hip[1], foot[1], JOINT, rim=0.3))
        r = part(side * 0.70 * u - 0.55 * u, -0.6 * u, side * 0.70 * u + 0.55 * u, 0.05 * u)
        if r:
            sl, X, Y = r
            d = sd_round_box(X, Y, side * 0.70 * u, -0.27 * u, 0.48 * u, 0.27 * u, 0.25 * u)
            cv.over(sl, cover(d, aa), shaded(d, Y, -0.55 * u, 0, dark_acc, rim=0.3))

    # ---- arms: the hanging arm is drawn behind the body, a waving arm in front of it
    wave = float(np.clip(s.get("wave", 0.0), 0, 1))
    t_wave = float(s.get("wave_phase", 0.0))
    arms = []
    for side in (-1, 1):
        sh = (side * 1.15 * u, -3.35 * u + bob)
        L = 1.35 * u
        if side == 1 and wave > 0:
            ang = math.radians(-15 - 55 * wave + 20 * wave * math.sin(t_wave * 2 * math.pi * 2.2))
            hand = (sh[0] + L * math.cos(ang), sh[1] + L * math.sin(ang))
        else:
            hand = (sh[0] + side * L * 0.32, sh[1] + L * 0.95)
        arms.append((side, sh, hand, side == 1 and wave > 0))

    def draw_arm(sh, hand):
        r = part(
            min(sh[0], hand[0]) - 0.5 * u,
            min(sh[1], hand[1]) - 0.5 * u,
            max(sh[0], hand[0]) + 0.5 * u,
            max(sh[1], hand[1]) + 0.5 * u,
        )
        if not r:
            return
        sl, X, Y = r
        d = sd_capsule(X, Y, *sh, *hand, 0.26 * u)
        cv.over(sl, cover(d, aa), shaded(d, Y, sh[1] - u, hand[1] + u, body_c, rim=0.3))
        d = sd_circle(X, Y, *hand, 0.36 * u)
        cv.over(sl, cover(d, aa), shaded(d, Y, hand[1] - 0.4 * u, hand[1] + 0.4 * u, JOINT, rim=0.3))

    for _side, sh, hand, front in arms:
        if not front:
            draw_arm(sh, hand)

    # ---- body
    by = -2.7 * u + bob
    r = part(-1.5 * u, by - 1.3 * u, 1.5 * u, by + 1.3 * u)
    if r:
        sl, X, Y = r
        d = sd_round_box(X, Y, 0, by, 1.25 * u, 1.05 * u, 0.62 * u)
        cv.over(sl, cover(d + 1.2 * aa, aa), outline)
        cv.over(sl, cover(d, aa), shaded(d, Y, by - 1.05 * u, by + 1.05 * u, body_c))
        dc = sd_circle(X, Y, 0, by - 0.1 * u, 0.32 * u)
        cv.over(sl, cover(dc, aa), dark_acc)
        cv.add(sl, cover(dc + 0.08 * u, aa) * 0.9, acc)
        cv.add(sl, falloff(dc, 0.35 * u, 0.9 * u) * 0.35 * (dc > 0) * (d < 0), acc)

    # ---- neck + head
    hy = -5.45 * u + bob * 1.1
    r = part(-0.6 * u, -4.3 * u + bob, 0.6 * u, -3.5 * u + bob)
    if r:
        sl, X, Y = r
        d = sd_round_box(X, Y, 0, -3.9 * u + bob, 0.45 * u, 0.3 * u, 0.15 * u)
        cv.over(sl, cover(d, aa), shaded(d, Y, -4.2 * u, -3.6 * u, JOINT))
    for side in (-1, 1):  # side bolts
        r = part(side * 2.12 * u - 0.35 * u, hy - 0.6 * u, side * 2.12 * u + 0.35 * u, hy + 0.8 * u)
        if r:
            sl, X, Y = r
            d = sd_round_box(X, Y, side * 2.12 * u, hy + 0.1 * u, 0.22 * u, 0.42 * u, 0.18 * u)
            cv.over(sl, cover(d, aa), shaded(d, Y, hy - 0.5 * u, hy + 0.6 * u, dark_acc))

    r = part(-2.3 * u, hy - 1.9 * u, 2.3 * u, hy + 1.9 * u)
    if r:
        sl, X, Y = r
        d_head = sd_round_box(X, Y, 0, hy, 2.05 * u, 1.62 * u, 0.85 * u)
        cv.over(sl, cover(d_head + 1.4 * aa, aa), outline)
        cv.over(sl, cover(d_head, aa), shaded(d_head, Y, hy - 1.62 * u, hy + 1.62 * u, body_c))

        # screen face
        d_scr = sd_round_box(X, Y, 0, hy + 0.08 * u, 1.62 * u, 1.18 * u, 0.62 * u)
        inside = (d_scr < 0).astype(np.float32)
        grad = 1 + 0.6 * np.clip((Y - (hy - u)) / (2.4 * u), 0, 1)
        cv.over(sl, cover(d_scr, aa), np.asarray(SCREEN, np.float32) * grad[..., None])
        d_ref = sd_capsule(X, Y, -1.1 * u, hy - 0.55 * u, -0.35 * u, hy - 0.85 * u, 0.12 * u)
        cv.over(sl, cover(d_ref, aa) * 0.35 * inside, (1, 1, 1))

        # eyes
        blink = float(np.clip(s.get("blink", 0.0), 0, 1))
        look = float(s.get("look", 0.0)) * 0.25 * u
        expr = s.get("expr", "normal")
        ey = hy - 0.12 * u
        glow = np.zeros_like(X)
        for side in (-1, 1):
            ex = side * 0.68 * u + look
            if expr == "happy":  # ^ ^ arcs
                d_e = np.abs(sd_circle(X, Y, ex, ey + 0.25 * u, 0.36 * u)) - 0.09 * u
                d_e = np.maximum(d_e, -(ey + 0.12 * u - Y))
            elif expr == "squeeze":  # > < squeezed shut
                k = -side
                d1 = sd_capsule(X, Y, ex - 0.28 * u * k, ey - 0.22 * u, ex + 0.22 * u * k, ey, 0.08 * u)
                d2 = sd_capsule(X, Y, ex + 0.22 * u * k, ey, ex - 0.28 * u * k, ey + 0.22 * u, 0.08 * u)
                d_e = np.minimum(d1, d2)
            elif expr == "heart":
                hx, hy2 = (X - ex) / (0.42 * u), (Y - ey) / (0.42 * u)
                d_e = np.minimum(np.hypot(hx + 0.35, hy2 + 0.25), np.hypot(hx - 0.35, hy2 + 0.25)) - 0.4
                d_e = np.minimum(d_e, np.maximum(np.abs(hx) + (hy2 + 0.1) * 0.95 - 0.75, -0.2 - hy2)) * 0.42 * u
            else:
                open_h = max(0.42 * u * (1 - blink), 0.07 * u)
                if expr == "surprised":
                    d_e = sd_ellipse(X, Y, ex, ey, 0.36 * u, max(open_h * 1.05, 0.07 * u))
                else:
                    d_e = sd_round_box(X, Y, ex, ey, 0.21 * u, open_h, 0.2 * u)
            cv.over(sl, cover(d_e, aa) * inside, acc)
            glow = np.maximum(glow, falloff(d_e, 0.22 * u, 0.7 * u) * (d_e > 0))
        cv.add(sl, glow * 0.45 * inside, acc)

        # mouth
        mouth = float(np.clip(s.get("mouth", 0.0), 0, 1))
        my = hy + 0.62 * u
        if mouth > 0.05:
            d_m = sd_ellipse(X, Y, look * 0.5, my, 0.26 * u, 0.06 * u + 0.24 * u * mouth)
        else:
            d_m = np.abs(sd_circle(X, Y, look * 0.5, my - 0.28 * u, 0.34 * u)) - 0.055 * u
            d_m = np.maximum(d_m, -(Y - (my - 0.08 * u)))
        cv.over(sl, cover(d_m, aa) * inside, acc)
        for side in (-1, 1):  # cheeks
            d_c = sd_ellipse(X, Y, side * 1.12 * u, my - 0.05 * u, 0.2 * u, 0.12 * u)
            cv.over(sl, cover(d_c, 2 * aa) * 0.45 * inside, (1.0, 0.45, 0.6))
        d_hl = sd_capsule(X, Y, -1.45 * u, hy - 1.2 * u, -0.6 * u, hy - 1.42 * u, 0.12 * u)
        cv.over(sl, cover(d_hl, 2 * aa) * 0.55, (1, 1, 1))

    # ---- antenna (lags behind the bob: secondary motion)
    lean = float(s.get("antenna", 0.0)) * 0.5 * u
    top = (lean, hy - 2.55 * u)
    base = (0, hy - 1.55 * u)
    r = part(min(0, lean) - 0.8 * u, top[1] - 0.8 * u, max(0, lean) + 0.8 * u, base[1] + 0.1 * u)
    if r:
        sl, X, Y = r
        d = sd_capsule(X, Y, *base, *top, 0.09 * u)
        cv.over(sl, cover(d, aa), JOINT)
        d = sd_circle(X, Y, *top, 0.3 * u)
        cv.add(sl, falloff(d, 0.18 * u, 0.42 * u) * 0.55 * (d > 0), acc)
        cv.over(sl, cover(d, aa), shaded(d, Y, top[1] - 0.3 * u, top[1] + 0.3 * u, acc, rim=0.15))
        d = sd_circle(X, Y, top[0] - 0.1 * u, top[1] - 0.1 * u, 0.08 * u)
        cv.over(sl, cover(d, aa) * 0.8, (1, 1, 1))

    for _side, sh, hand, front in arms:
        if front:
            draw_arm(sh, hand)

    out = np.empty((H, W, 4), np.float32)
    out[..., :3] = cv.p  # premultiplied (glows may exceed alpha: added light)
    out[..., 3] = cv.a
    return out


def size_for(height):
    H = int(height)
    return int(round(H * ASPECT)), H


def anchor_px(height):
    """Feet position inside the sprite, in pixels (x, y)."""
    W, H = size_for(height)
    return W / 2, H - FEET_PAD * H


if __name__ == "__main__":
    import sys

    from PIL import Image

    states = [
        {},
        {"blink": 1},
        {"expr": "happy"},
        {"wave": 1, "wave_phase": 0.1},
        {"mouth": 0.8},
        {"expr": "squeeze", "squash": 0.8},
        {"expr": "surprised", "squash": 1.15},
        {"expr": "heart"},
    ]
    tiles = []
    for st in states:
        img = render(st, 360)
        rgb = img[..., :3] + (1 - img[..., 3:]) * np.array([0.35, 0.4, 0.45], np.float32)
        tiles.append((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    Image.fromarray(np.concatenate(tiles, axis=1)).save(sys.argv[1] if len(sys.argv) > 1 else "avatar_sheet.png")
