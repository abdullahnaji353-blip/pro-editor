# pro-editor

**Make Claude a professional editor.**

A free plugin that turns Claude into a video editor for **gaming clips, vlogs, and travel or event
videos**, from 10-second TikToks to 45-minute YouTube videos. You talk to Claude normally ("cut my
clips to this song", "remove the ums and add captions"), and it does the editing with ffmpeg and
Python on your computer.

- Beat-synced montages with velocity ramps, zoom punches, shake, flashes, RGB glitch and slow-mo
- Talking videos: jump cuts, edit by deleting text, retake spotting, punch-in zooms, word-by-word captions
- Finds your best moments (kills, goals, funny reactions, the prettiest shots)
- "Find the clip where I clutched a 1v3": finds moments by description
- Copies the style of edits you like, or researches what's trending right now
- Color correction and looks, saved as a `.cube` LUT you can reuse in your own editor
- Exports for TikTok, Reels, Shorts and YouTube (up to 4K), plus Premiere Pro / DaVinci Resolve timelines

> **Early version (v0.7).** Every tool is tested on test videos, but not much on real footage
> yet. Expect rough edges, especially in highlight picking and face tracking. Bug reports welcome.

---

## How to use it (5 minutes)

### 1. Install the plugin

**Claude app (desktop or web, paid plans):**
1. Open **Customize** in the left sidebar, go to the **Plugins** tab.
2. Click **Add**, then **Add marketplace**, then **Add from a repository**.
3. Enter `abdullahnaji353-blip/pro-editor`.
4. Find **pro-editor** in the **Discover** tab and add it.

**Claude Code (terminal):**
```
/plugin marketplace add abdullahnaji353-blip/pro-editor
/plugin install pro-editor@pro-editor
```
(Claude Code 2.1.275 or later can do it in one step: `/plugin install pro-editor --marketplace abdullahnaji353-blip/pro-editor`)

### 2. Install the editing tools (once)

The plugin needs **ffmpeg** and **Python 3.9+** on your computer. You don't have to do this by hand:
the first time you use it, Claude checks what's missing, shows you the commands and asks before
installing anything. If you'd rather do it yourself:

| | Command |
|---|---|
| Windows | `winget install --id Gyan.FFmpeg -e` (then reopen the terminal) and `python -m pip install numpy librosa soundfile` |
| macOS | `brew install ffmpeg` and `python3 -m pip install numpy librosa soundfile` |
| Linux | `sudo apt install ffmpeg` and `python3 -m pip install numpy librosa soundfile` |
| Optional: transcripts, captions, jump cuts on "um" | `python -m pip install faster-whisper` |
| Optional: face-tracking vertical crop | `python -m pip install "opencv-python-headless<5"` |

### 3. Give Claude your footage and say what you want

Put your clips in a folder Claude can reach (in Claude Code: the folder you started it in; in the
Claude app: a folder you connected, or attach the files). Then just ask, for example:

```
/start
```
```
Make a 20-second TikTok from the clips in my "fortnite" folder, cut to song.mp3. Hype style.
```
```
Here's my vlog. Cut the silences and the ums, make it vertical, add word-by-word captions.
```
```
Find the best shots from my Japan trip and make a 30-second recap to this song.
```
```
What Rocket League edit style is trending right now? Make my clips look like that.
```

Claude shows you a **quick preview first**, then renders full quality once you're happy.

### 4. Check it works on your computer (optional)

```
python scripts/selftest.py
```

It makes small test videos, runs every tool, prints PASS/FAIL with a fix for anything that fails,
and tells you how long 1080p and 4K renders take on your computer. Add `--models` to also test
transcripts and face tracking. Or just ask Claude: "run the pro-editor self-test".

**Full manual with every command, option and workflow: [docs/MANUAL.md](docs/MANUAL.md)**

---

## Commands

You don't need these (just describe what you want), but they're there if you like shortcuts.

| Command | Say something like | What it does |
|---|---|---|
| `/start` | "help me edit this" | The front door: checks your setup and footage, asks what you're making, runs the right tools in order |
| `/checkup` | "is my footage ok?" | Finds phone-footage traps (audio drift, washed-out HDR colors, clipping) and makes fixed copies |
| `/trends` | "what edit style is trending?" | Researches current edit styles and sounds and turns one into a style recipe |
| `/style-match` | "edit it like these 3 videos" | Measures pace, beat sync, color and effects in reference edits and writes a style recipe |
| `/highlights` | "find the best moments" | Action (fights, goals), reactions (your voice) or scenic (best-looking shots) |
| `/describe-clip` | "find the 1v3 with the shotgun" | Finds a moment by description, edits one clip the way you describe, or labels footage |
| `/montage` | "cut these clips to this song" | Beat-synced edit with effects, cold open, loop ending, hook text, SFX, HUD insets, 3 A/B versions |
| `/vlog-edit` | "cut the silences and ums" | Voice cleanup, transcript, edit by text, jump cuts, punch-ins, vertical crop, captions, chapters |
| `/long-video` | "make a 20-min YouTube video" | Montage parts + raw parts, transitions, music that ducks under your voice, chapters |
| `/color` | "make it look cinematic" | Auto correction + looks (clean, warm, cinematic, vivid, moody, vintage), saved as a LUT |
| `/thumbnail` | "make a thumbnail" | Picks the sharpest frames and builds a 1280x720 thumbnail with big text |
| `/edit-review` | "review my edit" | Coach feedback: off-beat cuts with exact timestamps, dead spots, hook, loudness |
| `/export` | "ready for TikTok and YouTube" | Platform sizes, captions/text, loudness, up to 4K, titles/descriptions/hashtags |

In Claude Code, plugin commands may show up as `/pro-editor:start`, `/pro-editor:montage` and so on.

## Where it runs

The editing happens wherever Claude runs commands:

- **Claude Code** or the **Claude desktop app with a connected folder**: on your computer, with
  your files. Best for big or long footage.
- **A cloud session**: in Claude's cloud workspace, on files you attach. Fine for short clips;
  uploading big 4K files is slow.

The plugin never uploads your footage anywhere. When Claude needs to "see" your video (finding a
moment, checking framing), it looks at small still frames, the same way it looks at any image you
share with it.

## Good to know

- **Preview first:** previews are small and fast; the full-quality render happens once at the end.
- **High resolution:** `--res 1080 | 1440 | 2160 | source`. TikTok and Reels stay 1080p (they
  shrink anything bigger). Your graphics card's encoder is used automatically when it works.
- **Long videos take time:** a 45-minute 1080p60 render can take 30-90+ minutes on a normal CPU,
  4K several times that. The self-test measures your computer.
- **Music:** copyrighted songs can get muted or claimed on upload. That's your call.
- **Reference videos** (for style matching) are only analyzed, never used in your edit.
- **Can't do (yet):** hand-drawn speed curves, optical-flow slow-mo, 3D camera moves, masking,
  transition packs, or controlling CapCut directly. Highlight picking finds loud, busy or
  good-looking moments, not "good plays", so check its picks. Transcripts mishear names and slang.

## Updating

- Claude Code: `/plugin marketplace update pro-editor`, then `/reload-plugins`.
- Claude app: manage it under **Customize → Plugins**.

See [CHANGELOG.md](CHANGELOG.md) for what changed in each version.

## Feedback

Found a bug or want a feature? [Open an issue](https://github.com/abdullahnaji353-blip/pro-editor/issues).
Include what you asked Claude, what happened, and the output of `python scripts/selftest.py`.

## License

MIT. Free to use, change and share. See [LICENSE](LICENSE).
