---
name: vlog-edit
description: >
  This skill should be used when the user is editing talking footage or a vlog: "cut out the
  silences", "remove the ums", "jump cut this", "edit by transcript", "cut my bad takes", "add
  captions", "word by word subtitles", "make it vertical and keep me in frame", "clean up my
  audio", "my mic sounds bad", "edit my vlog", "day in my life", "podcast clip", "commentary".
  Handles transcripts, automatic jump cuts, editing by deleting text, retake spotting, animated
  word-by-word captions, face-tracking vertical crops, voice cleanup, punch-in zooms and
  YouTube chapters.
metadata:
  version: "0.7.0"
---

# Vlog Edit

Talking videos live or die on pacing and clarity: no dead air, no rambling, readable captions,
clean voice. This skill does the grunt work so the user can focus on the story.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session. Transcripts need the optional
`faster-whisper` package and face tracking needs `opencv-python-headless<5`; ask before
installing either. The first transcript downloads a speech model (a few hundred MB for "small").

## The usual order

0. **Checkup**: `python3 $S/checkup.py <video> --fix --out-dir <work>/checkup`. Phone footage is
   often variable frame rate (audio drifts after jump cuts) or HDR (washes out). Edit the fixed copy.
1. **Clean the voice** (before cutting, so cuts sound even):
   `python3 $S/voice.py <video> --strength medium --out <work>/clean.mp4`
   light = good mic, quiet room; medium = default; strong = noisy room or phone mic (preview it,
   it can sound processed). It measures the recording's own noise floor, denoises, pushes hiss
   down between sentences, tames harsh "s" sounds, and evens out volume without killing hype moments.
2. **Transcribe**: `python3 $S/vlog_cut.py transcribe <work>/clean.mp4 --out <work>/transcript.json`
   (`--model medium` for accents/noisy audio, `--language en` to skip detection, `--audio-track N`
   for multi-track recordings).
3. **Script (edit by text)**: `python3 $S/vlog_cut.py script <work>/clean.mp4 <work>/transcript.json --out <work>/script.txt`
   Read the script yourself. Lines flagged `RETAKE?` repeat in the next line or two: usually the
   first take goes. Also suggest cutting rambling, repeated points, "anyway so yeah" filler
   sentences and a slow intro (the first line should be the hook, not "hey guys"). Show the user
   your proposed cuts with line numbers and let them decide, then delete those lines (or put `#`
   in front) in a copy of the script.
4. **Cut**:
   `python3 $S/vlog_cut.py cut <work>/clean.mp4 --transcript <work>/transcript.json --script <work>/script_edit.txt --fillers --out <work>/cut.mp4`
   Removes deleted lines, silences (pauses over `--min-silence` 0.45s, keeping `--pad` 0.12s of
   breathing room) and um/uh fillers. Writes `cut.map.json` and `cut.xml` (Premiere/Resolve
   timeline with every jump cut, video + audio). Without a transcript it still cuts silences.
   Pace guide: `--min-silence 0.3 --pad 0.08` = punchy short-form; `0.6 / 0.15` = relaxed long-form.
   **Punch-ins** (`--punch-in 1.12`): every other piece is zoomed in slightly, so jump cuts look
   like a second camera angle instead of a glitch. That's the standard YouTube talking-head trick.
   `--punch-center 0.4` if the face sits left of centre. On 4K footage the zoom is free; on 1080p
   it costs a little sharpness (1.08-1.12 is fine, avoid going past 1.15). Skip it for vertical
   videos that will be reframed (the reframe already crops in).
5. **Vertical** (for Shorts/TikTok/Reels): `python3 $S/reframe.py <work>/cut.mp4 --out <work>/vertical.mp4`
   Follows the face like a camera operator (holds still for small moves, glides when they leave
   the middle). Two people or the wrong face picked: `--keyframes "0:0.3,12:0.7"` (time:centre).
   Check a few frames; detection struggles with side profiles, sunglasses, dark scenes.
6. **Captions**:
   `python3 $S/captions.py <work>/vertical.mp4 <work>/transcript.json --map <work>/cut.map.json --out <work>/final.mp4`
   Word-by-word, active word highlighted, ALL CAPS, inside the safe zone. `--style pop` (word pops
   in), `--style plain`, `--color green|cyan|pink|red|white`, `--words 2` for faster reading,
   `--position top|center|lower`, `--files-only` for just .ass/.srt (upload the .srt to YouTube
   for accessibility). Always pass `--map` when the video was cut, so captions follow the edit.
   Spot-check names, slang and game terms in the transcript before burning in; fix them in
   `transcript.json` ("w" fields) and re-run.
7. **Colour** (before captions, so caption text stays pure white): `/color`, usually `clean` or
   `warm` for faces. Then run captions on the graded file. It also saves the grade as a `.cube`
   LUT the user can load in their own editor.
8. **Chapters** (YouTube, long-form): read the script for topic changes and pick 3+ chapter
   starts with short, specific titles, then
   `python3 $S/chapters.py <work>/transcript.json --at "1:Intro" "14:Trying the new map" "31:Final verdict" --map <work>/cut.map.json --video <work>/final.mp4 --out <work>/final_chapters.mp4 --txt <work>/chapters.txt`
   Line numbers are the `[0014]` tags in the script (`14` works). Times follow the cut, chapters under 10 s are merged, the
   first one starts at 0:00, and they're embedded in the file too. The `.txt` goes in the
   YouTube description. Show the user the list before rendering anything else.
9. **Export** with `/export` (platform sizes, loudness, post copy) and a thumbnail with `/thumbnail`.

Steps are independent: skip what the user doesn't need (a horizontal YouTube vlog skips step 5).

## Long recordings (20-45+ min)

- Tell the user up front which steps take a while: transcribing (CPU: roughly the video's own
  length or longer with the "small" model; an NVIDIA GPU is much faster; `--model base` trades a
  little accuracy for speed), and every step that re-renders the whole video (checkup --fix,
  voice, cut, reframe, color, captions, export), each about as long as an export in a normal editor.
- Keep the number of full renders down: do previews (`--preview`) while deciding, then the final
  versions once. Burned-in captions and colour on a 45-minute file are each a full render.
- Disk: cutting writes temporary pieces before joining them; keep roughly 10-20 GB free for a
  45-minute 1080p recording.
- If the session allows, run long steps in the background and tell the user they can leave it.
- High-resolution footage (1440p/4K): final renders use the graphics card's encoder when it
  works and fall back to the CPU automatically. `python3 $S/selftest.py` prints how many minutes
  of rendering one finished minute takes on their computer; quote that instead of guessing.
  For colour on a long 4K file, `color.py apply --lut-only` makes just the `.cube` LUT to drop
  into Premiere/Resolve/CapCut, which apply it in real time, instead of a full extra render.

## Mixing with other skills

- B-roll / travel shots between talking parts: `/highlights --mode scenic` to find the best
  shots, then `/long-video` sections (raw talking parts + montage parts with music that ducks
  under the voice).
- Funny moments in long recordings: `/highlights --mode reactions`.
- A music-driven recap of a trip or event: `/montage` with scenic highlights.
- Feedback on the user's own vlog edit: `/edit-review` (pacing, dead spots, hook, loudness).

## Honesty notes

- Transcripts are good but not perfect: they mishear names and slang. Say so and check them.
- Jump cuts can feel choppy on slow, emotional moments. For those, cut less (`--min-silence 0.8`)
  or leave that part out of the cut and keep it natural.
- Never invent or reword what the person said; only remove.
