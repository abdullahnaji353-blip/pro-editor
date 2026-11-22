---
name: story
description: This skill should be used when the user invokes /story, or asks for "a Roblox story video", "an In this town story", "a blocky avatar story", "the HUSS HUSS HUSS trend", "an animated story with characters", "a 3D short with talking characters", "a story part 2", or wants a short narrated or dialogue story told with blocky 3D characters in a little town. Writes the story (a rule, a disaster, a twist), casts characters with their own voices, stages each shot in 3D with lip-synced faces, adds captions, sound and music, and renders a vertical video.
metadata:
  version: "0.20.0"
---

# Story (blocky 3D character stories)

Short animated stories with blocky 3D characters, like the "In this town..." Roblox-style trend
(the HUSS HUSS HUSS / "everybody goes out partying except me" wave, Nov 2026). Built on `/create`:
read that skill too, the voice, sheet and render steps are the same.

## Locate the scripts

`$S` = `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Needs playwright
with Chromium and ffmpeg (`python3 $S/check_setup.py`). Kokoro gives free character voices.

## 1. The story

The format that works:
- **Open on the rule, first line, first second**: "In this town, ..." said by the main character
  in first person, calm and matter-of-fact.
- **A rule, a disaster, a twist.** One odd rule; someone lives with it or breaks it; the ending
  flips it (a callback to the opening line lands hardest).
- 30-60 s, 6-10 shots, one line per shot. Leave a 1-2 s beat before the punchline.
- Series: end on a hook and name it "part 1" if they want more.

Write an **original** story and original characters. Riffing on a trend's catchphrase is fine;
copying a creator's script, characters or audio isn't. Never put a real person or a specific
game's official avatar, logo or map in it.

## 2. Cast and voices

One character speaks per shot (`"voice"` on each scene picks theirs). Kokoro voices:
`am_liam` (young male), `am_adam`, `am_michael`, `af_heart`, `af_bella`, `bf_emma`... For
ElevenLabs voices, generate each line with the connector and set `"audio"` per scene.

Characters: `K3.avatar(S, {shirt, pants, skin, hair: "short" | "long" | "none", hairColor,
hat: "beanie" | "party" | "cap", hatColor, capColor, glasses, hoodie, text, subtext, textColor,
stars, pattern: "check", shoes, seed})`. Rounded heads, soft plastic edges and printed hoodies
read as the blocky-avatar style; faces have moods (`neutral`, `grin`, `wink`, `shocked`, `smug`,
`tired`) and open into a talking grin with the voice. Give each main character one bold colour
and one signature item (a beanie, glasses) so they read at a glance; vary skin tones. Invent
your own shirt prints: don't copy another creator's character or merch text.

## 3. Stage it

Write a `common.js` next to the scenes that builds the world and cast once (`setup()`), then one
scene per shot:

```js
W = K3.world({ time: 0 });          // street, party house (lights on the beat), houses, hoop, lamps, trees
W.kid.pose("dribble", t, { ball }); // idle walk dribble talk shrug dance tired point cheer shoot
W.kid.say(K.talk(t));               // mouth follows this scene's voice line
W.kid.mood("smug");                 // neutral | smug | tired (eyes and mouth)
W.setTime(k);                       // 0 night ... 1 morning: sky, sun, stars, street lights
K3.shot(W.S, t, d, { from: [x, y, z], to: [x, y, z], look: [x, y, z], fov: 38 });
W.draw(t);
```

`K3.arc(ball, from, to, k)` throws a ball; `K3.house`, `K3.hoop`, `K3.lamp`, `K3.roundTree`,
`K3.fence`, `K3.car`, `K3.bunting` (flags or `lights: true`), `K3.balloons`, `K3.ball` add props.
The town is lit bright and clean like the trend videos, even at night (a big moon, string lights). Characters face +z; a camera's fill light keeps faces readable at night.

Cut like the trend: 2-3 shots per line with `K3.cuts(W.S, t, d, [{at: 0, from, to, look, fov},
{at: 1.4, ..., punch: 0.08, shake: 0.25}])` (hard cuts inside one voice line; `punch` snaps in on
the cut, `shake` jolts it, both for hits like "HUSS!"). Blend poses instead of snapping:
`W.kid.pose("talk", t, {from: "walk", at: 1.9})`; turn heads toward whoever's talking with
`W.fr.look(x, z)`. Frame close-ups chest-up with the whole head in frame (camera ~3.4 units away,
fov ~34), never a face filling the screen.

Shot grammar: wide establishing shot first, then close-ups for lines (camera 2-4 units away,
at eye height ~2), over-the-shoulder for dialogue, a low angle for swagger, a wide again for
the twist. Keep the camera outside characters and walls: check the sheet, it shows it at once.

## 4. Sound, captions, render

Sound makes or breaks these. Synthesized effects and the generated beat are placeholders; for a
video they'll post, use real audio:
- **Sound effects**: `python3 $S/ai_audio.py pack <work>/sounds --for story` makes a realistic
  set with ElevenLabs (bounce, swish, whoosh, pop, footsteps, door, crowd, ding; needs
  `ELEVENLABS_API_KEY`, uses their credits), then `"sfx_sounds": "sounds"` in the project. Without
  a key: make them with the ElevenLabs connector and save them under those names. Any file named
  after a sound kind replaces the built-in one, peak still on the frame.
- **Music**: their own track (`"music": "song.mp3"`), or `ai_audio.py music "prompt"` for an
  ElevenLabs track. For TikTok, the trend's sound is usually added in the app: set
  `"no_music_copy": true` and hand them the `_no_music` version too.
- **Voices**: young character voices from ElevenLabs beat Kokoro by a mile for this format;
  generate each line with the connector or the API and set `"audio"` per scene.

What the trend videos look like (from real references): rounded blocky heads with big
expressive face decals, printed hoodies, beanies and party hats; bright clean lighting even at
night (string lights, a big moon); busy cozy sets (fences, bunting, a court with a scoreboard,
furnished rooms); one word of caption at a time; a calm first-person narrator; a cut every 1-2 s.

### Render

Project: `"look": "story"` (one word at a time, big white with a dark edge, like the trend), `"captions": true`, `"sfx": true`
(add `K.sfx("bounce", time, id)` and friends for actions), `"music": "party"` (a house-party beat
heard through the walls) or `"bed"`, or their own song.

```
python3 $S/create.py voice <work>/project.json
python3 $S/create.py sheet <work>/project.json      # look at every shot
python3 $S/create.py render <work>/project.json
```

3D renders slowly on a CPU (several seconds per frame at 1080x1920): render the sheet first, fix
cameras, then render once. Run `check_render.py` on the result.

## 5. Finish

Show the video, offer a part 2 with the same cast, and `/export` for the post.
