---
name: voiceover
description: This skill should be used when the user invokes /voiceover or /tts, or asks to "add a voiceover", "text to speech", "read this script out", "make an AI voice", "narrate my video", "add a voice line at 0:05", "say this over my montage", "turn this text into audio", or wants spoken narration added to an existing video or saved as an audio file. Writes or takes the script, picks a voice (ElevenLabs, free Kokoro, or the computer's own), places each line at its time with the video's sound ducked underneath, and can burn captions.
metadata:
  version: "0.18.0"
---

# Voiceover (text to speech)

Spoken narration for anything: a voiceover file, voice lines laid onto a video (a montage, a
vlog, gameplay, a Short), or a whole narrated script. For videos made from scratch, `/create`
already voices its own scenes; this is for everything else.

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file). Call it
`$S`. Needs ffmpeg. Check with `python3 $S/check_setup.py`; ask before installing anything.

## 1. The words

- They gave a script: use it word for word. Fix only obvious typos, and say which.
- They want you to write it: one short question if the angle is unclear, then write it for the
  ear: short sentences, one idea each, numbers written how they're said ("one point eight
  million"), no stage directions. About 2.5 words a second, so a 30 s video takes ~75 words.
- Facts about real people, events or products: check them on the web first, same as `/create`.
- Lines tied to moments ("say this when the goal goes in"): find the moment first
  (`/describe-clip`, `/highlights`), then put each line at its time in `lines.json`:
  `[{"at": 2.0, "text": "..."}, {"at": 7.5, "text": "..."}]`.

## 2. The voice, best first

1. **ElevenLabs** when its connector is connected: list voices, pick one that fits (say which),
   generate the whole script as one take, download it, and lay it on with `--audio`. It spends
   their credits: never retry on your own; if it's busy, say so and offer Kokoro.
   With `ELEVENLABS_API_KEY` set instead: `--engine elevenlabs --voice <voice id>`.
2. **Kokoro**: free, natural, runs on their computer (`pip install kokoro-onnx soundfile`, the
   model downloads once). `--voice am_michael` (US male), `af_heart` (US female), `bm_george` /
   `bf_emma` (British). `python3 $S/tts.py voices` lists them.
3. **The computer's own voices**: `say` on a Mac, Windows voices, espeak-ng or Piper on Linux.
4. **Their own recording**: `--audio my_take.m4a`. Their own voice beats any AI voice for a
   personal channel; offer it when it fits.

Never clone or imitate a real person's voice (a celebrity, a streamer, a politician) or present
the AI voice as someone real.

## 3. Make it

```
python3 $S/tts.py say "text" --voice am_michael --out <work>/voice.wav        # just the audio
python3 $S/tts.py say --file script.txt --speed 1.08 --out <work>/voice.wav
python3 $S/tts.py onto <video> --text "line" --at 1.5 --out <out>.mp4          # one line on a video
python3 $S/tts.py onto <video> --lines <work>/lines.json --captions --out <out>.mp4
python3 $S/tts.py onto <video> --audio <work>/elevenlabs.mp3 --at 0.3 --out <out>.mp4
```

- `onto` ducks the video's own sound under the voice (`--duck 0.25`; lower = deeper dip,
  `--duck-level 0.6` lowers it overall) and ends at -14 LUFS. It warns when a line runs into the
  next one or past the end: shorten the line, `--speed 1.1`, or move it.
- `--captions` burns word-by-word captions for the spoken lines (the `/export` styles apply).
- Listen-check by numbers, not ears: run `check_render.py` on the result and report loudness.

## 4. Finish

Show the result, say which voice and engine you used, and offer `/export` for the platform.
Be clear that the voice is AI-generated when it is.
