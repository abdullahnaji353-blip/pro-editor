---
name: create
description: >
  This skill should be used when the user invokes /create, or asks to "make a video about X",
  "create an explainer", "make an informative video", "animated video from this article / topic /
  data", "faceless video", "make a video with AI", "motion graphics", "a video like the ones made
  with Claude", or wants a video made from scratch rather than edited from their footage. Researches
  the topic, writes the script, codes each scene as an animation, adds a voiceover, music and
  captions, checks the frames, and renders it.
metadata:
  version: "0.10.0"
---

# Create

Videos made from scratch with code: every frame is drawn from a timestamp, so text, numbers,
charts and diagrams stay sharp and exact (AI video generators still mangle text). Typical output:
a 20-90 s vertical explainer, a 1-3 min YouTube explainer, a data story, a trailer for an article.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call
it `$S`. Needs `playwright` with Chromium (`python -m pip install playwright && python -m playwright
install chromium`) and ffmpeg. Check with `python3 $S/check_setup.py`; ask before installing.

## 1. Pin down the brief (one short question if unclear)

Topic, who it's for, length, format (9:16 for TikTok/Reels/Shorts, 16:9 for YouTube), voice or
text-only, and any look they want. Default: 9:16, 30-45 s, voiceover, captions, dark clean style.

## 2. Research before writing (informative = accurate)

Search the web for the facts, numbers and dates. Every number on screen needs a source you found
this session; never invent statistics or quotes. Keep the sources for the end card or the post
description. If the user gave an article, data or a transcript, work from that.

## 3. Script and storyboard

Write `project.json` in a work folder (format: `python3 $S/create.py -h`). Rules that make these
videos work:

- **Hook in the first 2 seconds**: a surprising claim, a question, a number. No "In this video".
- **One idea per scene**, 3-8 s each, narration of 8-25 words. On screen: at most ~10 words, big.
  The screen shows the key word, number or diagram; the voice explains it.
- **Show, don't list**: count numbers up, grow bars, draw lines and arrows, move things.
- **Payoff at the end**, then a short end card (sources, or a call to action).

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
