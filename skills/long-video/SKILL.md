---
name: long-video
description: >
  This skill should be used when the user wants a long-form video (several minutes up to 45+
  minutes): "make a YouTube video", "long montage with multiple songs", "put my gameplay together
  with edits", "compilation", "stitch these sections", "add chapters". Builds the video from
  sections (beat-synced montage parts and raw gameplay parts with their own audio), joins them
  with transitions, normalizes loudness, and writes YouTube chapters.
metadata:
  version: "0.8.0"
---

# Long Video

Montage sections + raw gameplay sections → one long video with chapters.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing.

## Plan the structure with the user first

Ask about the shape before rendering anything long. A good default for a gaming video:

1. **Cold open** (montage, 10-25s): best moments on a hype song. This is the hook.
2. **Main content** (raw sections): matches or sessions, trimmed of dead time (lobby, walking,
   loading). Run `/highlights` on long recordings to find where the action is and trim around
   it, or ask the user for start/end times.
3. **Mid-video montage(s)** to break up long raw stretches every 5-10 minutes.
4. **Outro montage** (optional).

Write `<work>/project.json` (format documented at the top of `$S/stitch.py`):
- `"type": "montage"` sections take `song`, `song_start`, `length`, `clips` or `highlights`,
  and `recipe` (same as `/montage`).
- `"type": "raw"` sections take `source`, `start`, `end` (seconds), `audio_track` (pick the
  game or mixed track; check with `highlights.py --tracks-only`), optional `music` bed at
  `music_volume` 0.08-0.15 under commentary, and `show_title` for a title card. Music beds duck
  automatically when the voice band gets loud (`"duck": false` to turn off): the bed sits well
  under the voice and dips further while you talk or yell, then comes back.
- `transition`: `"fade"` (dip to black, safe default), `"flash"` (dip to white, hype), or `"cut"`;
  `{"type": "fade", "duration": 0.6}` to change how long it takes.
- `format.aspect`: 16:9 for YouTube long-form. `format.resolution`: 1080 (default), 1440,
  2160 or `"source"` (matches the footage, capped at 4K). For 1440p/4K footage, YouTube generally
  streams 1440p/4K uploads at higher quality than 1080p ones, so suggest `"source"`; it costs render
  time (roughly 2x for 1440p, 4x for 4K; `python3 $S/selftest.py` measures their computer).

Give each section a real `title`; titles become the chapters.

## Render: preview first, always

```
python3 $S/stitch.py <work>/project.json --preview --out <work>/preview.mp4 --work-dir <work>/sections
```

- `--only N` renders just section N for a quick check.
- Sections are cached: after the user changes one section, re-running only re-renders that one.
- Full quality: same command without `--preview`, to a new `--out`. Warn about time first: a
  45-minute 1080p60 render can take 30-90+ minutes depending on the computer (4K several times
  that; a graphics-card encoder, used automatically when present, cuts it a lot). Run it in the
  background if the session allows, and tell the user they can keep the computer on and walk away.
  Free disk: about 10-20 GB for 1080p, 40+ GB for 4K.

## Deliver

- The MP4 (chapters are embedded).
- `<out>_chapters.txt`: paste into the YouTube description. YouTube needs 3+ chapters starting
  at 0:00, each at least 10 seconds.
- The per-section `.xml` timelines from montage sections, for polishing in Premiere/Resolve.
- Offer a thumbnail with `/thumbnail` (long-form lives or dies on it) and post copy (title,
  description with the chapters, tags) from `/export`.
- For talking parts without titled sections, chapters come from the transcript instead: see
  step 8 of `/vlog-edit` (`chapters.py`).
