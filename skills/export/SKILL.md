---
name: export
description: >
  This skill should be used when the user wants to "export for TikTok", "make it vertical",
  "resize for Shorts/Reels/YouTube", "add captions", "add subtitles", "add text", "trim it",
  or get a finished edit ready to post on one or more platforms, or asks for a title,
  description, caption or hashtags for a video. Reframes to each platform's size (crop or
  blurred background), burns in captions or text, checks length limits and writes post copy.
metadata:
  version: "0.8.0"
---

# Export

Finished edit → platform-ready files.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`. Run `python3 $S/check_setup.py` once per session; if anything is missing, show the
printed install commands and ask before installing.

## Run

```
python3 $S/export.py <video> --platforms tiktok shorts youtube --fit blur|crop \
    [--trim 0-28] [--text "TEXT@START-END@top|center|bottom" ...] [--srt file.srt | --transcribe] \
    [--watermark "@handle"] [--lufs -14 | --no-normalize] [--fit hud --hud <regions>] \
    [--res 1080|1440|2160|source] --out-dir <work>/exports
```

| Platform | Size | Length warning |
|---|---|---|
| tiktok | 1080x1920 | 10 min |
| reels, shorts | 1080x1920 | 3 min |
| feed | 1080x1350 | none |
| square | 1080x1080 | none |
| youtube | 1920x1080 (up to 3840x2160 with `--res`) | none |

`--res` applies to YouTube and Shorts only: TikTok and Reels downscale anything above 1080p, so
those stay 1080x1920. For 1440p/4K footage, `--res source` on YouTube is worth it (YouTube tends
to stream bigger uploads at higher quality); for Shorts it's a small gain for 2-4x the render time.
Final renders use the graphics card's encoder automatically when one works.

Platform limits change; if the user asks what the current limit is, look it up instead of
trusting this table.

## Choosing options

- `--fit blur` (default) keeps the whole frame on a blurred background. `--fit crop` fills
  the screen but cuts the sides of 16:9 gameplay. `--fit hud --hud <presets or x,y,w,h>` crops to
  the centre and keeps the kill feed/minimap/scoreboard as insets (see the montage skill's HUD
  section for measuring). For a montage already rendered at 9:16, the fit doesn't matter.
- Text/caption times are relative to the trimmed clip when `--trim` is used.
- `--text` is for hooks and labels ("1v4 CLUTCH", "@handle"). Keep hooks in the first 1-2s.
  Safe zones on 1080x1920 (conservative): TikTok top 108 / bottom 320 / right 120 px, Reels
  210 / 310 / 84, Shorts 120 / 300 / 96. Text placement already respects these; check a frame
  with `python3 $S/layout.py safe <video>@<s> --platform tiktok`.
- Audio is loudness-normalized to -14 LUFS by default (what TikTok/YouTube play at), so the
  edit doesn't sound quieter than everything around it. `--no-normalize` keeps it as is.
- `--watermark "@handle"` adds a small tag top-left. Branding is off unless the user asks for
  it in this request.
- Word-by-word animated captions for talking videos come from `captions.py` (see `/vlog-edit`);
  `--srt` here burns a plain subtitle file. `--transcribe` makes captions from speech with the optional
  `faster-whisper` package; ask before installing it, and skip it for music-only edits.

## Post copy (titles, descriptions, captions, hashtags)

Write it when the user asks, and offer it in one line when delivering final files. Base every
line on what's actually in the video (transcript, highlight labels, what the user said); never
promise something the video doesn't show.

- **YouTube title**: 3 options, under ~60 characters so it doesn't get cut off, the hook up
  front. Match the thumbnail text, don't repeat it word for word.
- **YouTube description**: the first 1-2 lines show above "more", so they carry the hook and
  the keywords people would search. Then the chapters (from `chapters.py` or the stitch
  `_chapters.txt`), then links/credits (song credit if they used one).
- **TikTok / Reels / Shorts caption**: one short line that adds to the video (a question or
  context, not a description of what they're watching) plus 3-5 specific hashtags (game,
  mode, topic). No walls of tags.
- **Pinned comment** idea: a question that gets replies ("which play was cleaner, 1 or 3?").

Hashtag and caption trends change fast; if the user asks what's working right now, run
`/trends` or search instead of guessing. Save the copy as `<work>/post_copy.txt` next to the
exports so it's easy to paste.

## Verify and deliver

Check each output with `ffprobe` (size, duration, audio present). If images can be viewed, pull
one frame from a text moment to confirm nothing is cut off. Send or point to the files, one line
per platform.
