"""Word-by-word captions (the highlighted-word style talking videos use), burned in or as files.

Usage: python captions.py VIDEO TRANSCRIPT [--map cut.map.json] [--style highlight|pop|plain]
                          [--words 3] [--position auto|top|center|lower] [--color yellow] [--no-upper]
                          [--emphasis auto|none|"word,word"] [--emphasis-color green]
                          [--out captioned.mp4] [--files-only] [--preview]

TRANSCRIPT comes from `vlog_cut.py transcribe`. If the video was cut with `vlog_cut.py cut`, pass the
cut's .map.json so word times follow the edit (words that were cut out are dropped).
Writes <out>.ass (styled, for burn-in or editors) and <out>.srt (plain, for platform upload).
Positions stay inside the TikTok/Reels/Shorts safe zone on vertical video.
--emphasis auto colours the key word of some caption groups (numbers and scores, words said
louder than the rest, words written in caps or with "!"), plus any keywords you list. It's the
"bold the key word" trick that retention editors use, kept rare so it stays special.
"""

import argparse
import re
import subprocess
from pathlib import Path

import numpy as np

from common import die, ff_path, ffmpeg, load_json, need, probe, safe_copy

COLORS = {
    "yellow": "&H0000FFFF&",
    "green": "&H0000FF66&",
    "cyan": "&H00FFFF00&",
    "pink": "&H00B469FF&",
    "red": "&H003C3CFF&",
    "white": "&H00FFFFFF&",
}


def remap_words(words, mapping):
    if not mapping:
        return words
    out = []
    for w in words:
        for r in mapping["ranges"]:
            if r["src_start"] - 0.02 <= w["start"] and w["end"] <= r["src_end"] + 0.02:
                d = r["out_start"] - r["src_start"]
                out.append({**w, "start": max(r["out_start"], w["start"] + d), "end": w["end"] + d})
                break
    return out


STOP = set(
    """a an and are as at be but by for from had has have he her his i if in into is it its just like me my no
not of on or our out she so than that the their them then there these they this to too up us was we were what when
where which who will with you your yeah okay ok um uh oh like really very gonna wanna got get its im youre dont cant
thats theres lets one all about can do did does going go know right think want""".split()
)


