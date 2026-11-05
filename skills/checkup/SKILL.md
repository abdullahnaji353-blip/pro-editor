---
name: checkup
description: >
  This skill should be used before editing new footage, or when the user says "check my video",
  "is my footage ok", "why is my audio out of sync", "why do my colors look washed out/grey",
  "my iPhone video looks weird after editing", "what's wrong with this file", or invokes /checkup.
  Finds variable frame rate, HDR, audio-track, keyframe, loudness and clipping problems and can
  make fixed copies that are safe to edit.
metadata:
  version: "0.7.0"
---

# Checkup

## Run

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/checkup.py <files or folder> --out-dir <work>/checkup [--fix] [--tests]
```

(If the variable is empty, the scripts folder is two levels above this file.)

- `--fix` writes `<name>_fixed.mp4` for files that need it; use those copies for every later step.
  Originals are never touched. Fixing re-encodes, so it takes a while on long recordings.
- `--tests` also checks, on the user's own footage, whether face tracking finds a face and whether
  transcripts work (the speech model downloads on first use).

## Explain results in plain words

- **Variable frame rate**: phones and screen recorders change frame rate on the fly to save
  power. Editors then slowly drift audio out of sync. The fix makes it steady.
- **HDR** (iPhone HLG, Dolby Vision): extra-bright colour info that most edit pipelines don't
  understand, so it turns grey and flat. The fix converts it to normal video. The fix needs
  ffmpeg's `zscale`; if missing, tell the user to install a full ffmpeg build (Windows: gyan.dev
  "full"). Longer term: turn off HDR capture on the phone for footage they plan to edit.
- **Audio hits 0 dB / clipped**: the recording itself distorted. Editing can't fully repair it;
  suggest lowering mic/game volume next time.
- **1 audio track**: voice and game sound are mixed. Fine for most edits; for highlights in
  reactions mode or clean commentary, record separate tracks next time (OBS multi-track).
- **Keyframes far apart**: only matters for the clip library's fast mode.

Don't list the "ok" lines back verbatim; summarize what matters for the edit they want.

## Is the plugin itself working on this computer?

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/selftest.py` (add `--models` to also test transcripts
and face tracking) makes small test videos, runs every tool on them and prints PASS/FAIL with a
fix for each failure, whether the graphics card is used for encoding, and how long 1080p and 4K
renders take per finished minute on this computer. About 3-6 minutes. Use it after installing,
after updating ffmpeg/Python, or when something fails and it's unclear whether the footage or
the setup is to blame.
