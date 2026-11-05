---
name: highlights
description: >
  This skill should be used when the user wants to "find the best moments", "pull highlights",
  "find my kills", "find the goals", "clip the good parts", "go through my recording", "find the
  best shots from my trip", "best b-roll", or hands over long gameplay, vlog, travel or event
  footage to turn into short clips. Scores footage by action and sound (gaming), voice reactions
  (funny moments) or how good it looks (travel/events), and cuts out the top moments.
metadata:
  version: "0.7.0"
---

# Highlights

Shortlist the best moments from long recordings so the user doesn't scrub hours of footage.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing.

## Check the audio tracks first

```
python3 $S/highlights.py <recordings or folder> --tracks-only
```

- **2+ tracks** (OBS multi-track, some capture apps): the mic is likely on its own track.
  Use the game-only track for scoring with `--audio-track N` (titles like "Game"/"Desktop"
  help; if untitled, track 0 is usually the full mix, so try 1 for game-only, and ask the user
  if unsure).
- **1 track**: voice may be mixed in, and the plugin can't separate it reliably. Ask the user
  whether they talk in their recordings. If they're not sure, tell them to play 30 seconds and
  listen. If voice is mixed in, expect highlights to follow their loud reactions, and suggest
  recording game and mic on separate tracks next time (OBS: Settings > Output > Recording >
  Audio Track 1 + 2, then assign tracks in Advanced Audio Properties).

## Run

```
python3 $S/highlights.py <recordings or folder> --top 10 --pre 3 --post 2 [--audio-track N] \
    --out <work>/highlights.json --export-dir <work>/clips
```

- `--top`: moments kept per recording. Rough guide: 1 per 2-3 minutes of footage, max ~15.
- `--pre/--post`: seconds kept before/after the peak. Fortnite fights: `--pre 4 --post 2`.
  Rocket League goals: `--pre 5 --post 3` (the build-up matters).
- `--min-gap`: minimum seconds between highlights (default 8).
- `--min-score`: weak picks below this are dropped (default 0.5), so fewer, better clips.
- `--context 8` (default): extends the lead-in back to where the action starts (up to 8s extra),
  so a clip has setup → moment → reaction instead of starting mid-fight. `--context 0` = fixed `--pre`.
- `--mode scenic`: for travel, events, vlogs and b-roll. Scores how good each second LOOKS
  (sharp, colourful, well exposed, some movement), keeps shots that look different from each
  other, and keeps each clip inside one shot. Audio is ignored. Suggest `--min-gap 6` for variety.
- `--mode reactions`: for funny moments. Scores the voice band (yells, laughs) instead of game
  action, with longer lead-in (5s) and follow-through (4s). Use `--audio-track` on the mic
  track when there is one. Run it as a second pass next to the default action mode.
- `<work>` = a `pro-editor` folder next to the footage.

## Be honest about what it finds

The detector finds moments that are LOUD and BUSY: gunfire, elimination sounds, goal
explosions, the player hyping on mic. It does not know if a play was good. Expect misses
(quiet clutch plays, clean edits) and false hits (dying loudly, menu music, a dog barking).

So after running:

1. List the clips with rank, source and timestamps.
2. If the session can view images, grab a frame per clip at its peak
   (`ffmpeg -ss <peak> -i <source> -frames:v 1 -vf scale=480:-2 <work>/peek_<rank>.png`)
   and skim them to flag obvious junk (lobby, death screen, menus).
3. Ask the user to drop any duds or name moments it missed (they can give timestamps).
   Edit `highlights.json` accordingly: delete entries or add
   `{"source": "...", "start": s, "end": e, "score": 5}` for manual picks
   (a high score makes the montage save that clip for the drop).

To know what's actually in each clip (or find one specific moment), use `/describe-clip`;
it can label these highlights so they become searchable.

Then offer `/montage` with `--highlights <work>/highlights.json`.
