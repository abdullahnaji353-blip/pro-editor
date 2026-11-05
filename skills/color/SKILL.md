---
name: color
description: >
  This skill should be used when the user says "fix the colors", "color correct", "color grade",
  "it looks too dark", "it looks blue/yellow/green", "make it look cinematic", "warmer", "more
  vivid", "moody look", "vintage look", "give it a look", or invokes /color, usually for vlogs,
  travel and event footage. Measures and corrects exposure and colour casts, then applies an
  optional look.
metadata:
  version: "0.13.0"
---

# Color

Gaming montages grade themselves (the recipe's `color` block). This is for everything else, or
when the user wants a specific look.

## 1. Let them pick a look by eye

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/color.py looks <video>@<seconds> --out <work>/looks.png
```

(If the variable is empty, the scripts folder is two levels above this file.) Pick a frame that
represents the video (faces if it's a vlog). Show the grid: original, clean, warm, cinematic,
vivid, moody, vintage. Recommend one with a reason that fits the content:
- vlog / talking: clean or warm (skin tones matter most; avoid heavy looks on faces)
- travel / outdoors: vivid or warm
- night / city / emotional: moody or cinematic
- throwback / memories: vintage

## 2. Apply

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/color.py apply <video> --look <name> --strength 0.7 --compare --out <work>/graded.mp4
```

- `--strength` 0.4 subtle, 0.7 default, 1.0 full.
- `--look clean` = correction only. `--look none` = skip correction (look only makes sense with
  something else, so use clean in practice).
- Read the `.compare.png` before/after and check skin tones and skies didn't go strange.
- Every run also saves `<out>.cube`, the exact grade as a LUT. The user can load it in
  Premiere (Lumetri Color > Creative > Look), Resolve (Color page > LUTs, or the node's LUT
  menu), CapCut desktop (Adjust > LUT > Import) or Final Cut (Custom LUT effect) and reuse it on
  every clip from the same shoot. Vignette and grain (cinematic, moody, vintage) aren't colour, so
  they're not in the LUT: add them in the editor if they want them.
- `--lut-only` writes just the LUT, no render. Use it for long or 4K videos the user will finish
  in their own editor: the editor applies a LUT in real time on the graphics card, which beats a
  full extra render here.

## Order with other steps

Colour after cutting (less to render) and before captions/text (so text stays pure white):
`/vlog-edit` cut → reframe → **color** → captions → `/export`. For travel: scenic highlights →
**color** on the clips (or on the finished montage) → `/export`.

Be honest that auto correction is a starting point: mixed lighting (window + lamp) can't be fully
fixed by one global correction.

## Every edit: your rules, then a check before you show it

- **Their rules first.** Read `pro-editor-rules.md` in the footage folder if it exists; its rules
  beat this skill's defaults. When a note is lasting (it says always or never, it's about their
  style, or the same kind of note comes twice), add it there as one line with their own words and
  the date, and confirm in one line: "Saved as a rule: ...". One-off notes stay one-off.
- **Check the render before showing it**: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_render.py <video> --out-dir <work>/check`
  (pass `--cuts` when you know them). Read `report.md` and look at `cuts.png`: clicks at cuts,
  a section 10+ dB quieter than the rest, black or frozen stretches, a cut on the wrong frame.
  Fix and re-check, at most 3 rounds, then tell the user what's left instead of looping. You can't
  hear it: report the measured loudness, never "it sounds good".
- **Something they'll publish** (a launch, an ad, a channel trailer): before calling it done, spawn
  one critic sub-agent with the video's check report, frame strips and the plan, briefed to roast
  it: a verdict, problems ranked with timestamps, and the five fixes to make first. Fresh eyes
  catch the cut-off punchline and the 28 px text you stopped seeing.
