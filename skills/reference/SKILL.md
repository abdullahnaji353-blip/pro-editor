---
name: reference
description: >
  This skill should be used when the user invokes /reference, or asks "find me references", "find
  examples of edits like this", "how do people make this effect", "show me videos that do X",
  "what does a good Fortnite or travel edit look like", "search TikTok/Instagram/YouTube for this style",
  "I want something like ___ but I don't have examples". Searches the web (TikTok, Instagram,
  YouTube, Reddit, tutorials, GitHub) for references that match the user's idea, works out how
  they're made and what they have in common, asks how the user wants theirs, and turns the pick
  into a plan or style recipe the other commands can run.
metadata:
  version: "0.8.0"
---

# Reference

The user describes an idea ("a smooth Rocket League edit with the car flying in slow-mo", "a
day-in-my-life vlog that feels cinematic", "an AI robot hologram in my hand"). Find real examples,
work out how they're made, and turn that into the user's own version.

## 1. Pin down the idea (one line)

Write what they're after in one sentence: the subject, the platform, the vibe, the length. Don't
interrogate them. If a single detail would change the whole search (gaming vs vlog, say), ask that
one question. Otherwise search right away and ask with the results.

## 2. Search wide, one angle per search

Get today's date first and put the month and year in queries about trends. Run several separate
searches at once (not one combined query), including:

- `<idea> tiktok` and `<idea> edit tiktok <month year>`: TikTok discover/tag pages list real
  examples and the words creators use for the style.
- `<idea> reels instagram` / `<idea> edit instagram`.
- `<idea> youtube shorts` and `<idea> tutorial <year>`: tutorials explain how the effect is built.
- `how to make <idea> capcut` / `after effects` / `davinci resolve`: the step-by-step "how".
- `<idea> reddit` (r/editors, r/VideoEditing, r/AfterEffects, r/NewTubers): honest discussion
  of what works and what looks cheap.
- For technical effects (tracking, AI characters, captions, auto-zoom): `<effect> github` to see
  how open-source tools build it, and what this plugin's scripts can already do.
- If an analytics connector is available (vidIQ, for example: outliers, trending), use it for
  examples with real view numbers.

Open the 4-8 most useful pages. TikTok and Instagram pages often can't be read directly; use
their search-result titles and descriptions for what exists, and tutorials, YouTube and Reddit for
how it's made. Prefer recent sources and say how old each one is.

## 3. Build the reference board

Save `<work>/reference/<idea-slug>.md` with 3-6 references. For each one:

- **Link** and creator or source (credit them), plus the date if known.
- **What it is** in one line.
- **What makes it work**: the 2-3 specific techniques (pace, the signature effect, sound
  design, text style, framing, colour), as concrete as possible ("cuts every half beat",
  "0.3x slow-mo on the touch, then a 2x ramp out", "white flash on the drop", "captions two
  words at a time, yellow active word").
- **How it's made**: tools and steps from the tutorials (CapCut / After Effects / AI tool / phone
  effect). Note whether a paid tool or an AI-generation credit system is involved.
- **With pro-editor**: what the plugin does automatically (with the command), what it can only
  approximate, and what would need hand keyframing in their editor.

Then a section **What they have in common**: the shared core, meaning the 3-5 techniques that
show up across most references. That's the recipe; one-off tricks are optional extras.

## 4. Ask how they want it

Offer 2-3 directions in a few lines each, and recommend one:
- **Closest to the references**: the shared core, done straight.
- **Mix**: the core plus the best trick from one specific reference.
- **Your twist**: the core adapted to their footage, or something the references don't do.

If the user isn't around to answer, pick the recommended one and say so.

## 5. Turn the pick into something runnable

- Music edits → a recipe JSON (`../style-match/references/recipe-format.md`) saved as
  `<work>/style/<name>.json`, then `/montage`.
- Talking videos → `/vlog-edit` settings (pace, punch-ins, caption style).
- Characters, holograms, "thing in my hand" → `/avatar` options.
- Colour → a `/color` look and strength.
- Long videos → a `/long-video` section plan.

Say plainly which parts are built from descriptions rather than measured. If the user saves 1-3 of
the reference videos themselves, `/style-match` on them measures the exact pace and colour.

## Rules

- Links only. Never download videos from TikTok, Instagram or YouTube with rippers or downloader
  sites, and never put another creator's footage into the user's edit. The user can save
  references themselves for analysis.
- Emulating a style is fine. Copying someone's exact assets (their logo, character, overlays,
  footage) isn't: suggest an original take instead.
- Songs: suggest by name; the user supplies the audio. Popular songs can get muted or claimed.
- Never invent view counts, dates or quotes. If a source doesn't say it, don't claim it.
