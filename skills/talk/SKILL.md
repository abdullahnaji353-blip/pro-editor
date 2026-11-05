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
  version: "0.15.0"
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


## Sound effects that land

When the user wants SFX ("add sound effects", "make it pop"), or the style calls for them:

1. **Find the moments**: `python3 $S/sfx.py spot <video> --out <work>/sfx_events.json` lists hard
   cuts (whoosh) and things popping in, like cards, images and text (pop), thinned to about one a
   second. Read the list and drop anything that isn't a real moment.
2. **Pick the sounds**, best first: the user's own (a folder of `pop*.wav`, `whoosh*.mp3`...,
   passed as `--sounds`); free library sounds (`sfx.py search "pop" --dir <work>/sounds` pulls
   CC0 / CC BY sounds from Openverse and writes the credits; needs internet), ranked for the job
   with `sfx.py pick <work>/sounds --for pop` (length, attack, brightness, noise vs tone, measured);
   or the built-in synthesized ones (whoosh, swish, pop, click, tick, ding, impact, riser).
3. **Add them**: `sfx.py add <video> --events <work>/sfx_events.json [--sounds DIR] --out <out>`.
   Each sound's loudest point lands on its frame. Then run the render check.

Fewer is better: every effect sits on something you can see, and about 8 in 20 seconds reads as
designed where 20 reads as cheap. Effects sit under the voice, never over it.

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
