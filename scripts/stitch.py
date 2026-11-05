"""Long-form videos (up to ~45+ min): stitch montage sections and raw gameplay sections into one video.

Usage: python stitch.py project.json [--out final.mp4] [--work-dir sections/] [--preview] [--only N]

project.json:
{
  "name": "Road to Unreal",
  "format": {"aspect": "16:9", "fps": 60},
  "transition": {"type": "fade", "duration": 0.4},      // "cut" | "fade" (dip to black) | "flash" (dip to white)
  "sections": [
    {"type": "montage", "title": "Intro", "song": "intro.mp3", "song_start": 12, "length": 25,
     "clips": ["clips/"], "highlights": null, "recipe": "style/recipe.json", "fit": "crop"},
    {"type": "raw", "title": "Game 1", "source": "rec1.mkv", "start": 95, "end": 840,
     "audio_track": 0, "music": "lofi.mp3", "music_volume": 0.12, "show_title": true},
    {"type": "montage", "title": "Best kills", "song": "drop.mp3", "length": 40, "highlights": "h.json"}
  ]
}
(Comments are for reading only; real JSON can't contain them.)

- montage sections run build_montage.py (same recipes/effects), with the project's size/fps.
- raw sections keep the gameplay + game/voice audio, with an optional quiet music bed and title.
- every section is loudness-normalised (-14 LUFS) so nothing jumps in volume between parts.
- sections are cached in --work-dir: re-running only re-renders sections whose settings changed.
- writes chapters.txt (paste into the YouTube description) and embeds chapters in the MP4.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from common import (blur_radius, concat_line, die, frame_size, preview_size, resolve_res, need, ff_path, ffmpeg, find_font, load_json, normalize_loudness, probe,
                    save_json)

HERE = Path(__file__).resolve().parent


def fit_graph(W, H, fit):
    if fit == "blur":
        return (f"split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur={blur_radius(W, H)}:2[bgb];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
                f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


def title_filter(text, W, H, dur=2.5):
    font = find_font()
    txt = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")
    fontopt = f"fontfile='{ff_path(font)}':" if font else ""
    from layout import text_size
    size = text_size(W, H, text)
    return (f"drawtext={fontopt}text='{txt}':fontsize={size}:fontcolor=white:borderw=6:bordercolor=black:"
            f"x=(w-text_w)/2:y=h*0.12:alpha='if(lt(t,0.3),t/0.3,if(lt(t,{dur - 0.4}),1,max(0,({dur}-t)/0.4)))':"
            f"enable='lt(t,{dur})'")


def section_key(sec, fmt, preview):
    blob = json.dumps({"s": sec, "f": fmt, "p": preview}, sort_keys=True)
    files = [sec.get(k) for k in ("song", "source", "music", "recipe", "highlights")] + list(sec.get("clips") or [])
    for f in files:
        if f and Path(f).exists():
            st = Path(f).stat()
            blob += f"{f}:{st.st_size}:{int(st.st_mtime)}"
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def render_montage(sec, fmt, out_raw, preview, work):
    recipe = load_json(sec["recipe"]) if sec.get("recipe") else {}
    recipe["format"] = dict(fmt)  # project size/fps win
    rpath = work / f"_recipe_{out_raw.stem}.json"
    save_json(recipe, rpath)
    cmd = [sys.executable, str(HERE / "build_montage.py"), "--song", sec["song"], "--recipe", str(rpath),
           "--song-start", str(sec.get("song_start", 0)), "--fit", sec.get("fit", "crop"),
           "--fade-out", "0", "--exact-length", "--out", str(out_raw),
           "--plan-out", str(work / f"{out_raw.stem}_plan.json"), "--xml-out", str(work / f"{out_raw.stem}.xml")]
    if sec.get("length"):
        cmd += ["--length", str(sec["length"])]
    if sec.get("clips"):
        cmd += ["--clips", *sec["clips"]]
    if sec.get("highlights"):
        cmd += ["--highlights", sec["highlights"]]
    if sec.get("shuffle"):
        cmd += ["--shuffle"]
    if preview:
        cmd += ["--preview"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"Montage section '{sec.get('title')}' failed:\n{res.stderr[-1500:]}")


def finalize(src, out, W, H, fps, sec, transition, preview, is_first, is_last, raw=False):
    """Bring any section to the common size/fps/audio, add title, fades and loudness normalisation."""
    info = probe(src) if not raw else probe(sec["source"])
    ttype, td = transition.get("type", "fade"), float(transition.get("duration", 0.4))
    inputs, vchain = [], []
    if raw:
        start, end = float(sec.get("start", 0)), sec.get("end")
        inputs += ["-ss", str(start)]
        if end:
            inputs += ["-to", str(float(end))]
        inputs += ["-i", sec["source"]]
        dur = (float(end) if end else info["duration"]) - start
        vchain.append(fit_graph(W, H, sec.get("fit", "blur" if (info["height"] or 0) > (info["width"] or 1) else "crop")))
    else:
        inputs += ["-i", str(src)]
        dur = info["duration"]
        vchain.append(fit_graph(W, H, "crop"))
    vchain += ["setsar=1", f"fps={fps}"]
    if sec.get("show_title") and sec.get("title"):
        vchain.append(title_filter(sec["title"], W, H))
    color = "white" if ttype == "flash" else "black"
    if ttype in ("fade", "flash") and td > 0:
        if not is_first:
            vchain.append(f"fade=t=in:st=0:d={td}:color={color}")
        if not is_last:
            vchain.append(f"fade=t=out:st={max(dur - td, 0):.3f}:d={td}:color={color}")
    vchain.append("format=yuv420p")

    # audio: section's own sound (+ optional music bed), normalised
    achain = []
    has_audio = info["has_audio"]
    track = int(sec.get("audio_track", 0)) if raw else 0
    music = sec.get("music") if raw else None
    graph = f"[0:v]{','.join(vchain)}[v]"
    if has_audio:
        graph += f";[0:a:{track}]aresample=48000,aformat=channel_layouts=stereo[sa]"
    else:
        graph += f";anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[sa]"
    if music:
        inputs += ["-stream_loop", "-1", "-i", music]
        mv = float(sec.get("music_volume", 0.12))
        duck = sec.get("duck", True)
        if duck:
            # music sits ~18 dB under, then ducks a further ~6 dB whenever voice/game sound is active
            graph += (f";[sa]asplit=2[sa1][key0];[key0]highpass=f=250,lowpass=f=3400[key]"  # key on voice band
                      f";[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={mv}[mb0]"
                      f";[mb0][key]sidechaincompress=threshold=0.05:ratio=4:attack=15:release=450:makeup=1[mb]"
                      f";[sa1][mb]amix=inputs=2:duration=first:normalize=0[mix]")
        else:
            graph += (f";[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={mv}[mb]"
                      f";[sa][mb]amix=inputs=2:duration=first:normalize=0[mix]")
        last = "mix"
    else:
        last = "sa"
    if ttype in ("fade", "flash") and td > 0:
        if not is_first:
            achain.append(f"afade=t=in:st=0:d={td}")
        if not is_last:
            achain.append(f"afade=t=out:st={max(dur - td, 0):.3f}:d={td}")
    graph += f";[{last}]{','.join(achain)}[a]"

    preset, crf = ("veryfast", "26") if preview else ("medium", "18")
    ffmpeg([*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", preset, "-crf", crf, "-r", str(fps), "-g", str(fps * 2),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)], hw=True)
    normalize_loudness(out, float(sec.get("lufs", -14)))
    return probe(out)["duration"]


def ts(sec):
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", default="final.mp4")
    ap.add_argument("--work-dir", default="sections")
    ap.add_argument("--preview", action="store_true", help="half resolution, 30fps, fast encode")
    ap.add_argument("--only", type=int, help="render just section N (1-based) to check it")
    a = ap.parse_args()

    proj = load_json(a.project)
    fmt = {"aspect": "16:9", "fps": 60, **(proj.get("format") or {})}
    sections = proj.get("sections") or die("project has no sections")
    srcs = [s.get("source") for s in sections if s.get("source")] + \
        [c for s in sections for c in (s.get("clips") or []) if Path(c).is_file()]
    fmt["resolution"] = resolve_res(fmt.get("resolution", 1080), srcs)
    W, H = frame_size(fmt["aspect"], fmt["resolution"])
    fps = int(fmt["fps"])
    if a.preview:
        (W, H), fps = preview_size(W, H), 30
    transition = proj.get("transition") or {"type": "fade", "duration": 0.4}
    if isinstance(transition, str):          # "fade" is fine too, not just {"type": "fade"}
        transition = {"type": transition, "duration": 0.4}
    if transition.get("type") not in ("cut", "fade", "flash"):
        die(f"Unknown transition '{transition.get('type')}'. Use cut, fade or flash.")
    work = Path(a.work_dir)
    work.mkdir(parents=True, exist_ok=True)

    todo = range(len(sections)) if not a.only else [a.only - 1]
    finals, durations = [], []
    for i in todo:
        sec = sections[i]
        kind = sec.get("type", "montage")
        key = section_key(sec, fmt, a.preview) + f"-{transition.get('type')}-{i == 0}-{i == len(sections) - 1}"
        final = work / f"s{i + 1:02d}_{key}.mp4"
        label = f"[{i + 1}/{len(sections)}] {kind} '{sec.get('title', '')}'"
        if final.exists():
            print(f"{label}: cached")
        else:
            print(f"{label}: rendering ...")
            if kind == "montage":
                raw_out = work / f"s{i + 1:02d}_{key}_raw.mp4"
                render_montage(sec, fmt, raw_out, a.preview, work)
                finalize(raw_out, final, W, H, fps, sec, transition, a.preview, i == 0, i == len(sections) - 1)
                raw_out.unlink(missing_ok=True)
            elif kind == "raw":
                if not sec.get("source"):
                    die(f"Section {i + 1} is raw but has no 'source'")
                finalize(None, final, W, H, fps, sec, transition, a.preview, i == 0, i == len(sections) - 1, raw=True)
            else:
                die(f"Unknown section type '{kind}' (use 'montage' or 'raw')")
        finals.append(final)
        durations.append(probe(final)["duration"])

    if a.only:
        print(f"Section {a.only} -> {finals[0]}")
        raise SystemExit(0)

    # chapters
    t, chapters, meta = 0.0, [], [";FFMETADATA1", f"title={proj.get('name', 'video')}"]
    for sec, d in zip(sections, durations):
        title = sec.get("title") or f"Part {len(chapters) + 1}"
        chapters.append(f"{ts(t)} {title}")
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int((t + d) * 1000)}", f"title={title}"]
        t += d
    out = Path(a.out)
    chap_txt = out.with_name(out.stem + "_chapters.txt")
    chap_txt.write_text("\n".join(chapters) + "\n", encoding="utf-8")
    metaf = work / "chapters.ffmeta"
    metaf.write_text("\n".join(meta) + "\n", encoding="utf-8")
    lst = work / "concat.txt"
    lst.write_text("\n".join(concat_line(f) for f in finals), encoding="utf-8")
    # sections are joined without re-encoding when they all came from the same encoder; if some
    # were made on the GPU and some on the CPU (or by different runs), re-encode the join so the
    # file is clean
    sigs = set()
    for f in finals:
        r = subprocess.run([need("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,profile,pix_fmt,width,height,r_frame_rate:stream_tags=encoder",
                            "-of", "csv=p=0", str(f)], capture_output=True, text=True)
        sigs.add(r.stdout.strip())
    if len(sigs) <= 1:
        ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(metaf), "-map", "0", "-map_metadata", "1",
                "-map_chapters", "1", "-c", "copy", "-movflags", "+faststart", str(out)])
    else:
        print("Sections were encoded differently; re-encoding the join so playback is clean ...")
        ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(metaf), "-map", "0:v", "-map", "0:a",
                "-map_metadata", "1", "-map_chapters", "1", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy", "-movflags", "+faststart", str(out)], hw=True)
    print(f"Done -> {out} ({ts(t)} long), chapters -> {chap_txt}")
    if len(sections) < 3 or min(durations) < 10:
        print("Note: YouTube only shows chapters with 3+ chapters, each at least 10 seconds long.")
