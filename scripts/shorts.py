"""Turn one long video (stream, podcast, vlog, commentary) into ranked vertical Shorts.

Usage:
  python shorts.py VIDEO [--transcript tr.json] [--count 5] [--min 20] [--max 60]
                         [--out-dir shorts] [--render] [--pick 1,3,4] [--aspect 9:16] [--preview]

1. Candidates: stretches of whole sentences between --min and --max seconds.
2. Score 0-100 from four signals, each explained in the report:
   hook     the first sentence: a question, "you", a number, a strong word; not a filler opener
   energy   how loud and lively the stretch is compared with the rest of the video
   ending   finishes on a full stop, question or exclamation, not mid-thought
   pace     words per second in the range that holds attention on Shorts
3. The best non-overlapping candidates go to <out-dir>/shorts.json and shorts.md (with their
   transcripts, so Claude can read them and re-rank by what is actually said).
4. --render cuts each pick (or only --pick), reframes it vertical with face tracking and burns
   word-by-word captions: <out-dir>/short_01.mp4 ...

The score is a first pass. What makes a clip work is the content, so read the transcripts.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from common import die, extract_audio, load_json, need, probe, save_json

HERE = Path(__file__).resolve().parent
STRONG = {
    "insane",
    "crazy",
    "never",
    "secret",
    "worst",
    "best",
    "craziest",
    "biggest",
    "nobody",
    "everyone",
    "stop",
    "wait",
    "why",
    "how",
    "what",
    "mistake",
    "truth",
    "actually",
    "literally",
    "unbelievable",
    "first",
    "last",
    "only",
    "free",
    "money",
    "won",
    "lost",
    "win",
    "clutch",
    "broke",
    "hack",
    "trick",
}
WEAK_OPENERS = {"and", "so", "um", "uh", "but", "also", "like", "anyway", "then", "yeah", "okay", "ok", "because"}


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def sentences(transcript):
    """Flatten the transcript into sentences of words, splitting on . ! ? and long pauses."""
    words = [w for seg in transcript["segments"] for w in seg.get("words", [])]
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 9
        if w["w"].strip().endswith((".", "!", "?")) or gap > 0.9:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [s for s in out if s]


def loudness(video, dur):
    """RMS loudness per 0.5 s, normalised so the video's median is 1."""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        extract_audio(video, str(wav), sr=16000)
        import soundfile as sf

        x, sr = sf.read(str(wav), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = sr // 2
    n = max(1, len(x) // hop)
    rms = np.array([np.sqrt(np.mean(x[i * hop : (i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    med = np.median(rms[rms > 1e-4]) if np.any(rms > 1e-4) else 1.0
    return rms / max(med, 1e-6)


def score(cand, rms):
    first = cand["sents"][0]
    toks = [norm(w["w"]) for w in first]
    text_first = " ".join(w["w"] for w in first)
    hook, why = 0.0, []
    if text_first.strip().endswith("?"):
        hook += 0.35
        why.append("opens with a question")
    if {"you", "your", "you're"} & set(toks):
        hook += 0.2
        why.append("talks to the viewer")
    if any(t.isdigit() for t in toks):
        hook += 0.2
        why.append("has a number")
    hits = sorted(STRONG & set(toks))
    if hits:
        hook += min(0.35, 0.15 * len(hits))
        why.append("strong words: " + ", ".join(hits[:3]))
    if toks and toks[0] in WEAK_OPENERS:
        hook -= 0.3
        why.append(f'weak opener "{toks[0]}"')
    first_len = first[-1]["end"] - first[0]["start"]
    if first_len > 8:
        hook -= 0.15
        why.append("first sentence is long")
    hook = float(np.clip(hook, 0, 1))

    a, b = int(cand["start"] * 2), max(int(cand["start"] * 2) + 1, int(cand["end"] * 2))
    seg = rms[a:b] if a < len(rms) else np.array([1.0])
    energy = float(np.clip((np.mean(seg) - 0.7) / 0.8, 0, 1) * 0.7 + np.clip((np.max(seg) - 1.5) / 2.0, 0, 1) * 0.3)

    last = cand["sents"][-1][-1]["w"].strip()
    ending = 1.0 if last.endswith((".", "!", "?")) else 0.3
    if ending < 1:
        why.append("ends mid-sentence")

    n_words = sum(len(s) for s in cand["sents"])
    wps = n_words / max(cand["end"] - cand["start"], 0.1)
    pace = float(np.clip(1 - abs(wps - 2.9) / 1.6, 0, 1))
    if wps < 1.8:
        why.append("slow (long pauses)")

    total = round(100 * (0.4 * hook + 0.25 * energy + 0.15 * ending + 0.2 * pace))
    return {
        "score": total,
        "hook": round(hook, 2),
        "energy": round(energy, 2),
        "ending": ending,
        "pace": round(pace, 2),
        "words_per_sec": round(wps, 2),
        "notes": why,
    }


def candidates(sents, lo, hi):
    out = []
    for i in range(len(sents)):
        start = max(0.0, sents[i][0]["start"] - 0.15)
        for j in range(i, len(sents)):
            end = sents[j][-1]["end"] + 0.25
            d = end - start
            if d > hi:
                break
            if d >= lo:
                out.append({"start": round(start, 2), "end": round(end, 2), "sents": sents[i : j + 1]})
    return out


def pick(cands, count):
    chosen = []
    for c in sorted(cands, key=lambda c: -c["s"]["score"]):
        if all(c["end"] <= o["start"] or c["start"] >= o["end"] for o in chosen):
            chosen.append(c)
        if len(chosen) == count:
            break
    return chosen


def sub_transcript(transcript, start, end):
    segs = []
    for seg in transcript["segments"]:
        ws = [
            dict(w, start=round(w["start"] - start, 3), end=round(w["end"] - start, 3))
            for w in seg.get("words", [])
            if w["start"] >= start and w["end"] <= end
        ]
        if ws:
            segs.append(
                {
                    "id": len(segs) + 1,
                    "start": ws[0]["start"],
                    "end": ws[-1]["end"],
                    "text": " ".join(w["w"] for w in ws),
                    "words": ws,
                }
            )
    return {"language": transcript.get("language", "en"), "segments": segs}


def render(video, transcript, short, i, out_dir, aspect, preview):
    py = sys.executable
    base = out_dir / f"short_{i:02d}"
    cut = base.with_name(base.name + "_cut.mp4")
    d = short["end"] - short["start"]
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{short['start']:.3f}",
            "-i",
            str(video),
            "-t",
            f"{d:.3f}",
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
            str(cut),
        ],
        check=True,
    )
    vert = base.with_name(base.name + "_vertical.mp4")
    extra = ["--preview"] if preview else []
    subprocess.run([py, str(HERE / "reframe.py"), str(cut), "--aspect", aspect, "--out", str(vert), *extra], check=True)
    tr = base.with_name(base.name + ".transcript.json")
    save_json(sub_transcript(transcript, short["start"], short["end"]), tr)
    final = base.with_suffix(".mp4")
    subprocess.run([py, str(HERE / "captions.py"), str(vert), str(tr), "--out", str(final)], check=True)
    for f in (cut, vert):
        f.unlink(missing_ok=True)
    return final


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--transcript", help="transcript JSON from vlog_cut.py/listen.py (made if missing)")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--min", type=float, default=20.0, help="shortest short in seconds")
    ap.add_argument("--max", type=float, default=60.0, help="longest short in seconds")
    ap.add_argument("--out-dir", default="shorts")
    ap.add_argument("--render", action="store_true", help="cut, reframe vertical and caption the picks")
    ap.add_argument("--pick", help="render only these ranks, e.g. 1,3 (after reading the report)")
    ap.add_argument("--aspect", choices=["9:16", "4:5", "1:1"], default="9:16")
    ap.add_argument("--preview", action="store_true", help="fast half-resolution renders")
    a = ap.parse_args()
    need("ffmpeg")
    video = Path(a.video)
    info = probe(video)
    if not info["has_audio"]:
        die("This video has no audio track: /shorts picks moments by what's said.")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if a.transcript:
        transcript = load_json(a.transcript)
    else:
        from vlog_cut import transcribe

        transcript = transcribe(str(video))
        save_json(transcript, out_dir / f"{video.stem}.transcript.json")
    sents = sentences(transcript)
    if not sents:
        die("The transcript has no words with timings.")
    if a.min >= a.max:
        die("--min must be shorter than --max.")
    rms = loudness(video, info["duration"])
    cands = candidates(sents, a.min, a.max)
    if not cands:
        die(f"No stretch of whole sentences between {a.min:.0f} and {a.max:.0f} s. Try a wider --min/--max.")
    for c in cands:
        c["s"] = score(c, rms)
    best = pick(cands, a.count)
    shorts = []
    lines = [
        f"# Shorts from {video.name}",
        "",
        "Ranked by a first-pass score. Read the words: the content decides.",
        "",
    ]
    for rank, c in enumerate(best, 1):
        text = " ".join(w["w"] for s in c["sents"] for w in s).strip()
        hook = " ".join(w["w"] for w in c["sents"][0]).strip()
        shorts.append(
            {
                "rank": rank,
                "start": c["start"],
                "end": c["end"],
                "duration": round(c["end"] - c["start"], 1),
                **c["s"],
                "hook_line": hook,
                "text": text,
            }
        )
        mm = lambda t: f"{int(t // 60):02d}:{t % 60:04.1f}"  # noqa: E731
        lines += [
            f"## {rank}. {mm(c['start'])}-{mm(c['end'])}  ({c['end'] - c['start']:.0f} s)  score {c['s']['score']}",
            f"hook {c['s']['hook']} · energy {c['s']['energy']} · ending {c['s']['ending']} · "
            f"pace {c['s']['words_per_sec']} words/s" + (f" · {'; '.join(c['s']['notes'])}" if c["s"]["notes"] else ""),
            "",
            f"> {text}",
            "",
        ]
    save_json({"video": str(video.resolve()), "shorts": shorts}, out_dir / "shorts.json")
    (out_dir / "shorts.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(cands)} candidates, top {len(shorts)}:")
    for s in shorts:
        print(f'  {s["rank"]}. {s["start"]:7.1f}-{s["end"]:7.1f}s  score {s["score"]:3d}  "{s["hook_line"][:70]}"')
    print(f"Report -> {out_dir / 'shorts.md'}")
    if a.render:
        wanted = {int(x) for x in a.pick.split(",")} if a.pick else {s["rank"] for s in shorts}
        for s in shorts:
            if s["rank"] in wanted:
                f = render(video, transcript, s, s["rank"], out_dir, a.aspect, a.preview)
                print(f"Short {s['rank']} -> {f}")


if __name__ == "__main__":
    main()