def word_loudness(video, words):
    """dB of each word relative to the speaker's typical level (positive = said louder)."""
    res = subprocess.run(
        [
            need("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-map",
            "0:a:0",
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
        return [0.0] * len(words)
    db = []
    for w in words:
        a, b = int(w["start"] * 16000), int(max(w["end"], w["start"] + 0.05) * 16000)
        seg = x[a:b]
        db.append(10 * np.log10(np.mean(seg**2) + 1e-10) if len(seg) else -100.0)
    db = np.array(db)
    ok = db > -90
    med = np.median(db[ok]) if ok.any() else 0.0
    return list(np.where(ok, db - med, -99.0))


def pick_emphasis(words, chunks, mode, loud=None):
    """Indexes (into words) of the words to colour. At most one per caption group, in about a third of groups."""
    if mode == "none":
        return set()
    wanted = set()
    if mode != "auto":
        wanted = {re.sub(r"[^a-z0-9]", "", k.lower()) for k in mode.split(",") if k.strip()}
    idx = {id(w): i for i, w in enumerate(words)}
    picks = []
    for ch in chunks:
        best, best_sc = None, 0.0
        for w in ch:
            raw = w["w"].strip()
            n = re.sub(r"[^a-z0-9$%]", "", raw.lower())
            if not n:
                continue
            sc = 0.0
            if n.strip("$%") in wanted:
                sc += 6
            if re.search(r"\d", n) or n.startswith("$") or n.endswith("%"):
                sc += 3.5
            if len(raw) >= 2 and raw.isupper() and raw.isalpha():
                sc += 2
            if raw.endswith("!"):
                sc += 1.5
            if n not in STOP and len(n) >= 5:
                sc += 1 + min(len(n) - 5, 4) * 0.15
            if loud is not None:
                d = loud[idx[id(w)]]
                if d > 3:
                    sc += min(d - 3, 6) * 0.6
            if n in STOP:
                sc = 0
            if sc > best_sc:
                best, best_sc = w, sc
        picks.append((best_sc, best))
    # keep the strongest, about a third of the groups, and anything the user asked for
    scores = sorted((sc for sc, w in picks if w is not None), reverse=True)
    cut = scores[max(0, len(picks) // 3 - 1)] if scores and len(picks) >= 3 else 0
    out = set()
    for sc, w in picks:
        if w is not None and sc >= max(3.0, cut):
            out.add(idx[id(w)])
        elif w is not None and wanted and re.sub(r"[^a-z0-9]", "", w["w"].lower()) in wanted:
            out.add(idx[id(w)])
    return out


def chunk(words, max_words, max_chars):
    chunks, cur = [], []
    for w in words:
        gap = w["start"] - cur[-1]["end"] if cur else 0
        text_len = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
        if cur and (
            len(cur) >= max_words
            or text_len > max_chars
            or gap > 0.35
            or cur[-1]["w"].rstrip().endswith((".", "?", "!", ","))
        ):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def ass_time(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def srt_time(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"


def clean(text, upper):
    text = text.replace("{", "(").replace("}", ")").replace("\\", "/").strip()
    return text.upper() if upper else text


def build(
    words,
    W,
    H,
    style="highlight",
    max_words=3,
    position="auto",
    color="yellow",
    upper=True,
    emphasis="auto",
    emph_color="green",
    loud=None,
):
    vertical = H > W
    size = int(H * (0.045 if vertical else 0.062))
    max_chars = 15 if vertical else 30
    if position == "auto":
        position = "lower"
    y = {"top": 0.20, "center": 0.50, "lower": 0.64 if vertical else 0.84}[position]
    hl = COLORS.get(color, color)
    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,Arial,{size},&H00FFFFFF&,&H00FFFFFF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,1,0,1,"
        f"{max(2, size // 11)},{max(1, size // 22)},5,{int(W * 0.08)},{int(W * 0.08)},0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    pos = f"{{\\pos({W // 2},{int(H * y)})}}"
    events, srt = [], []
    chunks = chunk(words, max_words, max_chars)
    emph = pick_emphasis(words, chunks, emphasis, loud)
    ec = COLORS.get(emph_color, emph_color)
    if ec == hl:
        ec = COLORS["green"] if hl != COLORS["green"] else COLORS["yellow"]
    gidx = {id(w): i for i, w in enumerate(words)}
    for ci, ch in enumerate(chunks):
        c_start = ch[0]["start"]
        nxt = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else ch[-1]["end"] + 0.6
        c_end = min(ch[-1]["end"] + 0.25, nxt)
        texts = [clean(w["w"], upper) for w in ch]
        is_em = [gidx[id(w)] in emph for w in ch]
        srt.append((c_start, c_end, " ".join(texts)))
        if style == "plain":
            events.append(
                (
                    c_start,
                    c_end,
                    pos
                    + " ".join(f"{{\\c{ec}\\fscx112\\fscy112}}{t}{{\\r}}" if em else t for t, em in zip(texts, is_em)),
                )
            )
            continue
        for k, w in enumerate(ch):
            s = c_start if k == 0 else w["start"]
            e = ch[k + 1]["start"] if k + 1 < len(ch) else c_end
            if e <= s:
                continue
            parts = []
            for j, t in enumerate(texts):
                col = ec if is_em[j] else hl
                if j == k:
                    big = 122 if is_em[j] else 115
                    if style == "pop":
                        parts.append(f"{{\\c{col}\\fscx85\\fscy85\\t(0,90,\\fscx{big}\\fscy{big})}}{t}{{\\r}}")
                    else:
                        parts.append(f"{{\\c{col}\\fscx{big - 5}\\fscy{big - 5}}}{t}{{\\r}}")
                elif is_em[j]:
                    parts.append(f"{{\\c{ec}\\fscx108\\fscy108}}{t}{{\\r}}")
                else:
                    parts.append(t)
            events.append((s, e, pos + " ".join(parts)))
    ass = header + "".join(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{t}\n" for s, e, t in events)
    srt_txt = "".join(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(srt, 1))
    return ass, srt_txt, len(chunks), len(emph)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("transcript")
    ap.add_argument("--map", help=".map.json from vlog_cut.py cut")
    ap.add_argument("--style", choices=["highlight", "pop", "plain"], default="highlight")
    ap.add_argument("--words", type=int, default=3, help="max words on screen at once")
    ap.add_argument("--position", choices=["auto", "top", "center", "lower"], default="auto")
    ap.add_argument("--color", default="yellow", help=f"highlight colour: {', '.join(COLORS)}")
    ap.add_argument("--no-upper", action="store_true", help="keep normal case (default is ALL CAPS)")
    ap.add_argument("--emphasis", default="auto", help='auto, none, or keywords to colour: "clutch,1v4,insane"')
    ap.add_argument("--emphasis-color", default="green", help="colour for emphasised words")
    ap.add_argument("--out", default="captioned.mp4")
    ap.add_argument("--files-only", action="store_true", help="only write .ass/.srt, don't render")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()

    info = probe(a.video)
    tr = load_json(a.transcript)
    words = [w for s in tr["segments"] for w in s.get("words", []) if w["w"].strip()]
    if not words:
        die("Transcript has no word timings. Re-run vlog_cut.py transcribe.")
    words = remap_words(words, load_json(a.map) if a.map else None)
    W, H = info["width"], info["height"]
    loud = word_loudness(a.video, words) if a.emphasis != "none" and info["has_audio"] else None
    ass, srt, n, n_em = build(
        words, W, H, a.style, a.words, a.position, a.color, not a.no_upper, a.emphasis, a.emphasis_color, loud
    )
    if a.emphasis != "none":
        print(f"  key word coloured in {n_em} of {n} caption groups")
    out = Path(a.out)
    out.with_suffix(".ass").write_text(ass, encoding="utf-8")
    out.with_suffix(".srt").write_text(srt, encoding="utf-8")
    print(f"{len(words)} words in {n} caption groups -> {out.with_suffix('.ass').name}, {out.with_suffix('.srt').name}")
    if not a.files_only:
        enc = ["-preset", "veryfast", "-crf", "24"] if a.preview else ["-preset", "medium", "-crf", "18"]
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            ass = safe_copy(out.with_suffix(".ass"), td, "caps.ass")
            vf = f"subtitles='{ff_path(ass)}'"
            if a.preview:
                vf = f"scale=iw/2:-2,{vf}"
            ffmpeg(
                [
                    "-i",
                    a.video,
                    "-vf",
                    vf,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    *enc,
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(out),
                ],
                hw=True,
            )
        print(f"Done -> {out}")
