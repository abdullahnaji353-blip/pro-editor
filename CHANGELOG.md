# Changelog

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
