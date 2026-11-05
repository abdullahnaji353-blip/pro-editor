---
name: shorts
description: >
  This skill should be used when the user invokes /shorts, or says "make shorts from this",
  "clip my stream", "turn my podcast into TikToks", "find the best moments for Reels", "cut this
  long video into clips", "repurpose this video", or hands over a long talking video (stream,
  podcast, commentary, vlog, interview) and wants several short vertical clips from it. Finds
  self-contained moments, ranks them by hook, energy, ending and pace, reads them to judge the
  content, then renders vertical clips with face tracking and word-by-word captions.
metadata:
  version: "0.9.0"
---

# Shorts

One long video in, a handful of ready-to-post vertical clips out. For gameplay without much talking,
use `/highlights` + `/montage` instead: this one picks moments by what is said.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call
it `$S`. Needs `faster-whisper` for the transcript and `opencv-python-headless` for face tracking;
check with `python3 $S/check_setup.py` and ask before installing.

## 1. Find and rank

```
python3 $S/shorts.py <video> --count 6 --min 20 --max 60 --out-dir <work>/shorts [--transcript tr.json]
```

Reuse a transcript if `/talk` or `/vlog-edit` already made one. Lengths: 20-45 s for TikTok and
Reels, up to 60 s for Shorts; ask only if the user cares. It writes `shorts.md` (each candidate's
score, why, and full text) and `shorts.json`.

## 2. Read them before picking (this is the important part)

The score is a first pass: hook words, loudness, clean ending, pace. It can't tell whether a story
lands. Read every candidate in `shorts.md` and judge it like an editor:

- Does the first sentence make someone stop scrolling? If the real hook is one sentence later,
  say so and suggest trimming the start.
- Does it make sense with no context from the rest of the video?
- Is there a payoff (a punchline, an answer, a result) before it ends?

Re-rank with your reasons, then show the user the top picks: timecodes, the hook line, one line on
why, and a suggested title for each. Let them choose.

## 3. Render the chosen ones

```
python3 $S/shorts.py <video> --transcript <work>/shorts/<name>.transcript.json --out-dir <work>/shorts \
  --render --pick 1,3,4 --preview
```

`--preview` first (fast), check a frame of each, then render without it. Each short is cut on
sentence boundaries, reframed to 9:16 following the speaker's face, and captioned word by word.
If a hook needs trimming, cut with `vlog_cut.py cut --remove` on the short before captioning, or
re-run with a narrower `--min/--max`.

## 4. Finish

Offer `/export` for platform versions, titles and hashtags, and `/thumbnail` for a cover. Say
plainly what the score can't judge: whether a joke is funny, or whether a clip needs context the
viewer won't have.
