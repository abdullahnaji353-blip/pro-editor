# What works in short-form gaming edits (research, Nov 2026)

(Researched for gaming content. Hooks, length, loops, muted-viewer text, safe zones and in-app
sounds apply to most short-form; the HUD advice is gaming-only.)

Patterns that showed up across several 2026 sources. Most sources are blogs from clipping-tool
companies, so treat exact percentages as claims; the patterns are the consistent part. Re-check
with `/trends` for what's current; this file is the evergreen layer.

## Hook (first 1-1.5 seconds)
- Open on the payoff: the kill, the goal, the fail. No intros, no logo, no "what's up guys".
- "Result first, then rewind": flash the payoff for ~0.5-1s, then show the buildup.
  → `--cold-open`
- A curiosity caption on the first frame ("is this even possible?", "wait for the end").
  → `--hook-text`
- If completion is low, the first 3 seconds are almost always the problem: re-cut the hook
  and first caption before changing anything else.

## Length and structure
- 15-30s is the sweet spot for gaming Shorts/TikTok; one peak moment per video. Under ~5s lacks
  context; one source reports completion dropping sharply past ~45s.
- Slow the payoff down so nobody misses it (slow-mo on the hit, freeze frame).
- Loops: an ending that flows back into the first frame earns rewatches. → `--loop`
- YouTube Shorts allow up to 3 minutes (since Oct 2024), but length isn't the goal.

## Text (lots of people watch muted)
- Captions in the top third, white with a black outline.
- State the setup if it isn't obvious from the picture ("1v4, no shield, last zone").
- Keep text out of the app UI. On a 1080x1920 frame, TikTok covers about the top 108px,
  bottom 320px, right 120px; Reels top 210 / bottom 310 / right 84; Shorts top 120 /
  bottom 300 / right 96 (conservative estimates; check with `layout.py safe`).

## Sound
- For TikTok/Reels, adding the trending sound inside the app is how you join the trend; trends
  turn over in 1-2 weeks. TikTok lets you trim where the sound starts and set "Original sound"
  vs "Added sound" volume separately. → `--sound-ready` exports the edit without the song plus
  a guide with the exact start point.
- Game sounds (eliminations, goal explosions) under the song add punch.

## Vertical framing
- Crop so the character/crosshair sits in the centre.
- If the kill feed, minimap or scoreboard matters, shrink it into an inset instead of cropping
  it away. → `--fit hud --hud ...` (measure regions with `layout.py grid` on the user's footage)

## What creators want from AI editing tools (and this plugin's stance)
- Highlights with context (setup → moment → reaction), not just "loud". → highlights `--context`
- AI makes the draft, the creator decides; nothing opaque. → plan.json, XML timeline, previews
- Music that ducks under the voice without flattening hype reactions. → long-video `duck`
- One edit, every platform. → `/export`

## Sources (accessed 2026-11-01)
- FluxNote, "YouTube Shorts Strategy for Gaming Creators in 2026"
- dor.gg, "Game Shorts / TikTok tips"
- vidIQ review, "Here's what small gaming channels are doing wrong"
- CapCut, "What gaming content creators need from AI video editing tools"
- Eklipse, "AI gaming video editor comparison" (Aug 2026)
- PostPlanify, "Social media safe zones 2026"
- BlitzCut, "YouTube Shorts length limits 2026"
- FireCut, "How to add music to TikTok videos"
- Overseeros, "Background music volume under voiceover"
- Ludo.guide, Rocket League UI guide
