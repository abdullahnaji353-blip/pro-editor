---
name: thumbnail
description: >
  This skill should be used when the user wants a "thumbnail", "YouTube thumbnail", "cover
  image", "make a thumbnail for this video", or needs a cover for a long-form video or montage.
  Finds the sharpest, most colorful frames, then builds a 1280x720 thumbnail with big bold text.
metadata:
  version: "0.7.0"
---

# Thumbnail

## Locate the scripts

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts` (if empty: `../../scripts` from this file).
Call it `$S`.

## 1. Find candidate frames

```
python3 $S/thumbnail.py candidates <video> [--highlights <work>/highlights.json] --top 8 --out-dir <work>/thumbs
```

With highlights it scores frames around the best moments; without, it samples the whole video.
It favors sharp (no motion blur), colorful, well-exposed frames and drops near-duplicates.
Read `candidates.png` if images can be viewed, and recommend 1-2 picks with a reason: a clear
subject (enemy in the scope, car mid-flip, the victory screen), not a blurry mid-turn frame.
Let the user choose; they know their video.

## 2. Text

3-5 words max, readable on a phone: the payoff or the tension ("1V4 CLUTCH", "HE DIDN'T SEE
ME", "FIRST FLIP RESET"). Don't repeat the video title word for word. Offer 2-3 options if the
user has none.

## 3. Build

```
python3 $S/thumbnail.py make <video>@<seconds> --text "1V4 CLUTCH" [--sub "no way"] \
    --side left|right --color yellow --out <work>/thumbs/thumbnail.jpg
```

Put the text on the side where the frame is emptiest (not over the subject). Yellow or white
reads best on gameplay. Output is a 1280x720 JPG under YouTube's 2 MB limit. Look at the result
and adjust side/color/frame if the text covers the action.
