# pro-editor manual

Everything pro-editor can do, how to ask for it, what you get back, and what to do when something
goes wrong. If you only read one thing, read **[Part 2: How a session works](#part-2-how-a-session-works)**.

**Contents**

1. [Setup](#part-1-setup)
2. [How a session works](#part-2-how-a-session-works)
3. [Workflows, step by step](#part-3-workflows-step-by-step)
4. [Every command](#part-4-every-command)
5. [The files you get](#part-5-the-files-you-get)
6. [Finishing in Premiere, Resolve, CapCut or Final Cut](#part-6-finishing-in-your-own-editor)
7. [High resolution, speed and disk space](#part-7-high-resolution-speed-and-disk-space)
8. [Style recipes](#part-8-style-recipes)
9. [Running the scripts yourself](#part-9-running-the-scripts-yourself)
10. [Troubleshooting](#part-10-troubleshooting)
11. [FAQ](#part-11-faq)
12. [Words you'll see](#part-12-words-youll-see)

---

## Part 1: Setup

### What you need

| Thing | Why | Required? |
|---|---|---|
| A paid Claude plan (Claude app) or Claude Code | Plugins run there | Yes |
| ffmpeg | Does all the actual video work | Yes |
| Python 3.9+ with `numpy`, `librosa`, `soundfile` | Beat detection, analysis, planning | Yes |
| `faster-whisper` | Transcripts: jump cuts on "um", edit by text, captions, chapters | Only for talking videos |
| `opencv-python-headless<5` | Face tracking for vertical crops, and the avatar | Only for vertical vlogs / `/avatar` |
| `mediapipe` | Hand tracking for `/avatar`; sound recognition (laughs, cheers, gunfire...) for `/talk` | Only for those two |
| A graphics card (NVIDIA, AMD, Intel or Apple) | Faster final renders | No, the CPU works too |

### Install the plugin

**Claude app** (desktop or web): Customize → Plugins → Add → Add marketplace → Add from a
repository → `abdullahnaji353-blip/pro-editor` → then add **pro-editor** from the Discover tab.

**Claude Code:**
```
/plugin marketplace add abdullahnaji353-blip/pro-editor
/plugin install pro-editor@pro-editor
```

### Install the tools

Easiest: say **"/start"** or **"check my pro-editor setup"**. Claude runs `check_setup.py`, lists what's
missing with the exact commands for your system, and asks before installing anything.

By hand:

```
# Windows (PowerShell). Reopen the terminal after installing ffmpeg.
winget install --id Gyan.FFmpeg -e
python -m pip install numpy librosa soundfile

# macOS
brew install ffmpeg
python3 -m pip install numpy librosa soundfile

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg
python3 -m pip install numpy librosa soundfile

# Optional
python -m pip install faster-whisper                  # transcripts and captions
python -m pip install "opencv-python-headless<5"      # face tracking, avatar
python -m pip install mediapipe                       # avatar hand tracking, /talk sounds
```

The first transcript downloads a speech model (a few hundred MB for "small", the CPU default, and
about 1.6 GB for "large-v3-turbo", used automatically on an NVIDIA graphics card). The avatar's
hand-tracking model (about 7.5 MB) and /talk's sound model (about 4 MB) also download once. After
that everything works offline.

### Prove it works: the self-test

```
python scripts/selftest.py            # about 3-6 minutes
python scripts/selftest.py --models   # also tests transcripts and face tracking
python scripts/selftest.py --keep     # keeps the test videos so you can look at them
```

It makes small test videos and songs, runs every tool on them, and prints:

```
  PASS  checkup (footage problems)                   0.8s
  PASS  beat detection                               4.4s
  PASS  highlights                                  19.1s
  ...
Render speed on this computer:
  1080p60: about 1.2 min of rendering per minute of finished video
  4K60: about 4.8 min of rendering per minute of finished video
GPU encoding: h264_nvenc (final renders use your graphics card)
17/17 passed in 140s.
```

(Your numbers will differ.) Every FAIL line comes with what to do about it. Run it after
installing, after updating ffmpeg or Python, or when something breaks and you can't tell whether
it's your footage or your setup.

---

## Part 2: How a session works

### You describe, Claude edits

You don't need to know any commands. Say what you're making and where it's going:

> "20-second TikTok from these Rocket League clips, cut to this song, hype style, keep the scoreboard visible."

Claude works out which tools to run and in what order. If something important is unclear, it asks
up to three short questions (what is it, where is it going, auto or draft). Everything else gets a
sensible default.

### Auto or draft?

For montages, Claude asks once (unless you already said):

- **Auto**: Claude makes every decision, shows you a preview, then renders the final.
- **Draft**: Claude makes a strong 80% version and hands you the MP4 plus a **timeline file** you
  open in Premiere Pro or DaVinci Resolve to finish yourself. The timeline has every cut, plus
  markers wherever an effect was added, so you can redo it with your own keyframes.

### Preview first, always

Rendering takes time, so every edit goes:

1. **Plan**: Claude checks the structure (number of cuts, where the drops land, which clip is saved
   for the biggest moment) before rendering anything.
2. **Preview**: small, fast, same cuts and effects. You say what to change.
3. **Final**: full quality, rendered once.

Want to skip the preview? Say "just render it full quality".

### Your files are safe

- Your original footage is **never changed**. Fixes and edits are always written as new files.
- Results go into a work folder next to your footage (Claude tells you where).
- Nothing is deleted without asking.

### Tell Claude when it's wrong

Highlight picks, face tracking and transcripts are educated guesses. Claude says when something is
a guess and asks you to check it. You know your footage: "not that one, the goal at 3:20" is all it needs.

---

## Part 3: Workflows, step by step

### Gaming short (TikTok / Shorts / Reels)

1. **Check the footage** (`/checkup`): catches phone or screen-recorder problems before you waste time.
2. **Find the moments** (`/highlights`): scores your recordings by action and sound and cuts out
   the best moments, with a few seconds of setup before each.
3. **Pick a style** (optional): `/trends` for what's working now, or `/style-match` with 1-3 edits you like.
4. **Make the montage** (`/montage`): beat-synced cuts and effects, preview first.
5. **Export** (`/export`): 1080x1920 with loudness set right, plus a title, caption and hashtags if you want them.

Defaults for short-form: 15-30 seconds, one peak moment, a hook in the first 1.5 seconds (cold
open or best clip first), and an ending that loops back into the start.

> "Find my best kills from last night's recordings and make a 25-second TikTok to drop.mp3. Cold open, loop it."

### Talking video / vlog / commentary

1. **Check the footage** (`/checkup --fix`): phone videos are often variable frame rate (audio
   drifts out of sync after cuts) or HDR (colors go grey). Claude edits a fixed copy.
2. **Clean the voice** (`/vlog-edit`): removes background hiss and hum, tames harsh "s" sounds,
   evens out the volume.
3. **Transcript**: every word with its exact time.
4. **Edit by text**: Claude shows you the transcript as numbered lines, flags retakes ("RETAKE?"
   where you said the same thing twice), and suggests what to cut (rambling, slow intro). You
   decide; deleting a line deletes that part of the video.
5. **Jump cuts**: removes the silences and "um/uh". `--punch-in` zooms every other piece slightly so
   cuts look like a second camera.
6. **Vertical** (for Shorts/TikTok/Reels): a 9:16 crop that follows your face like a camera operator.
7. **Color** (`/color`): fixes exposure and color casts; `clean` or `warm` suit faces.
8. **Captions**: word-by-word, the current word highlighted, kept inside the safe zone.
9. **Chapters** (YouTube): from topic changes in the transcript, following your cuts.
10. **Export** (`/export`) and a **thumbnail** (`/thumbnail`).

Skip any step you don't need. A horizontal YouTube vlog skips step 6.

> "Here's my 20-minute vlog. Clean the audio, cut the silences and ums, show me the script so I can cut the boring parts, then make a YouTube version with chapters and a 45-second Short with captions."

### Travel or event recap

1. `/highlights --mode scenic`: finds the best-looking shots (sharp, colorful, well exposed, steady),
   one per scene.
2. `/color`: pick a look by eye from a grid of the same frame in every look.
3. `/montage`: cut to your song.
4. `/export`.

> "Make a 40-second recap of my Japan trip from this folder, warm look, to this song."

### Long YouTube video (5-45+ minutes)

Built from **sections**:

- **Montage sections**: beat-synced edits (cold open, mid-video hype parts, outro).
- **Raw sections**: your gameplay or talking with its own sound, trimmed of dead time, with an
  optional quiet music bed that ducks automatically when you talk.

A good shape for gaming: cold open montage (10-25 s) → main content → a short montage every 5-10
minutes → outro. Section titles become YouTube chapters. Claude previews it all first; changing one
section only re-renders that section.

> "Make a 15-minute YouTube video from these three recordings. Start with a 20-second hype montage, then the best parts of each game, with lofi music under my commentary."

### One moment, edited a specific way

`/describe-clip` finds a moment from a description and edits it the way you say:

> "Find the part where I hit the triple and the guy rage quits. Slow-mo the last shot, freeze on the elimination, then speed back up. Add '1v3' at the top."

For big recordings Claude builds a **clip library** first: it samples frames into timestamped
sheets, looks through them, and labels the moments. After that, any moment is one search away.

### Talk while you film, then /talk

Say instructions out loud while recording ("clip that" after a great play, "Claude, zoom in here",
"cut that", "let me redo that"), then:

> "/talk" + the recording (and, if you want, a typed or voice-note prompt like "make it a 30-second TikTok").

Claude listens to everything: the words, plus laughs, shouting, cheering, music, gunfire and engines.
It finds your spoken instructions and works out what each one applies to. It combines them with your
prompt, tells you its plan in a few lines, then edits. Your spoken commands are cut out of the final
video. "Clip that" moments and big laughs become highlights for a montage.

### An avatar in your hand

1. Film your open palm (good light, whole hand in frame, space above it). Want it to pop out of a
   fist? Start with a fist and open your hand.
2. "/avatar put a robot hologram in my hand that waves" + the clip.
3. Claude shows you the avatar's looks, checks the hand tracking on a sheet of frames, renders a
   preview, checks the placement, then renders full quality.

Poke it with your other hand's index finger and it squishes, then gets heart eyes. Speech bubbles
("Hi!" from 1.2 s to 3 s) and a voice line (its mouth moves with the audio) are optional.

### Finding references first

> "/reference smooth Rocket League freestyle edit with slow-mo on the touches"

You get 3-6 real examples with links, what makes each one work, how it's made, and what they have
in common. Then you pick: closest to the references, a mix, or your own twist. Claude turns that
into a style recipe or plan and makes it.

### Getting better at editing

Edit something yourself, then `/edit-review`:

> "Review my edit. The song is song.mp3, it starts at 0:30."

You get coach-style notes: cuts that miss the beat (with the exact timestamp and how many frames to
move them), dead spots, how strong the hook is, how the ending lands, loudness, and how it compares
to a target style.

---

## Part 4: Every command

Commands are shortcuts. Plain sentences work just as well. In Claude Code they may appear as
`/pro-editor:<name>`.

### /start: the front door

Use it when you don't know where to begin. Checks your setup, checks the footage, asks up to three
questions, then runs the right commands in order and tells you the plan in a sentence first.

### /talk: Claude listens

Hears everything in a video or voice note:
- **Words**: a word-by-word transcript. Names, slang and game terms come out better when Claude
  passes them as hotwords; it does this from your prompt, and you can list them yourself
  ("my friends are Zayd and Omar").
  Speakers who switch languages (Arabic and English, say) are supported.
- **Sounds**: laughter, shouting/screaming, cheering/applause, music, gunfire, explosions, engines,
  crying, gasps (Google's YAMNet sound classifier, run on your computer).
- **Energy**: the loudest moments.
- **Your instructions**:

| You say | Becomes |
|---|---|
| "clip that", "clip it", "that's a clip" | A highlight of the 12 s before (`--pre` changes it) |
| "Claude, ..." or "Editor, ..." + zoom / slow mo / speed up / freeze / cut / keep / music / sound effect / text / thumbnail / start here / end here / avatar | That edit, at that point ("here/this" = after it, "that/it" = before it) |
| "cut that", "scratch that" | Remove the sentence before |
| "let me redo that", "one more time", "take two" | Retake: drop the flubbed take |

It ignores normal speech that only sounds similar ("I clipped that guy", "the cloud today", "the
editor at my school"). Anything unclear is marked `[confirm]`, and Claude checks it against the
transcript or asks you. Spoken commands are removed from the final video unless you want them kept.

Voice notes: send a voice message instead of typing, and Claude transcribes it and treats it as
your request.

### /avatar: a character in your video

An animated avatar that follows your hand: standing on your palm, floating above it, sitting on a
fingertip, or parked anywhere in the frame.

| Option | What it does |
|---|---|
| Style | `solid` (a toy-like robot with a contact shadow, matched to your light and grain) or `hologram` (glowing projection with scanlines and a projector ring) |
| Your own character | A PNG with transparency, a GIF/WebP, a video with alpha, or a green/blue-screen video (keyed automatically) |
| Where | `palm` (default), `above`, `finger`, or `fixed` (no hand needed) |
| Size, start/end, colours | `--size 1.3`, `--start 2 --end 9`, `--accent #FF5A5F` |
| Summon | Open hand = it appears with a pop, fist = it vanishes |
| Pokes | Your other index finger touching it makes it squish, then heart eyes |
| Speech | `--say "Hi!@1.2-3.0"` bubbles; `--voice line.wav` makes it talk (mouth moves with the audio) |

How it stays believable: hand landmarks from MediaPipe, smoothing that's steady when you're still and
quick when you move (the One Euro filter), a soft contact shadow, colour and brightness matched to
the scene, matching film grain and softness, motion blur on fast moves, and a short hold if tracking
drops for a moment.

Limits: it's 2D, so your fingers can't wrap around it and it won't change perspective if you turn
your hand far away. The hologram style hides this best. The built-in robot is an original character;
Claude won't recreate brand mascots or logos, but your own character file works.

Want the photoreal "tiny me in my hand" look? That's made with AI video tools (Seedance, Kling, Veo,
Runway). Claude can write the prompt for those, or you can bring an AI-made green-screen character
back into your own footage with `/avatar`.

### /create: a video from scratch

For anything you don't have footage for: hype intros, kinetic typography, promos, lyric videos, memes,
explainers, data stories, trailers. With a song, scene cuts land on the bars and the animation hits
the beats (`"sync": "bars"`). When facts are involved, Claude researches them first.

Claude plans one idea per scene and codes each scene as an animation (words slamming in on the beat,
counting numbers, growing bars, drawn lines). A hidden browser records every frame, so text and
timing stay exact. Music ducks under the narration, and captions follow the words.

Voiceover, best first:

- An AI voice from ElevenLabs, if you've connected it in Claude: Claude picks a voice that fits,
  generates the whole script as one take (it uses your ElevenLabs credits), and `create.py voice`
  cuts it into lines at the pauses and times each scene to its line. With an API key instead, set
  `ELEVENLABS_API_KEY` and use `--engine elevenlabs`.
- Your computer's own voices (on a Mac, the same voices as `say`).
- Your own recording: one file for the whole script (`"voiceover"`) or one per scene (`"audio"`).

An on-screen presenter can narrate it: a hologram face or pro-editor's robot whose mouth moves with
the actual voice (`K.host` in a scene). Claude won't draw other people's mascots here either.

> "/create a 6-second hype intro for my channel, synced to intro.mp3"
>
> "/create a 40-second TikTok about why the Roman Empire fell, dark style, deep male voice"

Before the slow render Claude checks a sheet of still frames from every scene and fixes anything
cut off or overlapping. It's motion graphics, not filmed footage. For realistic shots, clips from an
AI video tool (Higgsfield, Veo, Kling, Runway; Claude checks the cost with you first) or your own
b-roll go into a scene with `K.clip` and play frame-accurately under the text. Claude won't generate
realistic footage of a real person.

### /shorts: one long video, several clips

Give it a stream, podcast, commentary or interview. It finds stretches of whole sentences (20-60 s by
default), scores each one on four things and explains the score:

| Signal | What it looks for |
|---|---|
| Hook | The first sentence: a question, talking to "you", a number, a strong word. "So", "um" and "and" openers lose points |
| Energy | How loud and lively it is compared with the rest of the video |
| Ending | Finishes on a full stop, question or exclamation, not mid-thought |
| Pace | Words per second in the range that holds attention on Shorts |

Claude then reads every candidate's words and re-ranks them like an editor (does the first line stop
the scroll, does it make sense without context, is there a payoff), and suggests titles. You pick;
it renders each one cut on sentence boundaries, reframed to 9:16 on your face, with word-by-word
captions.

> "/shorts" + your stream recording: "give me 5 TikToks, 30-45 seconds each"

### /reference: find examples first

Searches TikTok, Instagram, YouTube, Reddit, tutorials (and GitHub for technical effects) for your
idea. You get 3-6 references with links and credit, what makes each work, how it's made, what the
plugin can do automatically, and what they have in common. Then it asks how you want yours (closest /
mix / your twist), and writes the style recipe or plan. It never downloads videos from those sites;
if you save a few references yourself, `/style-match` measures them exactly.

### /checkup: is my footage OK?

Checks each file for:

| Problem | What it means | Fix |
|---|---|---|
| Variable frame rate | Phones and screen recorders change frame rate on the fly. After cuts, audio slowly drifts out of sync. | `--fix` makes a steady copy |
| HDR (iPhone HLG, Dolby Vision) | Extra-bright color info most editing pipelines don't understand: colors turn grey and flat | `--fix` makes a normal (SDR) copy |
| Audio tracks | Is your mic on its own track? Any audio at all? | Tells you which track to use |
| Clipping | The recording itself distorted (hit 0 dB) | Can't be repaired; lower the volume next time |
| Loudness, resolution, frame rate, rotation | Info for the edit | - |

`--tests` also tries face detection and a 20-second transcript on your footage, so you know now
whether those features will work on your machine.

### /trends: what's working right now

Searches current edit styles and sounds for your niche (Fortnite, Rocket League, other games, vlogs,
travel), explains what's trending in plain words, and turns the one you pick into a style recipe.
Trend info is only as current as what's online that week. If your Claude setup supports scheduled
tasks, you can ask for a weekly trend report.

### /style-match: copy a style

Give it 1-3 edits you like (files or downloaded videos). It measures:

- pace (how long shots last, how cuts line up with the beat)
- color (brightness, saturation, contrast)
- flashes and effects
- and Claude studies frame sheets for things numbers can't catch (text style, framing)

The result is a **style recipe** your montage uses. Reference videos are only analyzed; your edit
only ever uses your footage.

### /highlights: find the best moments

| Mode | Finds | Best for |
|---|---|---|
| `action` (default) | Busy picture + loud game sound (fights, goals, explosions) | Gaming |
| `reactions` | Your voice getting loud or excited | Funny moments, commentary |
| `scenic` | Sharp, colorful, steady, well-exposed shots, one per scene | Travel, events, b-roll |

Clips include a few seconds of setup before the moment (`--context`) so they make sense on their own.
It finds loud, busy or pretty moments, not "good plays", so check its picks. If your recording has
separate game and mic tracks, Claude picks the right one (`--audio-track`).

### /describe-clip: find or edit by description

Three jobs, and it figures out which you mean:

- **Find**: "the goal off the ceiling", "the part where we jump in the pool"
- **Edit one clip**: slow-mo, speed ramps, freeze frames, zooms, flashes, shake, RGB glitch,
  text, music, trimming, vertical. Effects are placed by time, for example "slow-mo the last kill".
- **Label**: builds a searchable clip library of your recordings.

Claude can't watch video like you do; it reads still frames. Very fast moments (a single-frame
flick) are easier to find if you give a rough time.

### /montage: cut clips to a song

The main event. What you can ask for:

| Ask for | What it does |
|---|---|
| Velocity / speed ramps | Fast into the hit, slow after, with motion blur on the fast part |
| Zoom punches | Quick zoom on strong beats |
| Shake | Camera shake on drops |
| Flashes | White (or any color) flash on hits |
| RGB split / glitch | Chromatic glitch on hits |
| Slow-mo | Smooth slow motion on the drop |
| Cold open | Starts with the payoff, rewinds VHS-style, then plays the buildup |
| Loop ending | The last shot flows back into the first, so replays feel seamless |
| Hook text | A curiosity line in the first 1.8 seconds |
| SFX | Whooshes on effect cuts, an impact on drops, a riser before the first drop (off by default) |
| HUD insets | Vertical crop that keeps the scoreboard / kill feed / minimap visible as small boxes |
| Sound-ready version | A version without the song, so you can add it as an in-app sound to join a trend, plus a guide for where to trim it |
| 3 A/B versions | Best clip first / reshuffled / song starting at the drop, to test what performs |

Fits for vertical: `crop` (fills the screen, cuts the sides), `blur` (whole frame over a blurred
copy, safest for Rocket League), `hud` (crop + HUD insets).

Claude tells you if you're stacking too many effects: 2-3 signature moves per edit beats everything at once.

### /vlog-edit: talking videos

See the [talking video workflow](#talking-video--vlog--commentary). Useful extras:

- Pace: "punchy" (cuts pauses over 0.3 s) for short-form, "relaxed" (0.6 s) for long-form.
- Caption styles: `highlight` (default), `pop` (each word pops in), `plain`; colors yellow, green,
  cyan, pink, red, white; 2 or 3 words at a time; top, center or lower. Ask for an `.srt` file to
  upload to YouTube for accessibility.
- Two people in frame, or the crop follows the wrong face? Give the crop positions by hand
  ("keep the left person until 0:12, then the right").
- Transcripts mishear names, slang and game terms. Check them before captions are burned in;
  Claude fixes the words and re-runs.
- Claude only removes what you said. It never rewords or invents speech.
- Key words in captions are coloured automatically (numbers, scores, words you said louder,
  caps or "!"), in about a third of the caption groups so it stays special. Name your own:
  "highlight clutch and 1v4". Turn it off: "no coloured words".
- Punch-ins can alternate (two-camera look) or hit the punchline (the pieces you said with the
  most energy).

### /long-video: 5-45+ minute videos

See the [long video workflow](#long-youtube-video-5-45-minutes). Transitions: `fade` (dip to black,
default), `flash` (dip to white, hype), `cut`. Every section is set to the same loudness so nothing
jumps in volume. Chapters are embedded in the file and written to a text file for the description
(YouTube needs 3+ chapters, each 10 s+, starting at 0:00).

### /color: correct and grade

1. Claude makes a grid of one frame in every look: original, clean, warm, cinematic, vivid, moody,
   vintage. You pick by eye.
2. It measures your footage and corrects exposure and color casts (blue indoor light, green
   fluorescents), but keeps golden-hour warmth on purpose.
3. It applies the look at the strength you want (subtle 0.4, default 0.7, full 1.0), with a
   before/after image to check skin tones.

Every grade is also saved as a **`.cube` LUT**: load it in your editor and reuse it on every clip
from the same shoot ([Part 6](#part-6-finishing-in-your-own-editor)). For long 4K videos, ask for
"just the LUT" and apply it in your editor in real time instead of an extra full render.

Mixed lighting (window + lamp) can't be fully fixed by one correction over the whole frame. Claude
will say so.

### /thumbnail

Finds the sharpest, most colorful, best-exposed frames and shows you numbered candidates. You pick
one; it builds a 1280x720 thumbnail with punchy color, a vignette and big outlined text (3-5 words
reads best at phone size). Saved as JPG under YouTube's 2 MB limit.

### /edit-review: coaching

For your own edits (or pro-editor's). Notes on beat sync with exact timestamps and frame offsets,
dead spots, hook strength, ending, loudness, and a comparison with a target style if you give one.
Short and actionable by default; ask for the deep version if you want it.

### /export: ready to post

| Platform | Size | Note |
|---|---|---|
| TikTok | 1080x1920 | Length warning over 10 min |
| Reels | 1080x1920 | Length warning over 3 min |
| Shorts | 1080x1920, up to 2160x3840 | Length warning over 3 min |
| Feed (Instagram) | 1080x1350 | - |
| Square | 1080x1080 | - |
| YouTube | 1920x1080, up to 3840x2160 | - |

Also: trim, text overlays, burned-in subtitles, a watermark (only if you ask), loudness at
-14 LUFS (what TikTok and YouTube play at, so your video doesn't sound quieter than the rest),
and text placement that avoids each app's buttons and captions. Platform limits change, so ask
Claude to check if it matters.

**Post copy:** ask for titles (3 options, hook first, short enough not to get cut off), a YouTube
description (hook in the first two lines, chapters, credits), a short-form caption with 3-5 specific
hashtags, and a pinned-comment idea. It's written from what's actually in your video.

---

## Part 5: The files you get

| File | What it is |
|---|---|
| `*.mp4` | The video. Final renders are H.264 with AAC audio, which plays everywhere |
| `preview.mp4` | Small, fast version for checking. Not for posting |
| `*.xml` | Timeline for Premiere Pro / DaVinci Resolve (cuts, audio, effect markers) |
| `plan.json` | The montage plan: every cut, effect and timing |
| `highlights.json` | The moments found, with scores and times |
| `recipe.json` | A style recipe |
| `transcript.json` | Every word with its start and end time |
| `script.txt` | The transcript as numbered lines for editing by text |
| `cut.map.json` | How times in the cut video map to the original (keeps captions and chapters in sync) |
| `*.ass` / `*.srt` | Caption files (`.srt` is the one to upload to YouTube) |
| `*.cube` | Your color grade as a LUT |
| `*.compare.png` | Before/after color check |
| `chapters.txt` | Paste into the YouTube description |
| `*_sound-ready.mp4` + `*_sound_guide.txt` | Version without the song, plus where to trim the in-app sound |
| `post_copy.txt` | Titles, description, caption, hashtags |
| `checkup/checkup.json` | Footage report; `*_fixed.mp4` are the safe-to-edit copies |
| `<name>.talk.md` / `.talk.json` | What /talk heard: instructions, sounds, loud moments, transcript |
| `<name>.highlights.json` (from /talk) | "Clip that" moments and big reactions, ready for a montage |
| `*_avatar.mp4` + `*_check.jpg` | The avatar render and 8 frames to check its placement |
| `*.track.json` | The hand track, reused when re-rendering the avatar |
| `<idea>.md` (from /reference) | The reference board: links, techniques, how they're made, the plan |

---

## Part 6: Finishing in your own editor

### Timelines (.xml)

- **Premiere Pro:** File → Import → pick the `.xml`.
- **DaVinci Resolve:** File → Import → Timeline → pick the `.xml`.

You get every cut, the song and the clip audio, and **markers** where zooms, flashes, shakes and
slow-mo were added in the MP4. Slow-mo and speed ramps sit at normal speed in the timeline; the
markers show where to add them with real keyframes.

**CapCut** can't import timelines. Use the MP4, or export the clean highlight clips and finish there.

### LUTs (.cube)

- **Premiere Pro:** Lumetri Color → Creative → Look → Browse → pick the `.cube`.
- **DaVinci Resolve:** Color page → right-click a node → LUT (or copy the file into Resolve's LUT folder).
- **CapCut (desktop):** Adjust → LUT → Import.
- **Final Cut Pro:** add the **Custom LUT** effect and choose the file.

A LUT only holds color. The vignette (cinematic, moody) and grain (vintage) aren't in it; add those
in your editor if you want them. Menu names can change between versions of these apps.

---

## Part 7: High resolution, speed and disk space

### Resolution

`--res` (or `"resolution"` in a recipe or long-video project) sets the size:

| Value | 16:9 | 9:16 |
|---|---|---|
| `1080` (default) | 1920x1080 | 1080x1920 |
| `1440` | 2560x1440 | 1440x2560 |
| `2160` / `4k` | 3840x2160 | 2160x3840 |
| `source` | Matches your footage, capped at 4K | same |

- **TikTok and Reels** shrink anything above 1080p, so those exports stay 1080x1920. A bigger
  render there only costs time.
- **YouTube** generally streams 1440p and 4K uploads at higher quality, so 4K footage is worth
  exporting at `source`. **Shorts** gains a little from bigger uploads.
- **Previews** stay small whatever you choose.

### Speed

- Rough cost: **1440p ≈ 2x** and **4K ≈ 4x** the time of 1080p.
- **Graphics card:** final renders use your GPU's video encoder (NVIDIA NVENC, AMD AMF, Intel
  Quick Sync, Apple VideoToolbox) when it works, and fall back to the CPU by themselves if it fails.
  `check_setup.py` and the self-test tell you which one you have.
- Force the CPU (if a GPU render ever looks wrong): set the environment variable `PRO_EDITOR_GPU=0`.
  Force a specific encoder: `PRO_EDITOR_GPU=nvenc` (or `qsv`, `amf`, `videotoolbox`).
- **Transcripts** on a CPU take about as long as the video, or longer, with the default model.
  An NVIDIA GPU is much faster. Ask for the "base" model to trade a little accuracy for speed.
- The self-test measures your computer, so you get real numbers instead of guesses.

### Disk space

Long edits write temporary pieces before joining them. Keep free:

- about **10-20 GB** for a 45-minute 1080p video
- **40+ GB** for long 4K projects

---

## Part 8: Style recipes

A recipe is a small JSON file that describes an editing style: shape, pace, color, effects, layout
and audio. `/style-match` and `/trends` write them for you; you can also ask Claude to tweak one
("make the cuts faster", "less saturated", "no shake").

The main settings:

| Setting | Examples |
|---|---|
| `format.aspect`, `format.fps`, `format.resolution` | `"9:16"`, `60`, `"source"` |
| `pacing.cut_every_beats` | `0.5` (very fast), `1`, `2` (default), `4`, `8` (slow) |
| `color` | target brightness, saturation, contrast |
| `effects` | zoom punches, shake, flashes, slow-mo, velocity ramps, RGB split, letterbox, text |
| `layout` | `crop`, `blur` or `hud` with HUD boxes |
| `audio` | game sound volume under the song, loudness target, SFX |

The full format, with every field explained:
[skills/style-match/references/recipe-format.md](../skills/style-match/references/recipe-format.md)

---

## Part 9: Running the scripts yourself

Everything Claude runs is a normal Python script in `scripts/`, so you can run them without
Claude. Every script has `--help`.

| Script | Does | Example |
|---|---|---|
| `check_setup.py` | Checks ffmpeg, Python packages, GPU encoder | `python scripts/check_setup.py` |
| `selftest.py` | Tests every tool + render speed | `python scripts/selftest.py --models` |
| `checkup.py` | Footage problems + fixed copies | `python scripts/checkup.py footage/ --fix` |
| `beats.py` | Tempo, beats, drops of a song | `python scripts/beats.py song.mp3` |
| `highlights.py` | Best moments | `python scripts/highlights.py rec.mp4 --mode action --top 8 --export-dir clips` |
| `build_montage.py` | Beat-synced montage | `python scripts/build_montage.py --song song.mp3 --clips clips/ --length 30 --preview` |
| `variants.py` | 3 A/B versions | `python scripts/variants.py --song song.mp3 --clips clips/ --length 20` |
| `analyze_style.py` | Recipe from reference edits | `python scripts/analyze_style.py ref1.mp4 ref2.mp4 --name my-style` |
| `library.py` | Searchable clip library | `python scripts/library.py index recordings/` then `search "goal off the ceiling"` |
| `clip_fx.py` | Edit one clip from a list of effects | `python scripts/clip_fx.py clip.mp4 edit.json --preview` |
| `vlog_cut.py` | Transcribe / script / jump cuts | `python scripts/vlog_cut.py cut vlog.mp4 --transcript t.json --fillers --punch-in 1.12` |
| `voice.py` | Voice cleanup | `python scripts/voice.py vlog.mp4 --strength medium` |
| `reframe.py` | Face-tracking vertical crop | `python scripts/reframe.py cut.mp4 --out vertical.mp4` |
| `captions.py` | Word-by-word captions | `python scripts/captions.py v.mp4 t.json --map cut.map.json --style pop` |
| `chapters.py` | YouTube chapters from a transcript | `python scripts/chapters.py t.json --at "1:Intro" "14:Main part" "31:Verdict" --map cut.map.json` |
| `color.py` | Looks grid / correction + look / LUT | `python scripts/color.py apply v.mp4 --look warm --compare` |
| `stitch.py` | Long video from sections | `python scripts/stitch.py project.json --preview` |
| `thumbnail.py` | Thumbnail candidates and builder | `python scripts/thumbnail.py make v.mp4@12.5 --text "1V4 CLUTCH"` |
| `review_edit.py` | Edit coaching | `python scripts/review_edit.py my_edit.mp4 --song song.mp3` |
| `export.py` | Platform exports | `python scripts/export.py final.mp4 --platforms tiktok youtube --res source` |
| `layout.py` | Grid for measuring HUD / safe-zone check | `python scripts/layout.py safe final.mp4@2 --platform tiktok` |
| `listen.py` | /talk: hear words, sounds and spoken instructions; voice notes | `python scripts/listen.py hear rec.mp4 --hotwords "Zayd, Rocket League"` |
| `avatar.py` | /avatar: looks sheet, hand check, render | `python scripts/avatar.py render clip.mp4 --style hologram --anchor above --preview` |

On macOS and Linux use `python3` instead of `python`.

---

## Part 10: Troubleshooting

| Problem | Fix |
|---|---|
| "ffmpeg not found" | Install ffmpeg ([Part 1](#part-1-setup)), then **close and reopen** the terminal or Claude app so it's picked up |
| A Python package is missing | `python -m pip install numpy librosa soundfile` (use the same Python that runs the scripts) |
| Audio drifts out of sync after cuts | Variable frame rate. Run `/checkup --fix` and edit the fixed copy |
| Colors look grey and washed out | HDR footage. `/checkup --fix`. If it says `zscale` is missing, install the full ffmpeg build (Windows: the gyan.dev "full" build). Long-term: turn off HDR recording on your phone for footage you'll edit |
| "Speech model couldn't load" | It downloads once on first use. Check the internet connection, firewall or VPN, then try again |
| Face tracking follows the wrong person or loses you | Side profiles, sunglasses and dark scenes are hard. Ask for manual crop positions, or a center/blurred crop |
| Captions have wrong words | Tell Claude the right spelling ("it's 'Rocket League', not 'rocket leak'"); it fixes the transcript and re-runs |
| The montage cuts feel off-beat | Ask for `/edit-review` with the song: it shows the exact cuts and by how much. Songs with soft or changing tempo are harder to sync |
| "GPU encoder failed on this render; using the CPU instead" | Harmless: it fell back by itself. If it happens every time, update your graphics driver, or set `PRO_EDITOR_GPU=0` to skip the GPU attempt |
| A render is very slow | Use previews while deciding, render full quality once, lower `--res`, close other heavy apps. The self-test shows what's normal for your computer |
| "No space left on device" | Free up disk space ([Part 7](#disk-space)) and run it again. Long videos reuse sections that already finished |
| The plugin's commands don't show up (Claude Code) | Run `/reload-plugins`, or restart Claude Code. Still missing: `/plugin` → Errors tab |
| "No hand found" (avatar) | Open palm toward the camera, even light (not backlit), whole hand in frame, no gloves. Or place it without tracking: "put it bottom right" (`--anchor fixed`) |
| The avatar sits beside the hand or jitters | Ask Claude to check the tracking sheet; it can switch hands (`--hand left-side`), use `above`, or change size. Very fast moves lag a frame or two |
| The avatar looks pasted on | Try the hologram style, or more softening (`--soften 1.2`) and colour matching (`--match 0.45`) |
| The hologram is hard to see | It's light added to the picture, so it fades on bright backgrounds like a white wall or the sky. Film against something darker, or use the solid style |
| "clip that" wasn't picked up | Say it clearly, right after the moment, louder than the game audio. If your mic is on its own track, Claude listens to that track. Check the transcript in the .talk.md: if it misheard, tell Claude what you said |
| The sound model / hand model couldn't download | They download once from Google (storage.googleapis.com). Check the internet connection, firewall or VPN, then try again |
| Something else | Run `python scripts/selftest.py` and [open an issue](https://github.com/abdullahnaji353-blip/pro-editor/issues) with its output |

---

## Part 11: FAQ

**Is it free?** The plugin is free and open source (MIT). You need a Claude plan that supports
plugins, or Claude Code.

**Does it upload my videos?** No. The plugin works on files where Claude runs (your computer in
Claude Code or the desktop app with a connected folder). When Claude needs to see the video, it
looks at still frames, like any image you share with it.

**Which games does it know?** Any. Fortnite and Rocket League have built-in HUD presets
(minimap, scoreboard, boost); for other games, Claude measures where the HUD sits on a frame.

**Can it use CapCut, Premiere or Resolve directly?** It doesn't click around in those apps. It
makes finished videos, plus timelines (Premiere/Resolve) and LUTs (all four) for finishing there.

**Will my edit get copyright-claimed?** If you use a copyrighted song, it might be muted or
claimed. That's between you and the platform. The sound-ready version lets you add the song
in-app instead, which is how trends usually work on TikTok and Reels.

**Can it make the video go viral?** No tool can promise that. It follows what tends to work
(fast hook, one peak moment, a loop, readable captions, right loudness) and can make A/B versions
so you can test.

**Does it work in other languages?** Transcripts work in many languages (Claude can force one with
`--language`). Captions are tested in English; for other alphabets (Arabic, for example) check
the preview, since the caption font has to include those letters.

**Can I change the plugin?** Yes. It's MIT licensed: fork it, change it, share it.

---

## Part 12: Words you'll see

| Word | Meaning |
|---|---|
| **Beat sync** | Cuts land exactly on the music's beats |
| **Drop** | The big moment in a song where the energy hits |
| **Velocity edit / speed ramp** | Footage speeds up into a moment and slows down after it |
| **Cold open** | Starting with the best moment before showing how it happened |
| **Hook** | The first 1-2 seconds that make people keep watching |
| **Jump cut** | Cutting out pauses so the talking flows without dead air |
| **Punch-in** | A slight zoom on every other jump cut, so it looks like a second camera |
| **Safe zone** | Parts of a vertical video not covered by the app's buttons and captions |
| **HUD** | On-screen game info: kill feed, minimap, scoreboard, boost meter |
| **LUFS** | Loudness. -14 LUFS is what TikTok and YouTube play at |
| **Ducking** | Music automatically gets quieter while someone talks |
| **VFR (variable frame rate)** | Frame rate that changes during a recording; causes audio drift |
| **HDR** | High dynamic range video; looks washed out if it's edited like normal video |
| **LUT (.cube)** | A file that stores a color grade, so any editor can apply the same look |
| **Timeline (.xml)** | Your edit as a project file you can open and change in Premiere or Resolve |
| **Preview** | Small, fast render for checking. Not the final quality |
| **Recipe** | A style written down as settings (pace, color, effects) |
| **Callout** | Saying "clip that" right after a great moment, so it gets found later |
| **Hotwords** | Names and terms given to the speech recognizer so it spells them right |
| **Hand tracking** | Finding the 21 points of your hand in every frame, so the avatar can follow it |
| **Contact shadow** | The soft shadow right under a character's feet that makes it look like it's standing on something |
| **Punch-in** | A slight zoom on a cut. Alternating = every other cut; on the punchline = the high-energy parts |
