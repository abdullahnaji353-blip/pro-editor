import numpy as np

from conftest import transcript
from listen import find_commands, highlights_from, loud_moments, norm


def by_said(cmds):
    return {c["said"]: c for c in cmds}


def test_norm_strips_punctuation_and_arabic_marks():
    assert norm("Clip-that!") == "clipthat"
    assert norm("That's") == "thats"
    assert norm("كلود،") == "كلود"
    assert norm("مَرحبا") == "مرحبا"


def test_clip_callouts_are_found_and_lookalikes_ignored():
    tr = transcript(
        [
            (6.0, "Oh my god dude, clip that!"),
            (14.0, "I clipped that guy so hard."),
            (18.0, "I'll clip it later tonight"),
            (22.0, "That's a clip."),
        ]
    )
    cmds = find_commands(tr, pre=12.0)
    clips = [c for c in cmds if c["type"] == "clip"]
    assert [c["said"] for c in clips] == ["clip that!", "That's a clip."]
    first = clips[0]
    assert first["applies_to"][1] <= first["t"]  # the moment is before the callout
    assert first["t"] - first["applies_to"][0] <= 12.0 + 1e-6


def test_wake_word_instructions_and_their_direction():
    tr = transcript(
        [
            (30.0, "Claude, zoom in here."),
            (31.8, "So this is the new car."),
            (44.0, "I love the cloud today."),
            (47.0, "Cloud, slow mo that."),
            (50.0, "The editor at my school is cool."),
        ]
    )
    cmds = by_said(find_commands(tr))
    zoom = cmds["Claude, zoom in here."]
    assert zoom["type"] == "zoom" and zoom["where"] == "after"
    assert zoom["applies_to"][0] == 31.8  # the next line
    slow = cmds["Cloud, slow mo that."]  # a common mishearing, accepted with a verb
    assert slow["type"] == "slowmo" and slow["where"] == "before"
    assert slow["applies_to"][0] == 44.0
    assert not any("school" in s or "cloud today" in s for s in cmds)


def test_cut_that_after_another_command_targets_the_real_line():
    tr = transcript(
        [
            (54.0, "This part is boring."),
            (55.6, "Editor, cut this part."),
            (57.4, "Scratch that."),
        ]
    )
    cmds = find_commands(tr)
    removes = [c for c in cmds if c["type"] == "remove"]
    assert len(removes) == 2
    assert all(c["applies_to"][0] == 54.0 for c in removes)


def test_retake_drops_the_flubbed_line():
    tr = transcript(
        [
            (35.0, "And then I went to the, uh, wait, let me redo that."),
            (39.5, "And then I went to the shop."),
        ]
    )
    retake = [c for c in find_commands(tr) if c["type"] == "retake"][0]
    assert retake["applies_to"][0] == 35.0
    assert retake["applies_to"][1] < 39.5
    assert retake["confidence"] == "check"


def test_arabic_wake_word():
    tr = {
        "segments": [
            {
                "id": 1,
                "start": 0,
                "end": 1.3,
                "text": "كلود، زوم هنا",
                "words": [
                    {"w": "كلود،", "start": 0.0, "end": 0.4},
                    {"w": "زوم", "start": 0.5, "end": 0.8},
                    {"w": "هنا", "start": 0.9, "end": 1.2},
                ],
            },
            {
                "id": 2,
                "start": 3.5,
                "end": 5.0,
                "text": "هذا المكان الجديد",
                "words": [
                    {"w": "هذا", "start": 3.5, "end": 3.8},
                    {"w": "المكان", "start": 3.9, "end": 4.3},
                    {"w": "الجديد", "start": 4.4, "end": 4.9},
                ],
            },
        ]
    }
    (cmd,) = find_commands(tr)
    assert cmd["type"] == "zoom"
    assert cmd["said"] == "كلود، زوم هنا"  # stops at the pause, doesn't swallow the next line
    assert cmd["applies_to"] == [3.5, 5.0]


def test_every_command_span_is_listed_for_removal():
    tr = transcript([(10.0, "Claude, put the drop here."), (12.5, "Here we go")])
    (cmd,) = find_commands(tr)
    s, e = cmd["cmd"]
    assert s < 10.0 + 0.01 and e > s


def test_highlights_from_callouts_and_laughter():
    tr = transcript([(20.0, "clip that")])
    cmds = find_commands(tr)
    events = [{"type": "laughter", "start": 40.0, "end": 42.0, "peak": 0.5}]
    hl = highlights_from("video.mp4", {"duration": 60.0}, cmds, events)
    labels = [h["label"] for h in hl]
    assert labels[0].startswith("callout")  # callouts rank above reactions
    assert any(lbl == "laughing" for lbl in labels)
    laugh = [h for h in hl if h["label"] == "laughing"][0]
    assert laugh["start"] < 40.0  # includes the setup before the laugh


def test_loud_moments_finds_the_spike():
    db = np.full(600, -40.0)
    db[300:320] = -15.0
    picks = loud_moments(db)
    assert len(picks) == 1 and abs(picks[0]["t"] - 31.0) < 1.5
