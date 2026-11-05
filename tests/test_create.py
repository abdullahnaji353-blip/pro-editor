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
    assert pick_engine("auto") in {"say", "sapi", "piper", "espeak", "none"}


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
