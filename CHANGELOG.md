# Changelog

## 0.12.0

- AI voiceover for `/create`: generate the whole script as one take with the ElevenLabs connector
  (or `--engine elevenlabs` with an API key) and set `"voiceover"`; `create.py voice` cuts it into
  scene lines at the pauses and times every scene to its line.
- `K.host`: an animated presenter (hologram face or pro-editor's robot) whose mouth follows the real
  voice. `K.talk(t)` gives the voice's loudness for your own animations.
- `K.clip`: AI clips, screen recordings or b-roll inside a scene, seeked to the exact frame so they
  stay in step with the text and graphics.

## 0.11.1

- Fixes installing in the Claude app: the plugin description is under 500 characters and no skill
  description contains tag-like text. Tests now check both on every push.

## 0.11.0

- `/create` makes any kind of video, not just explainers: hype intros, kinetic typography, promos,
  lyric videos, channel intros, memes and stories, each with its own plan in the skill. Research
  happens only when facts are on screen.
- Music sync for `/create`: `"sync": "bars"` or `"beats"` snaps scene cuts to the song, and every
  scene gets its beat times (`K.beat`, `K.bar`, `K.drop`, `K.count_beats` in the kit).

## 0.10.0

**New**
- `/create`: informative videos from scratch. Claude researches the topic, scripts it scene by
  scene and codes each scene as an animation (`create_kit`: reveals, typewriter text, counting
  numbers, growing bars, line drawing). `create.py` records every frame in a headless browser,
  voices the narration with the computer's own voices (`say`, Windows voices, espeak-ng, Piper),
  ducks music under it, burns word-by-word captions and normalises loudness. A still-frame sheet
  comes first so problems are fixed before the slow render.

## 0.9.0

**New**
- `/shorts`: one long video (stream, podcast, commentary) into ranked vertical clips. Finds
  stretches of whole sentences, scores hook, energy, ending and pace with the reasons written out,
  has Claude read and re-rank them, then renders the picks reframed to 9:16 on the speaker's face
  with word-by-word captions.
- Montage transitions: whip (the shot slams in sideways with motion blur) and spin, on strong beats,
  never two cuts in a row. Recipe `effects.transitions`: off, whip, spin or mix.

**Fixed**
- Captions crashed on short clips where only a few caption groups had a word worth colouring.

## 0.8.2

- Montages land the action on the beat: drop shots and strong-beat shots now start just before each
  clip's best moment, instead of wherever that clip left off.
- Montage pacing follows the song: cuts slow down where it's quiet and hit every beat for two bars
  after a drop (recipe `pacing.follow_energy`, on by default).

## 0.8.1

- New icon and a redesigned README: a banner, a "how it works" diagram, and images for `/talk` and
  `/avatar`. Designed in Figma.
- CI uses the Node 24 releases of the checkout and setup-python actions.

## 0.8.0

**New**
- `/talk`: Claude hears everything in a video. Word-by-word transcript, plus sounds (laughter,
  shouting, cheering, music, gunfire, explosions, engines, crying) through Google's YAMNet, and the
  loudest moments. It follows instructions spoken while filming: "clip that" callouts become
  highlights, "Claude/Editor, zoom in here / slow mo that / put the drop here", "cut that",
  "let me redo that". Spoken commands are cut from the final video. Voice notes work as prompts.
- `/avatar`: an animated character in your hand, tracked with MediaPipe. Original robot in solid or
  hologram style, or your own PNG/GIF/alpha/green-screen character. It stands on the palm, floats
  above it or sits on a fingertip, waves hello, blinks, reacts to pokes, appears on an open hand
  and vanishes on a fist, and has speech bubbles and lip-flap to a voice line. Contact shadow, scene
  colour/grain/softness matching, motion blur, One Euro smoothing.
- `/reference`: web research for references (TikTok, Instagram, YouTube, Reddit, tutorials, GitHub),
  how each is made, what they share, then the plan.
- Captions colour the key word of some groups automatically (numbers, scores, words said louder,
  caps), or the keywords you name.
- Punch-ins can land on the punchline (`--punch-mode emphasis`) instead of every other cut.
- Transcription: model picked for your hardware (large-v3-turbo on NVIDIA GPUs), hotwords for
  names and slang, mixed-language speech, and Whisper hallucination guards (voice filtering, no
  repetition loops, skipping text invented in long silences).
- `vlog_cut.py cut --remove / --remove-file` cuts exact ranges.

**Fixed**
- Phone videos stored sideways with a rotation flag (common on iPhones) reported the wrong
  width/height, which could squash vertical crops, colour sampling and cuts.

## 0.7.0

**New**
- High resolution: `--res 1080 | 1440 | 2160 | source` for montages, long videos, vertical crops and
  YouTube/Shorts exports. Previews stay small.
- Graphics-card encoding (NVIDIA, AMD, Intel, Apple) with automatic CPU fallback. `PRO_EDITOR_GPU=0` turns it off.
- Punch-in zooms on jump cuts (`vlog_cut.py cut --punch-in 1.12`).
- YouTube chapters from the transcript (`chapters.py`), following the cut.
- Color grades saved as `.cube` LUTs for Premiere, Resolve, CapCut and Final Cut; `--lut-only` for long 4K videos.
  The grade itself renders faster.
- `selftest.py`: tests every tool on your computer and measures render speed.
- Post copy: titles, descriptions with chapters, captions and hashtags.
- `check_setup.py` shows which graphics-card encoder is available.

**Fixed**
- Clips shorter than 10 seconds crashed highlight detection.
- Apostrophes in file or folder names broke joining, captions and subtitles.
- Vertical crop crashed on footage that was already vertical.
- Clip edits couldn't find a song given without its full path.
- Long videos crashed when the transition was written as plain text (`"fade"`).

## 0.6.0

- Renamed from montage-lab to pro-editor; added vlogs, travel and events.
- Voice cleanup, transcripts, edit by text, retake spotting, jump cuts, word-by-word captions,
  face-tracking vertical crops, color looks, thumbnails, footage checkup, scenic and reaction highlights.

## 0.5.0 and earlier

- Gaming montages: beat sync, velocity ramps, zoom/shake/flash/RGB effects, cold open, loop ending,
  HUD insets, SFX, sound-ready exports, A/B variants, style matching, trend research, clip library,
  describe-a-clip editing, edit review, long videos with chapters, Premiere/Resolve timelines.
