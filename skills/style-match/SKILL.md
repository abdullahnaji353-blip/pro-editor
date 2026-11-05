---
name: style-match
description: >
  This skill should be used when the user wants to "copy the style of this edit", "edit it like
  this video", "recreate this edit", "match this editor's style", "make it look like these
  references", sends 1-3 reference videos to learn from, or names an editing style ("velocity
  edit", "clean Fortnite montage", "Rocket League freestyle edit") to base a montage on.
  Breaks reference edits down into a reusable style recipe (pacing, beat sync, color, effects)
  that the montage skill applies to the user's own footage.
metadata:
  version: "0.8.0"
---

# Style Match

Turn 1-3 reference edits into a `recipe.json` that `/montage` applies to the user's clips.

## Locate the scripts

The scripts live in the plugin's `scripts/` folder: `${CLAUDE_PLUGIN_ROOT}/scripts`. If that
variable is empty, use the folder two levels above this SKILL.md (`../../scripts`). Call it
`$S` below. Run Python as `python3` (on Windows: `python` or `py`).

On first use in a session, run `python3 $S/check_setup.py`. If anything is MISSING, show the
user the install commands it prints and ask before installing anything on their computer.

## Get the references

- Ask for the actual video files (2-3 is the sweet spot; 1 works). Gameplay edits from the same
  editor give the cleanest recipe.
- Never download videos from Instagram, TikTok or YouTube with rippers or downloader sites. If
  the user only has a link, ask them to save the file themselves or screen-record it.
- Reference files are for analysis only. Never put another creator's footage into the user's
  montage or suggest reposting it.
- No files, only a style name or "whatever's trending": use the `/trends` workflow (live
  research → recipe). Tell the user it's an approximation built from descriptions, not
  measured from real edits.

## Analyze

```
python3 $S/analyze_style.py REF1 REF2 REF3 --out-dir <work>/style --name <short-style-name>
```

`<work>` is a `pro-editor` folder next to the user's footage (or the session's working folder).
It prints shots, median shot length, beat sync vs random, and tempo per reference, and writes
`recipe.json`, `<ref>_stats.json`, `<ref>_sheet.png` (one frame per shot) and `<ref>_cuts.png`
(frames just before/on/after the first cuts).

## Read the numbers like an editor

- `median_shot_sec` and `cut_every_beats`: the pace. Under 0.4s = hyper-fast velocity style;
  1-2s = clean/cinematic.
- `beat_sync_pct` vs `random_sync_pct`: only call it beat-synced if sync clearly beats random
  (15+ points). The recipe sets `snap_cuts_to_beats` from this.
- `flashes_per_min`, `motion_intensity`: hints for flash and shake effects.
- `color`: target brightness/saturation/contrast the montage grades toward.

## Look at the sheets (required)

Read every `_sheet.png` and `_cuts.png` image. Numbers miss half the style. Check for:

- Zoom punches (consecutive frames scaling in) and shake (frame offset/blur)
- Speed ramps: motion-blurred frames then crisp slow ones → `velocity`
- Color fringing at cuts → `rgb_split_on_beats`
- Transitions at cuts: hard cut, white/black flash, whip/blur
- Text: present? position, size, outline vs boxed, all caps?
- Letterbox bars, vignette, overlays, grain
- Color mood: crushed blacks, oversaturated, teal-orange, washed-out
- Aspect ratio and whether gameplay is cropped or sits on a blurred background

Then edit `recipe.json` → `effects` to match what the sheets show (field reference in
`references/recipe-format.md`) and delete the `_note` line. Don't leave the auto-guesses in
place if the frames contradict them.

## Report back

Give the user a short, plain breakdown: pace (cuts per beat / seconds per shot), how tightly it
hits the beat, the look, the effects found, and what the recipe can't copy (hand-keyframed
velocity curves, motion blur, 3D camera moves, custom overlays, sound design). Offer to run
`/montage` with their clips next, or `/edit-review` on one of their own edits with
`--recipe` to see how far their style is from this one.

If the user is studying a specific editor to apply for a job or collab, point out that the
breakdown is a study guide: the application edit should be theirs, not generated.
