"""Vertical-video layout helpers: HUD insets, a measuring grid, platform safe zones, text placement.

Commands:
  python layout.py grid VIDEO@SECONDS [--out grid.png]
      Frame with a labelled 10% grid. Read off where a HUD element sits (kill feed, minimap,
      scoreboard) as fractions x,y,w,h for a custom HUD region. HUD positions change with game
      settings and seasons, so measure on the user's own footage.
  python layout.py safe VIDEO@SECONDS [--platform tiktok|reels|shorts] [--out safe.png]
      Frame with the platform's UI dead zones shaded red, to check text and HUD insets.

HUD regions (recipe "layout": {"fit": "hud", "hud": [...], "hud_place": "top"|"bottom"}):
  presets:  rl-scoreboard (top centre), rl-boost (bottom right), fortnite-minimap (top right)
  custom:   {"x": 0.02, "y": 0.55, "w": 0.30, "h": 0.18, "scale": 0.6}   (fractions of the source)
Presets are approximate defaults for standard HUD settings; check with `grid` first.
"""

import argparse
from pathlib import Path

from common import die, ff_path, ffmpeg, find_font

HUD_PRESETS = {
    # Rocket League: scoreboard/clock top centre, boost meter bottom right (standard HUD).
    "rl-scoreboard": {"x": 0.36, "y": 0.00, "w": 0.28, "h": 0.10, "scale": 0.55},
    "rl-boost": {"x": 0.82, "y": 0.68, "w": 0.17, "h": 0.30, "scale": 0.30},
    # Fortnite: minimap top right (approximate; HUD layout is customisable).
    "fortnite-minimap": {"x": 0.82, "y": 0.02, "w": 0.17, "h": 0.30, "scale": 0.32},
}

# Dead zones on a 1080x1920 frame: (top, bottom, left, right) px. Conservative estimates; the apps
# change their UI often.
SAFE = {"tiktok": (108, 320, 60, 120), "reels": (210, 310, 0, 84), "shorts": (120, 300, 0, 96)}


def resolve_regions(spec):
    out = []
    for r in spec or []:
        if isinstance(r, str):
            r = {"preset": r}
        base = dict(HUD_PRESETS.get(r.get("preset", ""), {}))
        if r.get("preset") and not base:
            die(f"Unknown HUD preset '{r['preset']}'. Known: {', '.join(HUD_PRESETS)}")
        base.update({k: v for k, v in r.items() if k != "preset"})
        for k in ("x", "y", "w", "h"):
            if k not in base:
                die(f"HUD region needs x, y, w, h (fractions): {r}")
        base.setdefault("scale", 0.5)
        out.append(base)
    return out


def safe_margins(W, H, platform="tiktok"):
    top, bottom, left, right = SAFE.get(platform, SAFE["tiktok"])
    sx, sy = W / 1080, H / 1920
    return int(top * sy), int(bottom * sy), int(left * sx), int(right * sx)


def center_crop(W, H):
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"


def hud_graph(W, H, regions, place="top", effects=""):
    """Filtergraph body for -vf: centre crop (+effects) with HUD regions stacked on top, untouched by
    the effects. Starts from the unlabelled input and ends unlabelled, so it can sit inside a chain."""
    n = len(regions)
    labels = "".join(f"[h{i}]" for i in range(n))
    g = f"split={n + 1}[m]{labels};[m]{center_crop(W, H)}{(',' + effects) if effects else ''}[base]"
    widths = [max(16, int(W * float(r["scale"])) // 2 * 2) for r in regions]
    maxw = max(widths) + 6
    for i, (r, ow) in enumerate(zip(regions, widths)):
        g += (
            f";[h{i}]crop=iw*{r['w']}:ih*{r['h']}:iw*{r['x']}:ih*{r['y']},scale={ow}:-2,"
            f"pad=iw+6:ih+6:3:3:color=black,format=rgba,"
            f"pad={maxw}:ih+10:(ow-iw)/2:0:color=black@0[o{i}]"
        )
    if n > 1:
        g += ";" + "".join(f"[o{i}]" for i in range(n)) + f"vstack=inputs={n}[hud]"
    else:
        g += ";[o0]null[hud]"
    if H > W:
        top, bottom, _, _ = safe_margins(W, H)
    else:
        top = bottom = int(H * 0.03)
    y = f"{top + int(H * 0.01)}" if place == "top" else f"H-{bottom + int(H * 0.01)}-h"
    g += f";[base][hud]overlay=(W-w)/2:{y},format=yuv420p"
    return g


def text_size(W, H, text, scale=1.0):
    """Big but always inside the safe area (about 78% of the width at most)."""
    return int(min(H * 0.07, 1.15 * W / max(len(str(text)), 1)) * scale)


def text_y(position, W, H):
    vertical = H > W
    top = f"h*{0.12 if vertical else 0.08}"
    bottom = "h*0.70" if vertical else "h*0.80"  # vertical: stays above the app's caption/button zone
    return {"top": top, "center": "(h-text_h)/2", "bottom": bottom}.get(position, top)


def _frame(target):
    if "@" not in target:
        die("Use VIDEO@SECONDS, e.g. match.mp4@83.5")
    v, t = target.rsplit("@", 1)
    return v, t


def cmd_grid(a):
    v, t = _frame(a.frame)
    font = find_font()
    lab = ""
    if font:
        fp = ff_path(font)
        for i in range(1, 10):
            lab += (
                f",drawtext=fontfile='{fp}':text='{i * 10}':fontsize=22:fontcolor=yellow:borderw=2:"
                f"x=w*{i / 10}+4:y=4,drawtext=fontfile='{fp}':text='{i * 10}':fontsize=22:fontcolor=yellow:"
                f"borderw=2:x=4:y=h*{i / 10}+4"
            )
    ffmpeg(
        [
            "-ss",
            t,
            "-i",
            v,
            "-frames:v",
            "1",
            "-vf",
            f"scale=1280:-2,drawgrid=w=iw/10:h=ih/10:t=1:c=yellow@0.6{lab}",
            str(a.out),
        ]
    )
    print(f"{Path(a.out).resolve()}\n  Lines every 10% of width/height. Region = x,y (top-left) and w,h as fractions.")


def cmd_safe(a):
    v, t = _frame(a.frame)
    W, H = 1080, 1920
    top, bottom, left, right = SAFE[a.platform]
    boxes = (
        f"drawbox=x=0:y=0:w={W}:h={top}:color=red@0.35:t=fill,"
        f"drawbox=x=0:y={H - bottom}:w={W}:h={bottom}:color=red@0.35:t=fill,"
        f"drawbox=x={W - right}:y=0:w={right}:h={H}:color=red@0.35:t=fill"
    )
    if left:
        boxes += f",drawbox=x=0:y=0:w={left}:h={H}:color=red@0.35:t=fill"
    ffmpeg(
        [
            "-ss",
            t,
            "-i",
            v,
            "-frames:v",
            "1",
            "-vf",
            f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{boxes}",
            str(a.out),
        ]
    )
    print(
        f"{Path(a.out).resolve()}\n  Red = covered by {a.platform}'s buttons/captions. "
        "Keep text and HUD insets out of it."
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("grid")
    p.add_argument("frame")
    p.add_argument("--out", default="grid.png")
    p = sub.add_parser("safe")
    p.add_argument("frame")
    p.add_argument("--platform", choices=list(SAFE), default="tiktok")
    p.add_argument("--out", default="safe.png")
    a = ap.parse_args()
    {"grid": cmd_grid, "safe": cmd_safe}[a.cmd](a)
