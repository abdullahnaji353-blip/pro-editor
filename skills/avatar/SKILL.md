---
name: avatar
description: >
  This skill should be used when the user wants a character in their video: "put an avatar in my
  hand", "a tiny robot standing on my palm", "AI assistant hologram in my hand", "add a mascot",
  "make a little character wave at the camera", "an avatar of Claude", "a pet in my hand", "mini
  me in my hand", "make it talk/say something", or invokes /avatar. Tracks the hand with
  MediaPipe and composites an animated avatar (built-in robot, hologram, or their own
  PNG/GIF/green-screen character) that stays on the palm, reacts to pokes, appears on an open hand
  and vanishes on a fist, and can talk.
metadata:
  version: "0.8.0"
---

# Avatar

An animated character that lives in the user's footage: standing on their palm, floating above
it as a hologram, sitting on a fingertip, or parked anywhere in the frame.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call
it `$S`. Hand tracking needs `mediapipe` and `opencv-python-headless<5`. Check with
`python3 $S/check_setup.py` and ask before installing. The hand-tracking model (about 7.5 MB)
downloads once on first use.

## The character

The built-in avatar is an original little TV-head robot that blinks, glances around, waves hello,
talks, and reacts. Show it before rendering anything:

```
python3 $S/avatar.py look --out <work>/avatar_look.png [--style hologram] [--color #hex] [--accent #hex]
```

- `--style solid`: a toy-like robot standing in the scene (contact shadow, matched to the light).
- `--style hologram`: a glowing projection with scanlines, flicker and a projector ring. It's the
  "AI assistant in my hand" look, and the most forgiving: it doesn't need to match the scene's light.
  It's added light, though, so it fades against bright backgrounds (white wall, sky): there, suggest
  solid or a darker spot to film.
- `--accent` recolours eyes, lights and glow; `--color` the body.

If the user asks for a specific brand's mascot or logo, Anthropic's Claude logo included, say once
that it can't be recreated, and offer the built-in robot (recoloured if they like) or their own
character file. They can use any image or animation they have the rights to.

Their own character: `--avatar FILE`.
- PNG with a transparent background: static, gets the entrance, breathing and pokes.
- GIF / WebP / video with alpha (`.webm` VP9, `.mov` ProRes 4444): plays on a loop.
- Green or blue screen video: keyed automatically (`--key auto`), or force it with `--key green`/`blue`.

## 1. Check the footage

Phone clips: run `/checkup` first. HDR iPhone video looks washed out unless it's converted, and
`--fix` makes a copy to use instead.

```
python3 $S/avatar.py check <video> --out-dir <work>/avatar
```

It prints how much of the video has a visible hand, how big the hand is, and how often it's open
or a fist, and writes `<name>_hands.jpg`. **Look at that sheet.** The red skeleton is the hand the
avatar follows, and the green dot is where its feet go. If the wrong hand is picked, use
`--hand left-side` or `--hand right-side` (side of the screen). If almost no hand is found, tell
the user why (below), or use `--anchor fixed`.

## 2. Preview, then render

```
python3 $S/avatar.py render <video> --track <work>/avatar/<name>.track.json --preview --out <work>/avatar_preview.mp4 [options]
```

Read `<out>_check.jpg` (8 frames from the result) before sending the preview. Check that the
avatar stands on the palm (not floating beside it), is a sensible size, and isn't cut off. Then
render without `--preview`.

| Want | Option |
|---|---|
| Standing on the palm (palm facing up or toward the camera) | `--anchor palm` (default) |
| Floating above the hand (best for hologram) | `--anchor above` |
| Tiny, on the index fingertip | `--anchor finger` |
| No hand / on a desk / in a corner | `--anchor fixed --pos 0.7,0.85` (x,y as fractions) |
| Bigger / smaller | `--size 1.3` / `--size 0.7` (1.0 = about 1.35x the palm length) |
| Only appear from 2.5 s to 9 s | `--start 2.5 --end 9` |
| Appear when the hand opens, vanish on a fist | `--summon` (magic-trick style) |
| Pokes | On by default: the other hand's index fingertip touching it makes it squish, then heart eyes |
| Speech bubble | `--say "hey Naji!@1.2-3.0"` (text@start-end, several allowed) |
| It talks | `--voice line.wav [--voice-at 1.5]`: mouth moves with the audio, mixed into the video |
| No wave at the start | `--no-wave` |
| Looks too sharp / too soft | `--soften 1.2` / `--soften 0` |
| Less shadow / less colour matching | `--shadow 0.25` / `--match 0.15` |
| Debug the tracking | `--debug` draws the hand skeleton on the output |

The track is saved next to the output (`.track.json`). Pass it with `--track` on re-renders so
only the compositing runs again.

For the avatar's voice, the user records the line themselves or uses a text-to-speech tool they
have. If a speech connector is available in the session, offer it. Never make it sound like a real
person without that person's consent.

## Shooting tips (tell the user before they film)

- Palm open and steady-ish, whole hand in frame, even light (not backlit), 1080p or higher.
- Leave space above the hand: the avatar is about as tall as the palm is long.
- Pokes: come in slowly from the side with the index finger toward its head.
- Summon: start with a fist, open it fully, hold it open about half a second.
- Plain backgrounds make tracking more reliable; busy patterns and gloves make it worse.

## Honest limits

It's a 2D character composited onto the footage, not a 3D model:
- Fingers can't wrap around it (it's always in front of the hand).
- It doesn't change perspective if the hand turns far away from the camera. It tilts with the
  hand a little (`--tilt`).
- Very fast hand moves can lag a frame or two. Brief tracking drops are held for 0.4 s, longer ones
  fade it out.

The hologram style hides most of this, so recommend it when the shot is tricky.

## Photoreal "mini me" or 3D characters (AI video route)

The viral "tiny me in my palm" clips are made with AI video models (Seedance, Kling, Veo, Runway)
from a selfie, not by compositing. If the user wants that look and has one of those tools (or a
connected video-generation app, which costs credits, so ask first), write the prompt for them.
What makes these work:
- One prompt with an **anchor frame** (a palm-sized figure standing on an open palm, a soft contact
  shadow under its feet, macro lens, creamy bokeh, soft warm light) plus a **timed sequence**
  (idle, a light "boop" that lifts clear immediately, a reaction, a payoff like a hug or wave).
- Negatives: "cheek sticking to finger, skin stretching, melting, extra fingers".
- Make 3-5 takes and pick the best. Lead with the interaction in the first 2 seconds.
- Label it as AI-generated when posting, as TikTok, YouTube and Instagram require for realistic AI video.

Hybrid: have the AI tool make the character animation on a plain green background, then bring it
in with `--avatar that.mp4 --key green`. That gives their own footage plus real hand tracking, with
a character of their choice.

## Deliver

The video, `_check.jpg` if they want to see placement, and one line on what to try next (size,
hologram vs solid, a speech bubble). Offer `/export` for platform versions.
