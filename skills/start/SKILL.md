---
name: start
description: >
  This skill should be used when the user says "start", "help me edit", "I want to edit a video",
  "edit this for me", "where do I begin", "what can you do", "which command do I use", invokes
  /start, or gives video footage without saying which tool they want. It is the front door of the
  pro-editor plugin: checks the setup and the footage, works out what kind of edit the user wants,
  and routes to the right skills in the right order.
metadata:
  version: "0.8.0"
---

# Start

The user shouldn't need to know the commands. Find out what they want, then run the right
skills in order. Keep the language plain; explain jargon only if they ask.

## 1. First time in a session

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_setup.py` (if the variable is empty: the
`scripts` folder two levels above this file). If something required is missing, show the install
commands it prints and ask before installing. Right after a fresh install, or if renders fail
for no obvious reason, offer `selftest.py` (see `/checkup`): it tests every tool and measures how
fast this computer renders 1080p and 4K, which is what to quote when they ask "how long will it
take?".

## 2. Look at the footage

Run `/checkup` on it (`checkup.py <files> --out-dir <work>/checkup`). If it reports variable frame
rate or HDR, offer `--fix` and edit the fixed copies. Mention anything that changes the plan
(mic on its own track, no audio, clipped audio).

## 3. Ask only what's unclear (one short round, max 3 questions)

- **What is it?** gaming / talking (vlog, commentary, podcast) / travel or event / a mix
- **Where is it going?** TikTok/Reels/Shorts (vertical, 15-30s) / YouTube video / both
- **Auto or draft?** finished file, or an 80% draft + timeline to polish in Premiere/Resolve

If they sent a voice note instead of typing, transcribe it first (`/talk`, prompt mode) and treat
it as their request.

Skip any question the request or footage already answers.

## 4. Route

| They want | Run, in order |
|---|---|
| Gaming short to a song | `/highlights` (action) → `/trends` or `/style-match` if they want a style → `/montage` (preview first) → `/export` |
| One specific moment | `/describe-clip` (find) → optionally edit it there or `/montage` |
| Talking video / vlog | `/vlog-edit` (voice → transcript → script → jump cuts → vertical → captions → chapters) → `/color` → `/export` |
| Travel / event recap | `/highlights --mode scenic` → `/color` (pick a look) → `/montage` → `/export` |
| Funny moments | `/talk` (hears laughs, shouting, cheering, "clip that") or `/highlights --mode reactions` → `/montage` or `/describe-clip` |
| They talk in the footage, gave instructions out loud, or sent a voice note | `/talk` first, then whatever it calls for |
| "Find me examples / references", "how do people make X" | `/reference` → the matching command |
| A character / avatar / hologram / mascot in the video | `/avatar` |
| Long YouTube video | `/highlights` per recording → `/long-video` → `/thumbnail` |
| "What's trending?" | `/trends` (or `/reference` for a specific idea) |
| Feedback on their own edit | `/edit-review` |
| Just resize/caption/post-ready | `/export` (+ `captions.py` for word-by-word captions) |
| Title, description, hashtags | `/export` (post copy section) |

Say the plan in one or two plain sentences before starting ("I'll find your best moments,
cut them to the beat of your song, and give you a quick preview first"), then go.

## 5. While working

- Previews before full renders, always, unless they ask otherwise.
- Show progress in plain words, not script names.
- When something is a guess (highlights, trends, face tracking, transcripts), say so and ask the
  user to check it. They know their footage.
- If they're learning to edit, offer `/edit-review` on their own versions; don't push it.
