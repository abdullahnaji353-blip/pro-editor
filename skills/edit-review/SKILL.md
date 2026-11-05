---
name: edit-review
description: >
  This skill should be used when the user asks "review my edit", "what's wrong with my edit",
  "rate my edit", "how do I make this better", "is this on beat", "compare my edit to this
  style", or shares an edit they made and wants feedback. Breaks the edit down like a coach:
  off-beat cuts with exact timestamps and frame offsets, dead spots, hook, ending, loudness,
  and how it compares to a target style.
metadata:
  version: "0.7.0"
---

# Edit Review

Honest, specific feedback on an edit the user made, so they get better at editing.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing.

## Run

```
python3 $S/review_edit.py <their edit> [--song <song file> --song-start <s>] \
    [--recipe <target recipe.json>] --out-dir <work>/review
```

- Ask for the song file and where in the song the edit starts whenever beat sync matters.
  Beats tracked from the clean song are reliable; beats tracked from a finished edit get
  muddied by game sounds, voice and effects, which can make good cuts look off-beat.
- Pass `--recipe` when they're aiming at a style (from `/style-match` or `/trends`). Then read
`review.json` and look at `_sheet.png` / `_cuts.png` if images can be viewed.

## How to give the feedback

Be on their side, not on the edit's side. The user wants to improve, so:

1. **Lead with 1-2 things that genuinely work** (from `good`), specific not generic.
2. **Top 3 fixes, ranked by impact.** Usually: hook > sync > pacing > audio > color. Each fix
   gets the exact timestamp, what to do, and why it matters. Example: "Cut at 7.47s lands 7
   frames before the snare at 7.69s. Slide it right so the hit lands on the snare."
3. **What the numbers can't judge**, from looking at the frames: clip choice (is the best play
   first?), text readability, whether effects feel motivated or random, framing.
4. One sentence on the single thing to practice next.

Don't pad with praise. If the edit is rough, say so kindly and specifically. If it's strong,
say that too without inventing problems.

## Caveats to keep in mind (mention only when relevant)

- Without `--song`, off-beat flags are hints, not facts. The script notes when the beat grid
  looks shifted (`beat_grid_suspect`); in that case say the tracker is unsure and don't tell the
  user to move cuts. Either way, tell them to check a couple against the waveform first.
- Hard cuts inside visually similar footage (same map, same skin) can go undetected, so the cut
  count may be a bit low.
- Loudness: platforms play around -14 LUFS. Under -18 sounds weak; peaks above -1 dB risk
  clipping.

## Teach mode

Only explain the theory (why cutting on the snare feels better, what a J-cut is, how speed ramps
work) when the user asks. Default to the short, actionable version.
