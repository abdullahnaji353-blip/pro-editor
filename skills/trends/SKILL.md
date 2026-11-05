---
name: trends
description: >
  This skill should be used when the user asks "what's trending", "what edit style is popular
  right now", "what sounds are people using for edits", "give me a trending style", "what should
  my next edit look like", or wants an edit that follows the current TikTok/Shorts/Reels/YouTube
  trend for gaming (Fortnite, Rocket League, others), vlogs, travel or event videos. Researches current edit styles and
  sounds, then turns the chosen trend into a style recipe for the montage skill.
metadata:
  version: "0.7.0"
---

# Trends

Find what gaming edits look and sound like right now, and turn it into a recipe.

## Research (always live, never from memory)

Trends move weekly; anything remembered is stale. Get today's date first, then research.

1. If a YouTube/TikTok analytics connector is connected (for example vidIQ: trending videos,
   outlier search, keyword research), use it first for the user's game and platform: recent
   high-performing short edits, their titles, and view counts relative to channel size.
2. Run several separate web searches (one per angle, not one combined query), including the
   current month and year:
   - `<game or niche> edit trend tiktok <month year>` (niche: vlog, travel, day in my life, GRWM...)
   - `trending sounds for edits <month year>` / `<game> montage song <year>`
   - `<style word> edit tutorial <year>` for any style name that keeps appearing
     (velocity, "4K edit", "cc", "flow", "jumpcut", etc.)
3. Open the best 3-5 sources (creator tutorials, trend roundups, platform trend pages) and read
   them. Prefer sources from the last 1-2 months.

## Report: 3-5 trend cards

For each trend give:

- **What it looks like**: pacing, the signature effect, color, text style, aspect ratio.
- **Why it's working** (only if a source says so).
- **Sounds people pair with it**: song/sound names as found. Never state exact use counts or
  "#1" claims unless a source gives them, and tell the user to check the sound page in the app
  before committing, since sounds peak and die fast.
- **How hard it is** to pull off with this plugin: what it does automatically vs what still
  needs hand-keyframing in their editor.
- **Sources** with dates.

Then recommend one trend for the user's next edit and say why (fits their footage, doable with
the plugin, not already oversaturated if the sources suggest so).

Evergreen patterns (hooks, length, loops, text, in-app sounds, HUD framing) are in
`../montage/references/what-works.md`; combine them with what's current.

## Turn it into a recipe

When the user picks one, write `<work>/style/<trend-name>.json` following
`../style-match/references/recipe-format.md`. Map the trend to fields:

- pace → `cut_every_beats` (0.5-1 for hyper-fast trends, 2-4 for clean/cinematic)
- speed ramps → `"velocity": "strong_beats"` or `"all"`, with `velocity_fast`/`velocity_slow`
- glitchy/chromatic look → `rgb_split_on_beats`; flash cuts → `flash_on_strong_beats`
- color mood → `color` targets (e.g. saturation 0.35 for washed-out, 0.75 for punchy)
- short-form platforms → `"aspect": "9:16"`

Say it's built from descriptions, not measured. If the user can get 2-3 real example edits of
the trend, `/style-match` on them will be more accurate.

## Songs

Suggest songs by name only. The user supplies the audio file themselves. Never download audio
from TikTok, YouTube or other platforms, or point to ripping sites. Mention once that popular
songs can get muted or claimed on upload.
