from create import caption_transcript, pick_engine, scene_duration


def test_scene_length_follows_the_narration():
    assert scene_duration({"narration": "", "min_duration": 3}) == 3
    long = scene_duration({"narration": " ".join(["word"] * 26)})
    assert 10 < long < 11  # 26 words at 2.6 words/s plus a beat of air
    assert scene_duration({"narration": "hi", "duration": 7}) == 7


def test_caption_timings_stay_inside_each_scene():
    pj = {
        "scenes": [
            {"narration": "first line here"},
            {"narration": ""},
            {"narration": "last one", "audio_duration": 1.0},
        ]
    }
    tr = caption_transcript(pj, [3.0, 2.0, 2.0])
    first, last = tr["segments"]
    assert first["words"][0]["start"] >= 0 and first["words"][-1]["end"] <= 3.0
    assert 5.0 <= last["words"][0]["start"] and last["words"][-1]["end"] <= 6.2
    assert all(w["start"] < w["end"] for s in tr["segments"] for w in s["words"])


def test_engine_choice_respects_an_explicit_pick():
    assert pick_engine("none") == "none"
    assert pick_engine("auto") in {"kokoro", "say", "sapi", "piper", "espeak", "none"}


def test_scenes_snap_to_bars():
    from create import scene_beats, snap_durations

    beats = {"beats": [i * 0.5 for i in range(1, 60)], "downbeats": [i * 2.0 for i in range(1, 15)], "drops": [8.0]}
    pj = {"sync": "bars", "scenes": [{"duration": 3.1}, {"duration": 4.4}, {"duration": 2.0}]}
    assert snap_durations(pj, beats)
    ends, t = [], 0.0
    for s in pj["scenes"]:
        t += s["duration"]
        ends.append(round(t, 3))
    assert ends == [4.0, 8.0, 10.0]  # every cut on a bar, none cut much shorter than planned
    per = scene_beats(pj, beats, [s["duration"] for s in pj["scenes"]])
    assert per[1]["downbeats"] == [0.0, 2.0] and per[2]["drops"] == [0.0]  # the drop opens scene 3
    assert per[1]["beats"][0] == 0.0 and max(per[1]["beats"]) < 4.0


def test_no_sync_without_music_beats():
    from create import snap_durations

    assert not snap_durations({"sync": "bars", "scenes": [{"duration": 3}]}, None)


def test_whole_voiceover_is_cut_at_the_pauses_between_scenes():
    import numpy as np

    from create import pauses, split_points

    sr = 16000
    tone = lambda s: 0.3 * np.sin(np.arange(int(s * sr)) * 0.2)  # noqa: E731
    gap = lambda s: np.zeros(int(s * sr))  # noqa: E731
    # three lines: 2 s, pause, 1 s (with a short breath inside), pause, 3 s
    x = np.concatenate([tone(2), gap(0.6), tone(0.5), gap(0.15), tone(0.5), gap(0.5), tone(3)]).astype(np.float32)
    gaps = pauses(x, sr)
    assert len(gaps) == 2  # the breath is too short to count
    cuts = split_points(gaps, [10, 5, 15], len(x) / sr)
    assert abs(cuts[0] - 2.3) < 0.1 and abs(cuts[1] - 4.0) < 0.1


def test_split_never_goes_backwards_without_pauses():
    from create import split_points

    cuts = split_points([], [1, 1, 1, 1], 8.0)
    assert cuts == sorted(cuts) and len(cuts) == 3 and cuts[0] > 0


def test_audio_mix_numbers_every_voice_line_and_the_music(tmp_path, monkeypatch):
    import create

    seen = {}
    monkeypatch.setattr(create.subprocess, "run", lambda cmd, **k: seen.setdefault("cmd", cmd))
    pj = {"music": "song.mp3", "scenes": [{"audio": "a.wav"}, {}, {"audio": "b.wav"}, {"audio": "c.wav"}]}
    assert create.build_audio(tmp_path, pj, [2, 2, 2, 2], 8.0, tmp_path / "m.wav")
    graph = seen["cmd"][seen["cmd"].index("-filter_complex") + 1]
    assert "[0:a]" in graph and "[1:a]" in graph and "[2:a]" in graph and "[3:a]" in graph
    assert "[4:a]" not in graph


def test_in_scene_captions_split_words_by_scene():
    from create import in_scene_captions, scene_captions

    pj = {"captions": True, "look": "editorial", "scenes": [{"id": "a", "narration": "one two three"},
                                                            {"id": "b", "narration": "four five"}]}  # fmt: skip
    assert in_scene_captions(pj)
    assert not in_scene_captions({**pj, "caption_mode": "burn"}) and not in_scene_captions({**pj, "look": None})
    caps = scene_captions(pj, [3.0, 3.0])
    assert [w["w"] for w in caps["a"]] == ["one", "two", "three"] and [w["w"] for w in caps["b"]] == ["four", "five"]
    assert all(0 <= w["start"] < 3 for c in caps.values() for w in c)


def test_kit_ships_its_fonts_and_three():
    from pathlib import Path

    kit = Path(__file__).resolve().parents[1] / "scripts" / "create_kit"
    css = (kit / "looks.css").read_text()
    import re

    for f in re.findall(r'url\("fonts/([^"]+)"\)', css):
        assert (kit / "fonts" / f).exists(), f
    assert (kit / "vendor" / "three.cjs").exists() and (kit / "fonts" / "OFL.txt").exists()


def test_collage_kit_files_and_icons_are_registered():
    from pathlib import Path

    kit = Path(__file__).resolve().parents[1] / "scripts" / "create_kit"
    src = (kit / "icons.js").read_text()
    for name in ("capitol", "skyline", "michigan", "ballot", "money"):
        assert f"I.{name} =" in src
    import create

    page_src = Path(create.__file__).read_text()
    assert '"icons.js", "collage.js"' in page_src
