"""Cut gameplay clips to a song's beat using a style recipe, render an MP4 + editable timeline.

Usage:
  python build_montage.py --song SONG (--clips FILES_OR_FOLDERS... | --highlights highlights.json)
                          [--recipe recipe.json] [--song-start SEC] [--length SEC]
                          [--fit crop|blur] [--shuffle] [--seed N]
                          [--out montage.mp4] [--plan-out plan.json] [--xml-out montage.xml]
                          [--plan-only] [--preview] [--fade-in SEC] [--fade-out SEC]

--plan-only  writes plan.json + XML without rendering (instant structure check).
--preview    renders at half resolution, 30fps, fast settings: seconds instead of minutes.
             Same cuts and effects as the full render, so approve the preview then re-run without it.

Effects (recipe["effects"]): zoom punch, flash, shake, RGB split, velocity speed ramps with
motion blur, smooth slow-mo on drops, letterbox, text overlays, plus a color grade toward the
recipe's brightness/saturation/contrast. recipe["audio"]["game_audio_volume"] mixes the clips'
own sound (kills, goal explosions) under the song.
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor
import random
import statistics as st
import tempfile
from pathlib import Path

from common import (VIDEO_EXTS, blur_radius, collect_media, concat_line, die, ff_path, ffmpeg, find_font,
                    frame_size, load_json, preview_size, resolve_res,
                    normalize_loudness, probe, save_json)

DEFAULT_RECIPE = {
    "name": "default",
    "format": {"aspect": "16:9", "fps": 60},
    "pacing": {"cut_every_beats": 2, "snap_cuts_to_beats": True, "median_shot_sec": 1.0},
    "color": {"brightness": None, "saturation": None, "contrast": None},
    "effects": {"flash_on_strong_beats": False, "flash_color": "white", "zoom_punch_on_beats": True,
                "zoom_amount": 1.12, "shake_on_drops": True, "slowmo_on_drops": True,
                "slowmo_speed": 0.5, "letterbox": False, "text_overlays": [],
                "velocity": "off", "velocity_fast": 2.0, "velocity_slow": 0.4, "motion_blur": True,
                "rgb_split_on_beats": False, "rgb_split_px": 14},
    "audio": {"game_audio_volume": 0.25, "normalize_lufs": -14,
              "sfx": {"enabled": False, "whoosh_on": "effects", "impact_on_drops": True,
                      "riser_before_drop": True, "volume": 0.5}},
}


def merged_recipe(path):
    r = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_RECIPE.items()}
    if path:
        user = load_json(path)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(r.get(k), dict):
                r[k].update(v)
            else:
                r[k] = v
    return r


# ---------------------------------------------------------------- planning
def cut_points(beats, length, every, snap, shot_sec, drops):
    if snap and beats:
        bs = [b for b in beats["beats"] if 0 < b < length]
        if every == 0.5:
            pts = []
            for a, b in zip([0.0] + bs, bs):
                pts += [round(a + (b - a) / 2, 3), b]
        else:
            step = max(1, int(every))
            pts = bs[::step]
        pts = sorted(set(pts) | {d for d in drops if 0 < d < length})
    else:
        n = int(length / max(shot_sec, 0.2))
        pts = [round(i * shot_sec, 3) for i in range(1, n)]
    pts = [p for p in pts if 0.12 < p < length - 0.12]
    # drop cuts that would make a segment shorter than ~4 frames
    clean = []
    for p in pts:
        if not clean or p - clean[-1] >= 0.07:
            clean.append(p)
    return [0.0] + clean + [length]


def build_pool(args):
    pool = []
    if args.highlights:
        for h in load_json(args.highlights)["highlights"]:
            src = h.get("clip") or h["source"]
            s, e = (0.0, None) if h.get("clip") else (h["start"], h["end"])
            peak = h.get("peak")
            if peak is not None and h.get("clip"):
                peak = peak - h["start"]  # exported clips start at the highlight's start
            pool.append({"source": src, "start": s, "end": e, "score": h.get("score", 0), "peak": peak})
    for f in collect_media(args.clips or [], VIDEO_EXTS):
        pool.append({"source": str(f.resolve()), "start": 0.0, "end": None, "score": 0})
    if not pool:
        die("No clips. Pass --clips or --highlights.")
    for p in pool:
        info = probe(p["source"])
        if not info["has_video"]:
            die(f"{p['source']} has no video")
        p["end"] = min(p["end"] or info["duration"], info["duration"])
        p["cursor"] = p["start"]
        p["src_fps"] = info["fps"] or 30
        if p.get("peak") is None or not (p["start"] <= p["peak"] <= p["end"]):
            p["peak"] = p["start"] + 0.6 * (p["end"] - p["start"])  # best guess: action is late in a clip
    return pool


def take(pool_item, need_sec):
    """Take need_sec of source from a pool item; loops back to its start if it runs out."""
    if pool_item["end"] - pool_item["cursor"] < need_sec:
        pool_item["cursor"] = pool_item["start"]
    start = pool_item["cursor"]
    length = min(need_sec, pool_item["end"] - start)
    pool_item["cursor"] = start + length
    return start, length


def make_plan(args, recipe, beats, pool, length):
    fx = recipe["effects"]
    fps = int(recipe["format"]["fps"])
    W, H = frame_size(recipe["format"]["aspect"], recipe["format"].get("resolution", 1080))
    drops = beats["drops"] if beats else []
    bounds = cut_points(beats, length, recipe["pacing"].get("cut_every_beats", 2),
                        recipe["pacing"].get("snap_cuts_to_beats", True),
                        recipe["pacing"].get("median_shot_sec") or 1.0, drops)
    strong = set()
    if beats:
        for t, s in zip(beats["beats"], beats["beat_strength"]):
            if s >= 0.6:
                strong.add(round(t, 3))
        strong |= {round(t, 3) for t in beats.get("downbeats", [])}

    # Save the best-scoring clips for the drops; everything else rotates through the normal cuts.
    heroes = sorted(range(len(pool)), key=lambda i: -pool[i]["score"])
    n_drops = sum(1 for d in drops if 0 <= d < length)
    reserved = set(heroes[:min(n_drops, max(len(pool) - 2, 0))])
    order = [i for i in range(len(pool)) if i not in reserved] or list(range(len(pool)))
    if args.shuffle:
        random.Random(args.seed).shuffle(order)
    rot, hero_i, segs = 0, 0, []
    slowmo_left = 0
    hook_first = getattr(args, "hook_first", False)
    cold = getattr(args, "cold_open", False) and len(bounds) >= 5 and pool
    hero = heroes[0] if pool else None
    if cold:
        hero_i = 1  # the best clip is spent on the cold open; drops get the next ones
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        f0, f1 = int(round(a * fps)), int(round(b * fps))
        if f1 <= f0:
            continue
        if cold and i in (0, 1, 2):
            D = (f1 - f0) / fps
            p = pool[hero]
            if i == 0:    # result first: the payoff itself
                src_in = max(p["start"], min(p["peak"] - 0.15, p["end"] - D - 0.05))
                seg = {"speed": 1.0, "src_in": src_in, "src_len": D + 0.05, "effects": ["zoom"]}
            elif i == 1:  # rewind back through the play, fast and reversed
                rs = 3.0
                span = min(D * rs, p["peak"] - p["start"]) or D
                seg = {"speed": round(span / D, 3), "src_in": max(p["start"], p["peak"] - span),
                       "src_len": span, "effects": ["rewind"]}
            else:         # then the buildup plays from the top
                p["cursor"] = p["start"]
                s_in, got = take(p, D + 0.05)
                seg = {"speed": 1.0, "src_in": s_in, "src_len": got, "effects": ["flash"]}
            segs.append({"index": len(segs), "tl_start": round(a, 3), "tl_end": round(b, 3),
                         "tl_start_frame": f0, "tl_end_frame": f1, "source": p["source"],
                         "src_in": round(seg["src_in"], 3), "src_len": round(seg["src_len"], 3),
                         "speed": seg["speed"], "effects": seg["effects"]})
            continue
        on_drop = any(abs(a - d) < 0.05 for d in drops)
        on_strong = round(a, 3) in strong or any(abs(a - s) < 0.05 for s in strong)
        if on_drop and fx.get("slowmo_on_drops"):
            slowmo_left = 2
        speed = fx.get("slowmo_speed", 0.5) if slowmo_left > 0 else 1.0
        slowmo_left -= 1
        if (on_drop or (hook_first and i == 0)) and hero_i < len(heroes):
            idx = heroes[hero_i]
            hero_i += 1
        else:
            idx = order[rot % len(order)]
            rot += 1
        D = (f1 - f0) / fps
        vel_mode = fx.get("velocity", "off")
        velocity = (speed == 1 and D >= 0.35 and
                    (vel_mode == "all" or (vel_mode == "strong_beats" and on_strong)))
        if velocity:
            vf, vs = float(fx.get("velocity_fast", 2.0)), float(fx.get("velocity_slow", 0.4))
            need_sec = D * (0.4 * vf + 0.6 * vs) + 0.05
        else:
            need_sec = D * speed + 0.05
        src_in, got = take(pool[idx], need_sec)
        effects = ["velocity"] if velocity else []
        if fx.get("zoom_punch_on_beats") and (on_strong or on_drop):
            effects.append("zoom")
        if fx.get("shake_on_drops") and on_drop:
            effects.append("shake")
        if fx.get("flash_on_strong_beats") and (on_drop or (on_strong and i % 2 == 0)):
            effects.append("flash")
        if fx.get("rgb_split_on_beats") and (on_drop or on_strong):
            effects.append("rgb")
        segs.append({"index": len(segs), "tl_start": round(a, 3), "tl_end": round(b, 3),
                     "tl_start_frame": f0, "tl_end_frame": f1, "source": pool[idx]["source"],
                     "src_in": round(src_in, 3), "src_len": round(got, 3), "speed": speed,
                     "effects": effects})
    if getattr(args, "loop", False) and len(segs) >= 3:
        # end on the moments just before the opening frame, so the replay flows straight on
        first, last = segs[0], segs[-1]
        D = (last["tl_end_frame"] - last["tl_start_frame"]) / fps
        if first["src_in"] - D >= 0:
            last.update({"source": first["source"], "src_in": round(first["src_in"] - D, 3),
                         "src_len": round(D, 3), "speed": 1.0, "effects": ["loop-end"]})
        else:
            print("Note: not enough footage before the opening shot for a seamless loop; "
                  "the ending cuts back to the start on the beat instead.")
    return {"name": recipe.get("name", "montage"), "fps": fps, "width": W, "height": H,
            "song": str(Path(args.song).resolve()), "song_start": args.song_start,
            "length": length, "fit": args.fit, "recipe": recipe, "segments": segs,
            "render_w": W, "render_h": H, "render_fps": fps,
            "drops": [d for d in drops if 0 < d < length]}


# ---------------------------------------------------------------- grading
def footage_look(sources):
    from analyze_style import frame_stats  # reuse signalstats parser

    ya, sat, con = [], [], []
    for src in list(dict.fromkeys(sources))[:6]:
        for f in frame_stats(src, fps=1, limit=120, keyframes_only=True):
            ya.append(f.get("YAVG", 0) / 255)
            sat.append(f.get("SATAVG", 0) / 128)
            con.append((f.get("YHIGH", 0) - f.get("YLOW", 0)) / 255)
    if not ya:
        return None
    return {"brightness": st.mean(ya), "saturation": st.mean(sat), "contrast": st.mean(con)}


def grade_filter(target, current):
    if not current or not any(target.get(k) for k in ("brightness", "saturation", "contrast")):
        return None
    clamp = lambda v, lo, hi: max(lo, min(hi, v))
    s = clamp((target.get("saturation") or current["saturation"]) / max(current["saturation"], 0.01), 0.6, 1.8)
    c = clamp((target.get("contrast") or current["contrast"]) / max(current["contrast"], 0.01), 0.85, 1.35)
    b = clamp((target.get("brightness") or current["brightness"]) - current["brightness"], -0.12, 0.12)
    return f"eq=contrast={c:.3f}:saturation={s:.3f}:brightness={b:.3f}"


# ---------------------------------------------------------------- rendering
def fit_chain(W, H, fit):
    if fit == "blur":
        return (f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur={blur_radius(W, H)}:2[bgb];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
                f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


def segment_filter(seg, plan, grade):
    W, H, fps = plan["render_w"], plan["render_h"], plan["render_fps"]
    fx = plan["recipe"]["effects"]
    parts = []  # timing first (applies to the HUD inset too), then framing, then effects
    if "rewind" in seg["effects"]:
        parts += ["reverse", f"setpts=(PTS-STARTPTS)/{seg['speed']}", f"fps={fps}"]
    elif "velocity" in seg["effects"]:
        # fast into the hit, then slow: speed vf for the first 40% of the shot, vs after
        D = (seg["tl_end_frame"] - seg["tl_start_frame"]) / plan["fps"]
        vf, vs = float(fx.get("velocity_fast", 2.0)), float(fx.get("velocity_slow", 0.4))
        t1, d1 = 0.4 * D * vf, 0.4 * D
        if fx.get("motion_blur", True):
            parts.append(f"tmix=frames=3:enable='lt(t,{t1:.3f})'")
        parts.append(f"setpts='if(lt(T-STARTT,{t1:.3f}),(T-STARTT)/{vf},"
                     f"{d1:.3f}+(T-STARTT-{t1:.3f})/{vs})/TB'")
        parts.append(f"framerate=fps={fps}")  # blends frames in the slow part instead of stuttering
    elif seg["speed"] != 1:
        parts.append(f"setpts=PTS/{seg['speed']}")
        parts.append(f"framerate=fps={fps}")
    else:
        parts.append(f"fps={fps}")
    if grade:
        parts.append(grade)
    timing = ",".join(parts)
    parts = []
    if "rewind" in seg["effects"]:  # VHS-ish look so the rewind reads as a rewind
        px = max(2, int(10 * W / 1080))
        parts += ["hue=s=0.25", "eq=contrast=1.18:brightness=0.03", "colorbalance=bs=0.18:bm=0.08:rh=-0.05",
                  "noise=alls=28:allf=t", f"rgbashift=rh=-{px}:bh={px}",
                  "drawbox=x=0:y=ih*mod(t*1.7\\,1):w=iw:h=ih*0.035:color=white@0.25:t=fill"]
    if "zoom" in seg["effects"]:
        z = float(fx.get("zoom_amount", 1.12)) - 1
        parts.append(f"zoompan=z='1+{z:.3f}*pow(max(0\\,1-it/0.28)\\,2)':d=1:"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps}")
    if "shake" in seg["effects"]:
        pw, ph = int(W * 1.06) // 2 * 2, int(H * 1.06) // 2 * 2
        parts.append(f"scale={pw}:{ph},crop={W}:{H}:"
                     f"x='(iw-{W})/2+(iw-{W})/2*sin(t*47)*exp(-t*2.5)':"
                     f"y='(ih-{H})/2+(ih-{H})/2*cos(t*39)*exp(-t*2.5)'")
    if "rgb" in seg["effects"]:
        px = max(2, int(fx.get("rgb_split_px", 14) * W / 1080))
        parts.append(f"rgbashift=rh=-{px}:bh={px}:enable='lt(t,0.15)'")
    if "flash" in seg["effects"]:
        parts.append(f"fade=t=in:st=0:d=0.12:color={fx.get('flash_color', 'white')}")
    if fx.get("letterbox"):
        bar = int(H * 0.11)
        parts.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
                     f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    effects = ",".join(parts)
    lay = plan.get("layout") or {}
    if plan["fit"] == "hud" and lay.get("hud"):
        from layout import hud_graph, resolve_regions
        body = hud_graph(W, H, resolve_regions(lay["hud"]), lay.get("hud_place", "top"), effects)
    else:
        body = f"{fit_chain(W, H, 'crop' if plan['fit'] == 'hud' else plan['fit'])},setsar=1" + (
            f",{effects}" if effects else "")
    # never run short; -frames:v trims exactly
    return f"{timing},{body},tpad=stop_mode=clone:stop=-1,format=yuv420p"


def text_filter(overlays, W, H, hud_top=False):
    if not overlays:
        return None
    font = find_font()
    out = []
    for o in overlays:
        txt = str(o["text"]).replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
        from layout import text_size, text_y
        size = int(o.get("size") or text_size(W, H, o["text"]))
        y = text_y(o.get("position", "center"), W, H)
        if hud_top and o.get("position", "center") == "top":
            y = "h*0.30"  # HUD insets own the top: drop the caption below them
        fontopt = f"fontfile='{ff_path(font)}':" if font else ""
        out.append(f"drawtext={fontopt}text='{txt}':fontsize={size}:fontcolor=white:borderw=6:"
                   f"bordercolor=black:x=(w-text_w)/2:y={y}:"
                   f"enable='between(t,{o.get('start', 0)},{o.get('end', 2)})'")
    return ",".join(out)


def segment_audio(seg, plan, path):
    """The clip's own sound for this cut, exactly as long as the cut. Silent for speed changes."""
    D = (seg["tl_end_frame"] - seg["tl_start_frame"]) / plan["fps"]
    has_audio = probe_cached(seg["source"])["has_audio"]
    if has_audio and seg["speed"] == 1 and "velocity" not in seg["effects"]:
        ffmpeg(["-ss", f"{seg['src_in']:.3f}", "-t", f"{D + 0.1:.3f}", "-i", seg["source"], "-vn",
                "-af", f"aresample=48000,apad,atrim=0:{D:.5f}", "-ac", "2", "-c:a", "pcm_s16le", str(path)])
    else:
        ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{D:.5f}",
                "-c:a", "pcm_s16le", str(path)])
    return path


