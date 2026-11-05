# recipe.json format

`build_montage.py --recipe` merges this over its defaults, so any field can be left out.

```json
{
  "name": "clean-fortnite",
  "format": {
    "aspect": "9:16",          // "16:9" | "9:16" | "1:1" | "4:5"
    "fps": 60                  // 30 or 60
  },
  "pacing": {
    "cut_every_beats": 2,      // 0.5 | 1 | 2 | 4 | 8  (0.5 = cut on every half beat)
    "snap_cuts_to_beats": true,// false = cut every median_shot_sec instead of on beats
    "follow_energy": true,     // slower cuts where the song is quiet, every beat right after a drop
    "median_shot_sec": 0.9     // used when not snapping
  },
  "color": {                   // targets on a 0-1 scale; null = leave the footage alone
    "brightness": 0.45,        // average luma
    "saturation": 0.55,        // ~0.3 muted, ~0.6 punchy, 0.8+ very saturated
    "contrast": 0.75           // spread between darkest and brightest
  },
  "effects": {
    "zoom_punch_on_beats": true,   // quick zoom-in that eases out on strong beats and drops
    "zoom_amount": 1.12,           // 1.05 subtle, 1.12 normal, 1.25 aggressive
    "shake_on_drops": true,        // decaying camera shake on drop cuts
    "flash_on_strong_beats": false,// fade from flash_color on drops + every other strong beat
    "flash_color": "white",        // any ffmpeg color: white, black, 0xFF00AA
    "slowmo_on_drops": true,       // the 2 cuts starting at each drop play slowed down
    "slowmo_speed": 0.5,           // 0.5 = half speed
    "letterbox": false,            // cinematic black bars top and bottom
    "text_overlays": [             // seconds on the montage timeline
      {"text": "NAJI", "start": 0.0, "end": 1.5, "position": "center", "size": null}
    ],
    "velocity": "off",             // "off" | "strong_beats" | "all": speed ramp fast -> slow
    "velocity_fast": 2.0,          // speed going into the hit (1.6-2.5)
    "velocity_slow": 0.4,          // speed after the hit (0.3-0.5)
    "motion_blur": true,           // blur the fast part of velocity ramps
    "rgb_split_on_beats": false,   // chromatic RGB glitch on strong beats and drops
    "rgb_split_px": 14             // glitch strength at 1080p
  },
  "layout": {                      // optional
    "fit": "hud",                  // crop | blur | hud
    "hud": ["rl-scoreboard", {"x": 0.02, "y": 0.55, "w": 0.30, "h": 0.18, "scale": 0.55}],
    "hud_place": "bottom"          // bottom (default, above the app's caption zone) | top
  },
  "audio": {
    "game_audio_volume": 0.25,     // clip sound under the song; 0 = song only
    "normalize_lufs": -14,         // loudness target; null = leave as is
    "sfx": {                       // synthesized sound effects (off by default)
      "enabled": false,
      "whoosh_on": "effects",      // "effects" (cuts with zoom/flash/rgb/velocity) | "all" | "none"
      "impact_on_drops": true,
      "riser_before_drop": true,
      "volume": 0.5
    }
  }
}
```

(The comments are for reading here only. Real JSON files cannot contain comments.)

## Style starting points (when writing a recipe by hand)

| Style | cut_every_beats | velocity | zoom | shake | flash / rgb | slowmo | color |
|---|---|---|---|---|---|---|---|
| Velocity / hype edit | 1-2 | all, 2.2 / 0.35 | 1.2 | on | white + rgb | on, 0.4 | saturation 0.7, contrast 0.85 |
| Clean montage | 2 | off | 1.08 | off | off | on, 0.5 | light boost or null |
| Cinematic / moody | 4 | off | off | off | black, rare | on, 0.5 | saturation 0.35, letterbox on |
| Rocket League freestyle | 1-2 | strong_beats, 1.8 / 0.45 | 1.1 | drops only | white on drops | on, 0.5 | saturation 0.6 |
| Glitchy / "cc" edit | 0.5-1 | strong_beats | 1.15 | on | rgb on | off | contrast 0.85 |

Treat these as starting points and say so; real styles vary by editor.
