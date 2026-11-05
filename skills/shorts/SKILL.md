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
  version: "0.13.0"
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

## Every edit: your rules, then a check before you show it

- **Their rules first.** Read `pro-editor-rules.md` in the footage folder if it exists; its rules
  beat this skill's defaults. When a note is lasting (it says always or never, it's about their
  style, or the same kind of note comes twice), add it there as one line with their own words and
  the date, and confirm in one line: "Saved as a rule: ...". One-off notes stay one-off.
- **Check the render before showing it**: `python3 $S/check_render.py <video> --out-dir <work>/check`
  (pass `--cuts` when you know them). Read `report.md` and look at `cuts.png`: clicks at cuts,
  a section 10+ dB quieter than the rest, black or frozen stretches, a cut on the wrong frame.
  Fix and re-check, at most 3 rounds, then tell the user what's left instead of looping. You can't
  hear it: report the measured loudness, never "it sounds good".
- **Something they'll publish** (a launch, an ad, a channel trailer): before calling it done, spawn
  one critic sub-agent with the video's check report, frame strips and the plan, briefed to roast
  it: a verdict, problems ranked with timestamps, and the five fixes to make first. Fresh eyes
  catch the cut-off punchline and the 28 px text you stopped seeing.
- **Faster transcripts**: `--model groq` sends the audio to Groq's hosted Whisper large-v3 (free
  key from console.groq.com, `GROQ_API_KEY`). Minutes instead of an hour on a slow laptop, but the
  audio leaves their computer, so offer it and use it only if they say yes.
