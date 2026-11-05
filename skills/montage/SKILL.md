---
name: montage
description: >
  This skill should be used when the user wants to "make a montage", "edit my clips to this
  song", "cut this to the beat", "sync my clips to music", "make an edit", "add zooms/shakes/
  flashes/slow-mo", or asks for a Fortnite, Rocket League, gaming, travel recap, event or vlog
  music edit from their clips and a song. Cuts clips on the beat, applies effects and color from a style recipe, and renders an
  MP4 plus an XML timeline that opens in Premiere Pro or DaVinci Resolve.
metadata:
  version: "0.7.0"
---

# Montage

Clips + song (+ optional style recipe) → finished MP4 and an editable timeline.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing.

## First: auto or draft?

Unless the user already said, ask one quick question before anything else:
- **Full auto**: pick sensible defaults for everything, render a preview, then the final after
  one quick look. Fewest questions.
- **Draft**: aim for a strong 80% and hand over the MP4 + Premiere/Resolve timeline for them to
  polish. Explain the effect markers they'll find in the timeline.

## Short-form defaults (from research: `references/what-works.md`)

For TikTok/Shorts/Reels, unless the user wants otherwise:
- 15-30s, one peak moment, 9:16.
- Strong hook in the first ~1.5s: `--cold-open` (payoff → rewind → buildup) or at least
  `--hook-first`, plus `--hook-text "<curiosity line>"` (offer 2-3 options, 2-6 words).
- `--loop` so the end flows back into the start.
- Ask whether they'll add the song as an in-app sound (best for joining a trend): if yes,
  add `--sound-ready` and give them the generated sound guide.
- If the kill feed / minimap / scoreboard matters, `--fit hud` (see HUD insets below).
Don't stack every option on every edit; pick what serves this clip and say why.

## Gather inputs (ask only what's missing)

- **Clips**: files or a folder, a `highlights.json` from `/highlights` (`--mode scenic` for
  travel/events/vlog b-roll), or labeled clips from
  the clip library (`library.py search` then `cut` the best ones into a folder).
- **Song**: an audio or video file the user provides. Remind them once, briefly, that
  copyrighted songs can get muted or claimed on YouTube/TikTok/Instagram; that's their call.
- **Which part of the song** and **how long**: default the first 30-60s; better to start a few
  seconds before the drop. Find the drops first with
  `python3 $S/beats.py <song> --out <work>/song_beats.json` and suggest a start point.
- **Style**: a recipe from `/style-match` or `/trends`, a style name (write a recipe from
  `../style-match/references/recipe-format.md`), or nothing (defaults: 16:9 60fps, cut every
  2 beats, zoom punches, shake + smooth slow-mo on drops, game audio at 25% under the song,
  loudness normalized to -14 LUFS).
- **Where it's going**: TikTok/Shorts/Reels → `"aspect": "9:16"` in the recipe;
  YouTube → 16:9.

## Preview the plan before rendering

Rendering takes minutes, so check the structure first:

```
python3 $S/build_montage.py --song <song> --clips <files/folder> [--highlights <json>] \
    --recipe <recipe.json> --song-start <s> --length <s> --fit crop|blur \
    --out <work>/montage.mp4 --plan-out <work>/plan.json --xml-out <work>/montage.xml --plan-only
```

Read `plan.json` and summarize: number of cuts, tempo, where the drops land, which clip is
saved for the biggest drop, effect count. Fix obvious problems (one clip dominating → add
`--shuffle` or more clips; too few cuts → lower `cut_every_beats`). Skip the preview when the
user said to just go.

## Render: preview, then full quality

1. Re-run the command without `--plan-only`, adding `--preview` and `--out <work>/preview.mp4`.
   Half resolution, 30fps, fast settings, with the same cuts and effects. Send it and ask what
   to change.
2. Apply changes (recipe tweaks, different song section, `--seed`), preview again if the
   change was big.
3. When the user approves, run once more without `--preview` to `<work>/montage.mp4`.

Skip the preview only when the user explicitly asks for full quality straight away.

After each render, verify:

