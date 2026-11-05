---
name: create
description: >
  This skill should be used when the user invokes /create, or asks to "make a video about X",
  "make a hype intro", "kinetic typography", "lyric video", "promo / ad for my product", "channel
  intro or outro", "animated meme", "make an explainer", "faceless video", "make a video with AI",
  "motion graphics", "a video like the ones made with Claude", or wants any video made from scratch
  rather than edited from their footage. Plans it, codes each scene as an animation (synced to the
  music's beats when there's a song), adds voice, music and captions if wanted, checks the frames,
  and renders it.
metadata:
  version: "0.11.0"
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

- **Voice** uses the computer's own voices: `say` on a Mac (`--voice Samantha`, `Daniel`...; list
  them with `say -v ?`), Windows' built-in voices, espeak-ng or Piper on Linux. No voice available:
  `--engine none` times scenes for reading. A user with a better voice (ElevenLabs or another TTS
  connector, or their own recording) can drop files in and set `"audio"` per scene.
- **Look at the sheet before rendering**: text overflow, things overlapping, empty frames, a scene
  that ends before its last element appears. Fix the HTML and re-sheet; it takes seconds.
- `render --only <scene id>` redraws one scene and reuses the rest.
- Music: `"music": "song.mp3"` ducks under the voice automatically; loudness ends at -14 LUFS.
  `"captions": true` burns word-by-word captions from the narration.

## 6. Finish

Show the video, list the sources, and offer `/export` (platform sizes, title, hashtags) and
`/thumbnail`. Be clear about what it is: motion graphics, not filmed or AI-generated footage. For
realistic shots, the user would need an AI video tool (Veo, Kling, Seedance, Runway) and can drop
those clips into a scene as `<video>` files.
