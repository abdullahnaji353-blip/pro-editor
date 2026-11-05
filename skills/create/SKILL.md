---
name: create
description: >
  This skill should be used when the user invokes /create, or asks to "make a video about X",
  "make a hype intro", "kinetic typography", "lyric video", "promo / ad for my product", "channel
  intro or outro", "animated meme", "make an explainer", "faceless video", "make a video with AI",
  "motion graphics", "a video like the ones made with Claude", "AI voiceover", "add an AI presenter",
  "use AI clips", or wants any video made from scratch
  rather than edited from their footage. Plans it, codes each scene as an animation (synced to the
  music's beats when there's a song), adds voice, music and captions if wanted, checks the frames,
  and renders it.
metadata:
  version: "0.14.0"
---

# Create

Any video made from scratch with code: every frame is drawn from a timestamp, so text, numbers,
shapes and timing are exact (AI video generators still mangle text). Anything goes:

| Kind | What makes it work |
|---|---|
| Hype intro, kinetic typography | one or two words per beat, hard cuts on bars, pulses and flashes on the beat, big type |
| Lyric video | each line on screen as it's sung (time lines to the song), the key word coloured |
| Promo / ad | the problem in one line, the product doing its thing, one benefit per scene, a clear ending |
| Channel intro / outro | 3-6 s, logo or name reveal on the drop, subscribe / next-video slot |
| Meme, joke, reaction | setup, beat of silence, punchline big; timing is everything |
| Story | a character or object that changes across scenes, narration carrying it |
| Explainer, facts, data | hook in 2 s, one idea per scene, numbers counting up, sources at the end |

Not sure which kind they want? Ask once, with two or three of these as options.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call
it `$S`. Needs `playwright` with Chromium (`python -m pip install playwright && python -m playwright
install chromium`) and ffmpeg. Check with `python3 $S/check_setup.py`; ask before installing.

## 1. Pin down the brief (one short question if unclear)

Topic, who it's for, length, format (9:16 for TikTok/Reels/Shorts, 16:9 for YouTube), voice or
text-only, and any look they want. Default: 9:16, 30-45 s, voiceover, captions, dark clean style.

## 2. Research only when it's needed

Facts, numbers, dates, or a real product or person on screen: search the web first. Every number
needs a source you found this session; never invent statistics or quotes. For a hype edit, a meme
or a story there's nothing to research: go straight to the plan. Looking up the current trend for
that kind of video (`/trends`, `/reference`) is worth it when the user wants it to feel current.

## 3. Plan the scenes

Write `project.json` in a work folder (format: `python3 $S/create.py -h`). For every kind:

- **Hook in the first 1-2 seconds**: motion, a bold word, a question. Never a slow fade from black.
- **One thing per scene**, big and readable on a phone: at most ~10 words on screen at once.
- **Move with purpose**: things arrive, hit, count, grow, draw, then leave. Nothing just sits.
- **End on purpose**: a payoff, a punchline, a logo hit or a call to action.
- Narration is optional: a hype intro or a lyric video usually has none (`"narration"` omitted).

With a song, add `"music": "song.mp3"` and `"sync": "bars"` (or `"beats"` for faster cutting):
scene ends snap to the music, and every scene gets its own beat times. Animate on them with
`K.beat(t)` (1 on each beat, fading), `K.bar(t)` (each bar), `K.drop(t)` (the drop) and
`K.count_beats(t)` (how many beats so far: one word per beat).

## 4. Code the scenes

One HTML file per scene. It defines `window.render = (t, d) => {...}` and sets everything from `t`
(seconds into the scene, `d` = its length). The kit (`$S/create_kit/kit.css`, `kit.js`) is loaded
into every scene automatically:

- classes: `.stage` (full frame with safe margins), `.kicker`, `.title`, `.subtitle`, `.big`,
  `.body`, `.card`, `.row`, `.col`, `.bar`, `.source`, `.accent`, `.hl`, `.muted`