- `ffprobe` duration equals `--length` and audio is present.
- Extract a frame grid
  (`ffmpeg -i montage.mp4 -vf "fps=2,scale=200:-2,tile=6x3" -frames:v 1 grid.png`) and look at
  it if the session can view images: crop framing, text not cut off, grade not nuked
  (orange skin / clipped whites → rerun with `--no-grade` or tone the recipe's color down).

## Options worth knowing

- Effects that make edits stop looking mid (set in the recipe `effects`):
  - `"velocity": "strong_beats"` (or `"all"`): speed ramp fast into the hit, slow after,
    with motion blur on the fast part. The signature velocity-edit look. Tune
    `velocity_fast` (1.6-2.5) and `velocity_slow` (0.3-0.5).
  - `rgb_split_on_beats`: chromatic glitch on hits (`rgb_split_px` 8-20).
  - `flash_on_strong_beats`, `zoom_punch_on_beats` + `zoom_amount`, `shake_on_drops`.
  - Too many effects at once = noise. Pick 2-3 signature moves per edit and say so if the
    user's recipe turns everything on.
- `recipe.audio.game_audio_volume`: clip sound under the song (0 = song only, 0.2-0.35 lets
  eliminations and goal explosions punch through). Mic chatter comes along with it if the
  recording has voice mixed in; set 0 in that case.
- `recipe.audio.normalize_lufs`: -14 matches TikTok/YouTube playback; `null` disables.
- `--fade-in/--fade-out`: song fades (fade-out 0 = hard stop on the last beat).
- The ending snaps to the nearest downbeat/beat within ~0.6s of `--length` so the edit ends on
  a hit; `--exact-length` keeps the exact length.
- `--fit crop` fills vertical frames by cutting the sides (punchier, loses HUD/killfeed);
  `--fit blur` keeps the full frame over a blurred copy (safer for Rocket League, where
  the ball is often off-center).
- `--shuffle --seed N` reorders clips; change the seed for a different cut.
- `--hook-first` opens on the best-scoring clip (strongest hook for short-form).
- `--sfx` adds synthesized whooshes on effect cuts, an impact on each drop and a riser into the
  first drop (recipe `audio.sfx`: `whoosh_on` effects|all|none, `impact_on_drops`,
  `riser_before_drop`, `volume`). Off by default; offer it, don't force it.
- **3 versions to A/B test**: `python3 $S/variants.py` with the same inputs makes A (best clip
  first), B (reshuffled) and C (song starts right before the drop). Suggest it when the user's
  goal is growth or they can't decide.
- `--cold-open`: first shot = the best clip's payoff, second shot = a fast VHS-style rewind,
  third = the buildup from the top. Needs at least 5 cuts. Best with `--highlights` (peaks known).
- `--loop`: the last shot is the footage just before the first frame, and the song ends hard on
  the beat (no fade), so the replay feels continuous.
- `--hook-text "..."`: caption for the first 1.8s in the top third; other top text that would
  overlap moves to the centre.
- `--sound-ready`: also writes `<name>_sound-ready.mp4` (game sounds + SFX, no song, at a
  quieter "original sound" level) and `<name>_sound_guide.txt` (which song, where to trim it to,
  volume settings). Warn that a sped-up/remixed in-app version won't line up with the cuts.
- Clips shorter than a segment loop; frozen last frames pad if a source runs out.
- `--res 1080|1440|2160|source`: output size (the short side). Default 1080. For high-res
  footage going to YouTube, `source` (capped at 4K) or 1440. For TikTok/Reels keep 1080: they
  downscale anything bigger. Previews stay small whatever `--res` says. Expect roughly 2x the
  render time at 1440p and 4x at 4K.
- Final renders use the graphics card's encoder (NVIDIA/AMD/Intel/Apple) when one works and fall
  back to the CPU on their own. If a GPU render ever looks wrong, set the environment variable
  `PRO_EDITOR_GPU=0` to force the CPU.

## HUD insets (vertical edits)

1. Grab a frame from the user's footage with a 10% grid: `python3 $S/layout.py grid <video>@<s>`
   and read where the element sits (x, y, w, h as fractions). HUD layouts change with settings and
   seasons, so measure rather than guess. Rocket League presets: `rl-scoreboard` (top centre),
   `rl-boost` (bottom right); Fortnite: `fortnite-minimap` (top right). Check presets on a frame too.
2. `--fit hud --hud rl-scoreboard 0.02,0.55,0.30,0.18,0.55` (custom = x,y,w,h[,scale of output width]).
   Insets stack at the bottom, above the app's caption zone (`--hud-place top` to move them;
   top captions then drop below them). Or set `"layout": {"fit": "hud", "hud": [...]}` in the recipe.
3. Check with `python3 $S/layout.py safe <render>@<s> --platform tiktok`: nothing important in red.
- Highest-score highlights are saved for the drops.

## Deliver

1. The MP4.
2. `montage.xml`: the same cut as a timeline. Premiere: File → Import. Resolve: File →
   Import → Timeline. It contains every cut plus markers where zooms, flashes, shakes and
   slow-mo were baked into the MP4, so the user can redo them with real keyframes. Slow-mo
   and velocity-ramp sections sit at normal speed in the XML; the marker tells them where to
   apply the speed change.
3. One line on what to tweak next (pace, effect strength, song section).

Offer `/edit-review` on the result or on their own polished version if they want feedback.

CapCut can't import the timeline; for CapCut users, deliver the MP4 (or export clean clips via
`/highlights`) and let them finish there.

When working in a cloud session, send finished files to the user with the file-sending tool.
On their own computer, write outputs next to their footage and say where.
