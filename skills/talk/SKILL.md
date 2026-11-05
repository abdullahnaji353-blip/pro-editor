---
name: talk
description: >
  This skill should be used when the user invokes /talk, or says "listen to my video", "hear what I
  said", "I told you what to do in the video", "follow what I said while recording", "I said clip
  that", "use my voice note as instructions", "here's a voice message with what I want", or sends a
  recording where they talk (vlog, commentary, gaming with friends) and wants the edit to follow
  what was said. Hears everything (words, laughter, shouting, cheering, music, game sounds), finds
  spoken instructions ("clip that", "Claude, zoom in here", "cut that", "let me redo that"), thinks
  through what the user wants together with any typed prompt, then edits.
metadata:
  version: "0.8.0"
---

# Talk

The user talks; Claude listens to all of it and turns it into an edit. There are three kinds of
input, and any mix of them is fine:

1. **Footage where they talk**: vlogs, commentary, gaming with friends. Instructions can be spoken
   while recording ("clip that", "Claude, slow mo that").
2. **A voice note** with instructions ("make the intro faster, put the clutch first...").
3. **A typed prompt** alongside either one.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call
it `$S`. Words need `faster-whisper`. Sounds (laughter, cheering, gunfire...) need `mediapipe`;
the 4 MB sound model downloads once. Check with `python3 $S/check_setup.py` and ask before
installing. Without MediaPipe it still hears words and loudness.

## 1. Listen

Footage:
```
python3 $S/listen.py hear <video> --out-dir <work>/talk --hotwords "<names, game, slang>" [--audio-track N] [--language xx] [--multilingual]
```
- `--hotwords`: the user's name, friends' names, the game, map names, slang. Take them from the
  prompt and the context; they fix most misspellings. "Claude" and "clip that" are always added.
- The speaker switches languages (Arabic and English, say): `--multilingual`. A single known
  language: `--language ar` / `en` (faster, and avoids a wrong guess).
- Recordings with the mic on its own track (OBS): pass that track with `--audio-track`. Check
  with `python3 $S/highlights.py <video> --tracks-only`.
- If a transcript already exists from `/vlog-edit`, pass `--transcript` to skip transcribing again.

Voice note:
```
python3 $S/listen.py prompt <voice_note> --out <work>/talk/prompt.txt
```
Treat that text exactly like a typed prompt.

## 2. Read everything it heard

Read `<work>/talk/<name>.talk.md` in full: spoken instructions (with what each one applies to),
moments (laughing, shouting, cheering, music, gunfire/explosions, engines, loudest spots), and the
whole transcript. On long videos, read the transcript in chunks; don't skim past the middle.

## 3. Think it through properly before editing

Work out, and write down briefly for the user:

- **The goal.** What they asked for in words (typed or voice), and the platform, length and vibe.
  If they didn't say, infer it from the footage (gaming clips with "clip that" callouts are
  short-form highlights; a 20-minute sit-down vlog is long-form) and say what you assumed.
- **Every spoken instruction, interpreted.** For each: what was said, what it means, which part
  of the video it applies to, and how sure you are. "Here/this" usually means the part after the
  command and "that/it" the part before, but read the transcript around it and decide like an
  editor would. Anything marked `[confirm]` (retakes, mid-sentence "cut that", unclear wording) gets
  checked against the transcript; ask about it only if it's still ambiguous.
- **Conflicts.** The typed or voice prompt wins over something said casually in the footage, and
  a later instruction wins over an earlier one. Say when one overrides the other.
- **What the footage itself says.** The story or arc, the strongest hook (often a callout or the
  biggest laugh), dead stretches, and repeated takes. A callout or a big laugh is the best signal
  of a good moment; loudness alone isn't (game explosions are loud too).
- **The plan.** The edits, in order, using the tools below. Keep it short.

Show that summary (instructions with their interpretation, then the plan) in a few lines. If the
user is around and something important is ambiguous, ask once with the specific options.
Otherwise go, and say which reading you took.

## 4. Do it

Spoken commands like "Claude, zoom in here" are cut from the final video by default (the list is
`edit.remove` in `<name>.talk.json`). Keep them only if the user wants the raw feel.

| Instruction | How |
|---|---|
| Cut spoken commands / "cut that" / confirmed retakes | `python3 $S/vlog_cut.py cut <video> --remove-file <work>/talk/<name>.talk.json [--remove "a-b,..."] [--fillers] --out <work>/cut.mp4` (add confirmed `[confirm]` ranges with `--remove`) |
| "Clip that" callouts, laughs, hype moments → montage | `build_montage.py --highlights <work>/talk/<name>.highlights.json` (see `/montage`) |
| ... → separate short clips | re-run `listen.py hear ... --transcript <work>/talk/<name>.transcript.json --export-dir <work>/clips` |
| Zoom / slow-mo / freeze / speed-up at a moment | `clip_fx.py` ops on that clip (see `/describe-clip`); for a talking video, `--punch-in` on the cut |
| Music / "put the drop here" | `/montage` or `/long-video` (music bed); align the drop to the time they said |
| Text / caption | `export.py --text "TEXT@S-E@top"` or `/vlog-edit` captions |
| Thumbnail | `thumbnail.py make <video>@<time>` |
| Avatar / "put the robot here" | `/avatar` with `--start` at that time |
| Bleep / censor | ask what to bleep, then mute that word's range (`--remove` cuts it; a bleep tone needs `sfx.py`) |

Times in `talk.json` are in the original video. After `vlog_cut.py cut`, convert them with the
`cut.map.json` (`chapters.py` and `captions.py` do this themselves; for anything else, look up the
range in the map).

## 5. Report back

What you heard (instruction count and the notable moments), what you did, and anything you
skipped or interpreted, each in a line. Then deliver the files.

## Phrases the user can say while filming

Share this when they ask how to use /talk:
- "**Clip that**" / "clip it" / "that's a clip": right after a great moment (the 12 s before it
  become a highlight; change with `--pre`).
- "**Claude, zoom in here**", "Claude, slow mo that", "Claude, put the drop here", "Claude, add text
  NO WAY", "Claude, thumbnail", "Claude, start here" / "end here". "Editor, ..." works too.
- "**Cut that**" / "scratch that": drops the sentence before.
- "**Let me redo that**" / "one more time": marks a retake, and the flubbed take gets dropped.
- Pause half a second before and after a command so it cuts out cleanly.

## Honesty

Speech recognition mishears names, slang and mixed languages. Say so when an instruction depends
on a word it may have misheard. A sound being detected doesn't mean it was a good moment: check
the frames or the transcript around it before building the edit on it.