- `K.reveal(sel, t, start, dur, dy, d)`, `K.pop`, `K.type(sel, text, t, start, cps)`,
  `K.count(sel, to, t, start, dur)`, `K.grow(sel, frac, t, start)`, `K.draw(svgPath, t, start)`,
  `K.zoom(sel, t, d)`, `K.p(t, start, dur)` for anything custom
- colours are CSS variables (`--bg`, `--text`, `--accent`...): restyle a whole video by overriding
  them in each scene's `<style>`.
- **Presenter**: `K.host(t, d, {style: "orb" | "bot", pos: "br" | "bl" | "center"})` draws an
  animated host whose mouth follows the real voiceover (`K.talk(t)` is the voice's loudness, 0-1).
  `orb` is a hologram face, `bot` is pro-editor's robot. Use it for faceless videos when the user
  wants a narrator on screen. Never draw someone else's mascot or character (Claude's, a game's, a
  brand's); offer one of these or the user's own PNG instead.
- **Footage**: `<video src="clip.mp4"></video>` plus `K.clip(sel, t, start)` plays a clip in step
  with the frame (AI clips, screen recordings, the user's b-roll), under text and graphics.

Never use CSS animations, timers or `requestAnimationFrame`: the renderer calls `render()` once per
frame. Only touch `K` inside `render`. Vertical video: keep text out of the bottom ~18% (the app's
buttons and captions live there); the kit's `.stage` already does.

## 5. Voice, check, render

```
python3 $S/create.py voice  <work>/project.json        # voiceover + scene timing
python3 $S/create.py sheet  <work>/project.json        # 3 stills per scene -> look at it
python3 $S/create.py render <work>/project.json --preview
python3 $S/create.py render <work>/project.json        # full quality
```

- **Voice**, best first:
  1. **AI voice** with a voice connector (ElevenLabs) when one is connected: list its voices, pick
     one that fits (say which), generate the **whole script as one take** (more natural than line by
     line, and one credit charge), download it to the work folder and set `"voiceover": "vo.mp3"`.
     `voice` then cuts it at the pauses between scenes and times every scene to its line; listen
     to `vo/` if a cut sounds off. It spends the user's credits: never retry a generation on your
     own, and if the service is busy, say so and carry on with the visuals.
  2. `--engine elevenlabs` when the user has `ELEVENLABS_API_KEY` set (`--voice <voice id>`).
  3. **Kokoro**, free and natural-sounding, runs on their computer (`pip install kokoro-onnx
     soundfile`; the 120 MB model downloads once from GitHub). `--engine kokoro --voice am_michael`
     (US male), `af_heart` (US female), `bm_george` / `bf_emma` (British). It's the default when
     installed, and the fallback when a paid voice is busy or out of credits.
  4. The computer's own voices: `say` on a Mac (`--voice Samantha`, `Daniel`; `say -v ?` lists
     them), Windows' voices, espeak-ng or Piper on Linux.
  5. Their own recording: `"voiceover"` for one file, or `"audio"` per scene.
  No voice at all: `--engine none` times scenes for reading.
- **Look at the sheet before rendering**: text overflow, things overlapping, empty frames, a scene
  that ends before its last element appears. Fix the HTML and re-sheet; it takes seconds.
- `render --only <scene id>` redraws one scene and reuses the rest.
- Music: `"music": "song.mp3"` ducks under the voice automatically; loudness ends at -14 LUFS.
  `"captions": true` burns word-by-word captions from the narration.

## 6. Finish

Show the video, list the sources, and offer `/export` (platform sizes, title, hashtags) and
`/thumbnail`. Be clear about what it is: motion graphics, with an AI voice or AI clips if used.

**AI footage**: when the user wants realistic shots and has an AI video tool connected (Higgsfield,
Veo, Kling, Seedance, Runway), check the cost first and tell them before spending their credits,
generate short clips for the scenes that need them (scenery, objects, an establishing shot) and
lay them in with `K.clip`, with the text and the host on top. Ask which tool if they named none,
and use none they ruled out. Never generate realistic footage of a real person: for a video about
someone, use places, objects, graphics and their own words, not a synthetic face.

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
