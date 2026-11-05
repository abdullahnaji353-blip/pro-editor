import numpy as np

from conftest import transcript
from shorts import candidates, pick, score, sentences, sub_transcript

TR = transcript(
    [
        (0.0, "So um yeah today we are just going to look around."),
        (6.0, "Why does nobody use this insane trick?"),
        (9.0, "You can win every round with it."),
        (12.0, "Here is the proof."),
        (30.0, "And then we went home and it was fine I guess."),
    ]
)


def test_sentences_split_on_punctuation():
    s = sentences(TR)
    assert [x[0]["w"] for x in s] == ["So", "Why", "You", "Here", "And"]


def test_a_strong_hook_beats_a_weak_opener():
    rms = np.ones(200)
    cands = candidates(sentences(TR), 4, 12)
    for c in cands:
        c["s"] = score(c, rms)
    best = pick(cands, 1)[0]
    assert best["sents"][0][0]["w"] == "Why"
    weak = next(c for c in cands if c["sents"][0][0]["w"] == "So")
    assert any("weak opener" in n for n in weak["s"]["notes"])
    assert best["s"]["score"] > weak["s"]["score"]


def test_picks_never_overlap():
    rms = np.ones(200)
    cands = candidates(sentences(TR), 2, 40)
    for c in cands:
        c["s"] = score(c, rms)
    chosen = pick(cands, 5)
    spans = sorted((c["start"], c["end"]) for c in chosen)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))


def test_sub_transcript_is_shifted_to_the_clip():
    sub = sub_transcript(TR, 5.85, 12.0)
    words = [w for s in sub["segments"] for w in s["words"]]
    assert words[0]["w"] == "Why" and abs(words[0]["start"] - 0.15) < 1e-6
    assert all(0 <= w["start"] < w["end"] <= 6.15 for w in words)