_PROBES = {}


def probe_cached(path):
    if path not in _PROBES:
        _PROBES[path] = probe(path)
    return _PROBES[path]


def render(plan, out_path, grade, preview=False, fade_in=0.0, fade_out=1.5, sound_ready=False):
    if preview:  # half size, 30fps, fast: same cuts and effects
        plan["render_w"], plan["render_h"] = preview_size(plan["width"], plan["height"])
        plan["render_fps"] = 30
    fps = plan["render_fps"]
    game_vol = float(plan["recipe"].get("audio", {}).get("game_audio_volume") or 0)
    norm = ""  # loudness is set exactly after the render (normalize_loudness)
    with tempfile.TemporaryDirectory() as td:
        def one(seg):
            # frames at render fps, from the same timeline positions -> no drift in preview either
            f0 = round(seg["tl_start"] * fps) if preview else seg["tl_start_frame"]
            f1 = round(seg["tl_end"] * fps) if preview else seg["tl_end_frame"]
            n = max(1, f1 - f0)
            part = Path(td) / f"seg_{seg['index']:04d}.mp4"
            ffmpeg(["-ss", f"{seg['src_in']:.3f}", "-t", f"{seg['src_len'] + 0.2:.3f}", "-i", seg["source"],
                    "-an", "-vf", segment_filter(seg, plan, grade),
                    "-frames:v", str(n), "-r", str(fps), "-threads", "2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20" if preview else "14", str(part)])
            if game_vol > 0:
                segment_audio(seg, plan, Path(td) / f"seg_{seg['index']:04d}.wav")
            return part

        workers = max(1, min(6, (os.cpu_count() or 2) // 2))
        with ThreadPoolExecutor(workers) as pool_ex:
            parts = []
            for k, part in enumerate(pool_ex.map(one, plan["segments"]), 1):
                parts.append(part)
                print(f"  segment {k}/{len(plan['segments'])}", end="\r")
        print()
        listing = [concat_line(p) for p in parts]
        lst = Path(td) / "list.txt"
        lst.write_text("\n".join(listing), encoding="utf-8")
        joined = Path(td) / "joined.mp4"
        ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])

        L = plan["length"]
        inputs = ["-i", str(joined), "-ss", str(plan["song_start"]), "-t", f"{L:.3f}", "-i", plan["song"]]
        fades = ""
        if fade_in > 0:
            fades += f",afade=t=in:st=0:d={fade_in}"
        if fade_out > 0:
            fades += f",afade=t=out:st={max(L - fade_out, 0):.3f}:d={fade_out}"
        layers, pre = ["[1:a]"], ""
        if game_vol > 0:
            alst = Path(td) / "alist.txt"
            wavs = [(Path(td) / "seg_{:04d}.wav".format(s["index"])).as_posix() for s in plan["segments"]]
            alst.write_text("\n".join(concat_line(w) for w in wavs), encoding="utf-8")
            inputs += ["-f", "concat", "-safe", "0", "-i", str(alst)]
            pre += f"[{len(layers) + 1}:a]volume={game_vol}[g];"
            layers.append("[g]")
        sfx_cfg = plan["recipe"].get("audio", {}).get("sfx") or {}
        if sfx_cfg.get("enabled"):
            from sfx import build_sfx_track, montage_events
            events = montage_events(plan, sfx_cfg)
            if events:
                sfx_wav = build_sfx_track(events, L, Path(td) / "sfx.wav", float(sfx_cfg.get("volume", 0.5)))
                inputs += ["-i", str(sfx_wav)]
                pre += f"[{len(layers) + 1}:a]aresample=48000[fx];"
                layers.append("[fx]")
                print(f"SFX: {len(events)} sounds ({', '.join(sorted(set(k for k, _ in events)))})")
        if len(layers) > 1:
            graph = (f"{pre}{''.join(layers)}amix=inputs={len(layers)}:duration=first:normalize=0,"
                     f"alimiter=limit=0.95{norm}{fades}[a]")
        else:
            graph = f"[1:a]anull{norm}{fades}[a]"
        lay = plan.get("layout") or {}
        vf = text_filter(plan["recipe"]["effects"].get("text_overlays"), plan["render_w"], plan["render_h"],
                         hud_top=plan["fit"] == "hud" and lay.get("hud_place") == "top")
        graph += f";[0:v]{vf}[v]" if vf else ";[0:v]null[v]"
        args = [*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]"]
        if preview:
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p"]
        else:
            args += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
        args += ["-c:a", "aac", "-b:a", "256k", "-t", f"{L:.3f}", "-movflags", "+faststart", str(out_path)]
        ffmpeg(args, hw=True)

        sr_path = None
        if sound_ready:
            # Same video, everything except the song: add the trending sound in the app instead.
            sr_path = Path(out_path).with_name(Path(out_path).stem + "_sound-ready.mp4")
            extra = layers[1:]
            if extra:
                sr_in = ["-i", str(out_path)] + inputs[8:]   # drop the joined-video and song inputs
                import re as _re
                shifted = _re.sub(r"\[(\d+):a\]", lambda m: f"[{int(m.group(1)) - 1}:a]", pre)  # song input removed
                sgraph = (f"{shifted}{''.join(extra)}amix=inputs={len(extra)}:duration=longest:normalize=0,"
                          f"apad,atrim=0:{L:.3f},alimiter=limit=0.95[a]") if len(extra) > 1 else \
                         f"{shifted}{extra[0]}apad,atrim=0:{L:.3f}[a]"
                ffmpeg([*sr_in, "-filter_complex", sgraph, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-t", f"{L:.3f}", "-movflags", "+faststart", str(sr_path)])
            else:
                ffmpeg(["-i", str(out_path), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-t", f"{L:.3f}", str(sr_path)])
    lufs = plan["recipe"].get("audio", {}).get("normalize_lufs")
    if lufs is not None:
        got = normalize_loudness(out_path, float(lufs))
        if got is not None:
            print(f"Loudness: {got} LUFS")
        if sr_path and len(layers) > 1:
            normalize_loudness(sr_path, -18.0)  # "original sound" bed: the app's sound goes on top
    if sr_path:
        write_sound_guide(plan, sr_path)
    return str(out_path)


def write_sound_guide(plan, sr_path):
    m, s = divmod(plan["song_start"], 60)
    guide = Path(sr_path).with_name(Path(sr_path).stem.replace("_sound-ready", "") + "_sound_guide.txt")
    guide.write_text(
        f"Sound-ready version: {Path(sr_path).name}\n"
        f"Cuts are synced to: {Path(plan['song']).stem}, starting at {int(m)}:{s:05.2f} into the track.\n\n"
        "TikTok / Reels / Shorts:\n"
        f"  1. Upload {Path(sr_path).name}\n"
        f"  2. Add sound -> search for the song (use the trending/official version of the SAME edit of it)\n"
        f"  3. Scissors / trim -> start the sound at {int(m)}:{s:05.2f}\n"
        "  4. Volume -> Added sound 100%, Original sound 30-50% (that's your game sounds/SFX)\n\n"
        "If the in-app version is sped up, slowed or a remix, the beat won't line up: pick the version that\n"
        "matches, or post the regular version with the song baked in.\n"
        f"Length: {plan['length']:.1f}s\n", encoding="utf-8")
    print(f"Sound-ready -> {sr_path}\nGuide -> {guide}")


if __name__ == "__main__":
    from beats import analyze as beat_analyze
    from xml_timeline import write_xmeml

    ap = argparse.ArgumentParser()
    ap.add_argument("--song", required=True)
    ap.add_argument("--clips", nargs="*")
    ap.add_argument("--highlights")
    ap.add_argument("--recipe")
    ap.add_argument("--song-start", type=float, default=0.0)
    ap.add_argument("--length", type=float, default=None, help="montage length in seconds")
    ap.add_argument("--fit", choices=["crop", "blur", "hud"], default=None,
                    help="crop | blur | hud (vertical crop + HUD insets; regions from recipe layout or --hud)")
    ap.add_argument("--hud", nargs="*", help="HUD regions: presets (rl-scoreboard rl-boost fortnite-minimap) "
                    "or x,y,w,h[,scale] fractions")
    ap.add_argument("--hud-place", choices=["top", "bottom"], default=None)
    ap.add_argument("--res", default=None,
                    help="output resolution (short side): 1080 (default), 1440, 2160/4k, or 'source' to match "
                         "your best clip. TikTok/Reels/Shorts show 1080p; YouTube can use more")
    ap.add_argument("--cold-open", action="store_true",
                    help="result first: flash the payoff, rewind, then play the buildup")
    ap.add_argument("--loop", action="store_true", help="end on the frames just before the opening, for replays")
    ap.add_argument("--hook-text", help="curiosity caption on the first frame, e.g. 'IS THIS EVEN POSSIBLE?'")
    ap.add_argument("--sound-ready", action="store_true",
                    help="also export a version without the song + a guide for adding the sound in-app")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--hook-first", action="store_true", help="open on the best-scoring clip")
    ap.add_argument("--sfx", action="store_true", help="add whooshes/impacts/riser (same as recipe audio.sfx.enabled)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-grade", action="store_true")
    ap.add_argument("--out", default="montage.mp4")
    ap.add_argument("--plan-out", default="plan.json")
    ap.add_argument("--xml-out", default="montage.xml")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--preview", action="store_true", help="fast half-res render to check the edit")
    ap.add_argument("--fade-in", type=float, default=0.0, help="song fade-in seconds")
    ap.add_argument("--fade-out", type=float, default=1.5, help="song fade-out seconds (0 = hard end)")
    ap.add_argument("--exact-length", action="store_true", help="don't snap the ending to a beat")
    a = ap.parse_args()

    recipe = merged_recipe(a.recipe)
    lay = dict(recipe.get("layout") or {})
    if a.hud:
        regs = []
        for h in a.hud:
            if "," in h:
                vals = [float(x) for x in h.split(",")]
                regs.append(dict(zip(["x", "y", "w", "h", "scale"], vals)))
            else:
                regs.append(h)
        lay["hud"] = regs
    if a.hud_place:
        lay["hud_place"] = a.hud_place
    lay.setdefault("hud_place", "bottom")  # captions own the top third; insets sit above the app's caption zone
    a.fit = a.fit or lay.get("fit") or ("hud" if lay.get("hud") else "crop")
    if a.fit == "hud" and not lay.get("hud"):
        die("--fit hud needs HUD regions: --hud rl-scoreboard ... or recipe layout.hud")
    if a.hook_text:
        others = []
        for o in recipe["effects"].get("text_overlays") or []:
            o = dict(o)
            if o.get("position", "center") == "top" and float(o.get("start", 0)) < 1.8:
                o["position"] = "center"  # the hook owns the top for its first 1.8s
            others.append(o)
        recipe["effects"]["text_overlays"] = [{"text": a.hook_text, "start": 0, "end": 1.8, "position": "top"}] + others
    if a.loop and a.fade_out == 1.5:
        a.fade_out = 0.0  # a fade-out kills the loop; end hard on the beat
    if a.sfx:
        recipe.setdefault("audio", {}).setdefault("sfx", {})["enabled"] = True
    song_info = probe(a.song)
    if not song_info["has_audio"]:
        die("The song file has no audio.")
    length = a.length or min(song_info["duration"] - a.song_start, 60.0)
    if length <= 1:
        die("Montage length is too short; check --song-start / --length.")
    print(f"Beat-tracking {Path(a.song).name} ...")
    room = max(0.0, min(1.0, song_info["duration"] - a.song_start - length))
    beats = beat_analyze(a.song, a.song_start, a.song_start + length + room)
    if not a.exact_length and beats["beats"]:
        # end on a hit: snap the length to the nearest downbeat (or beat) within ~0.6s
        cands = [t for t in beats["downbeats"] if abs(t - length) <= 0.6] or \
                [t for t in beats["beats"] if abs(t - length) <= 0.6]
        if cands:
            snapped = min(cands, key=lambda t: abs(t - length))
            if snapped > 1 and abs(snapped - length) > 0.01:
                print(f"  ending snapped to the beat at {snapped:.2f}s (asked {length:.2f}s; --exact-length to keep)")
                length = round(snapped, 3)
    for k in ("beats", "beat_strength", "downbeats", "drops", "onsets"):
        if k == "beat_strength":
            continue
        beats[k] = [t for t in beats.get(k, []) if t < length]
    beats["beat_strength"] = beats["beat_strength"][:len(beats["beats"])]
    print(f"  {beats['tempo_bpm']} BPM, drops at {beats['drops']}")
    pool = build_pool(a)
    res_req = a.res or recipe["format"].get("resolution", 1080)
    recipe["format"]["resolution"] = resolve_res(res_req, [p["source"] for p in pool])
    if recipe["format"]["resolution"] > 1080 and recipe["format"].get("aspect") in ("9:16", "4:5", "1:1"):
        print("Note: TikTok and Reels downscale vertical video to 1080p, so this size only helps YouTube Shorts "
              "(bigger uploads tend to get a cleaner transcode there) and costs render time.")
    plan = make_plan(a, recipe, beats, pool, length)
    plan["layout"] = lay
    if recipe["format"].get("aspect") in ("9:16", "4:5") and length > 45:
        print(f"Heads up: {length:.0f}s is long for short-form. Gaming shorts tend to hold viewers best at 15-30s "
              "with one peak moment.")
    if length > 180 and recipe["format"].get("aspect") == "9:16":
        print("Warning: YouTube Shorts max out at 3 minutes; longer vertical uploads become regular videos.")
    print(f"Plan: {len(plan['segments'])} cuts over {length:.1f}s at {plan['width']}x{plan['height']} {plan['fps']}fps")
    save_json(plan, a.plan_out)
    write_xmeml(plan, a.xml_out)
    print(f"Plan -> {a.plan_out}, timeline -> {a.xml_out}")
    if a.plan_only:
        raise SystemExit(0)
    grade = None
    if not a.no_grade:
        grade = grade_filter(recipe["color"], footage_look([s["source"] for s in plan["segments"]]))
        if grade:
            print(f"Color grade: {grade}")
            for s in plan["segments"]:
                s["effects"].append("grade")
    print("Rendering preview ..." if a.preview else "Rendering ...")
    render(plan, a.out, grade, preview=a.preview, fade_in=a.fade_in, fade_out=a.fade_out,
           sound_ready=a.sound_ready)
    if not a.preview:
        save_json(plan, a.plan_out)
    print(f"Done -> {a.out}")
