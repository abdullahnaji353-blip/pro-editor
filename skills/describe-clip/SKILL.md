---
name: describe-clip
description: >
  This skill should be used when the user describes a moment or an edit in plain words:
  "find the clip where I clutched a 1v3 with the shotgun", "the goal I scored off the ceiling",
  "the part where we jump in the pool", "the sunset shot",
  "that time I fell off the map", "slow-mo the last kill then speed back up", "put a freeze frame
  on the elimination", "what's in this recording", "label my clips", or invokes /describe-clip.
  Understands whether they want to FIND a moment in their footage, EDIT a clip the way they
  describe, or LABEL/catalog clips, and handles combinations of these.
metadata:
  version: "0.7.0"
---

# Describe Clip

The user describes; Claude figures out what they mean and does it. Footage becomes searchable
through a clip library: timestamped frame sheets that Claude reads, plus labels Claude writes.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing. Library commands below are
`python3 $S/library.py --lib <work>/clip-library ...` (shortened to `lib` here).

## 1. Work out the intent

Read the request and decide, without asking unless it's genuinely unclear:

- **FIND**: describes a past moment ("the 1v3", "when I hit the flip reset") → locate and cut it.
- **EDIT**: describes how a clip should look ("slow-mo the last kill") → apply it with `clip_fx.py`.
- **LABEL**: wants to know what's in footage or organize it → index + label.
- **Combos** are common: "find the 1v3 and slow-mo the last kill" = FIND then EDIT.

If the description could match several moments, find all candidates and let the user pick.

## 2. Make sure the footage is indexed

```
lib status                          # what's indexed
lib index <recordings or folder>    # fast: keyframes, ~1 frame / 4s
lib index <short clips> --accurate --every 1    # clips under ~2 min: denser, exact spacing
```

Tell the user the sampling rate. A moment shorter than the gap between samples can be missed,
so confirm candidates with `zoom` before acting.

## 3. Read sheets and label

`lib next --n 4` lists the hottest unreviewed sheets (loudest moments first) with each tile's
time. Read the sheet images. For every moment worth keeping:

```
lib add <VIDEO_ID> <start> <end> --tags elimination,shotgun,1v3,endgame --desc "..." --quality 4 --game fortnite
lib reviewed <VIDEO_ID> 1-4
```

Visual cues to look for:
- Fortnite: kill-feed lines and "ELIMINATED" / elimination popups, the elim counter going up,
  knocked/downed players, storm/zone circle (endgame), "#1 VICTORY ROYALE", build fights
  (lots of walls/ramps), spectating screens (= you died).
- Rocket League: goal explosion, scoreboard change, "REPLAY" banner, car high in the air
  (aerial), ball near the ceiling/wall, saves (ball stopped at the goal line), demo explosions.
- Vlogs / travel / events: people and faces (who, laughing, talking to camera), places (beach,
  street, food, view), actions (jumping in, opening a gift, walking in), lighting (golden hour,
  night). Tag them the same way: `talking`, `laughing`, `food`, `view`, `sunset`, `group`, `arrival`.
- Funny moments: mostly in the audio, so sheets alone often miss them; run
  `highlights.py --mode reactions` and label those windows too.

Tag vocabulary (search understands synonyms): elimination, knock, clutch, 1v2/1v3/1v4, win,
shotgun, sniper, build, edit-course, goal, save, aerial, flip-reset, freestyle, demo, fail,
funny, reaction, early, midgame, endgame. Quality: 5 = would open a montage with it,
3 = solid filler, 1 = skip. Skip lobbies, menus, walking, loading.

Budget for long footage: a 45-min recording at 4s spacing is ~45 sheets. For FIND, review
hottest-first and stop when the moment is found. For a full LABEL pass, work in batches and tell
the user progress ("labeled 12/45 sheets, 9 clips so far").

## 4. FIND

1. `lib search "<their words>"`; strong match → go to step 3.
2. No match: scan unreviewed sheets hottest-first for the described cues, labeling as you go.
3. Confirm with an exact window: `lib zoom <VIDEO_ID> <start-3> <end+3> --step 0.5`, read it,
   and set tight in/out points (start a beat before the action, end after the payoff).
4. `lib cut <CLIP_ID>` (or `<VIDEO_ID>@start-end`). Show the user the zoom sheet frame or
   timestamps so they can confirm it's the right moment, especially when unsure.

## 5. EDIT

Translate the description into `clip_fx.py` ops (format in the docstring at the top of
`$S/clip_fx.py`). Use the zoom sheet to find the exact second of the key moment.

| They say | Ops |
|---|---|
| slow-mo on X | `speed` 0.35-0.5 from ~0.3s before X to ~0.8s after |
| speed up / skip the boring part | `speed` 1.5-2.5 over that range |
| velocity / ramp into X | `ramp` at X (fast 2.0, slow 0.4) |
| freeze on X / "wait for it" | `freeze` at X, 0.5-1s, often with `text` |
| hit it hard / impact | `zoom` + `flash` + `shake` at X |
| glitch | `rgb` at X |
| caption / hook text | `text` (keep to 1-4 words) |
| to music | `music` block; ask which song and where in it |

Render `--preview` first, check the printed time map, look at a few frames, then render full
quality when the user is happy. For vertical posts set `"aspect": "9:16"` (`"fit": "blur"` keeps
the whole gameplay frame).

## 6. LABEL / "what's in this?"

Index, review sheets, add labels, then summarize: number of moments by type, the 3 best (with
timestamps), and dead stretches the user could cut. The labels persist, so later
`/describe-clip` and `/montage` requests reuse them (`lib search`, then cut the best ones into a
folder for `build_montage.py --clips`).
