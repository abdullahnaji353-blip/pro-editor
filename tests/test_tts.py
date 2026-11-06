from tts import chunks, transcript


def test_long_text_splits_at_sentence_ends():
    text = "One two three. " * 60
    parts = chunks(text, limit=100)
    assert all(len(p) <= 100 for p in parts) and all(p.endswith(".") for p in parts)
    assert " ".join(parts).split() == text.split()


def test_caption_words_sit_inside_their_line():
    tr = transcript([(1.0, "watch this clip", 1.5), (4.0, "best play", 1.0)])
    a, b = tr["segments"]
    assert [w["w"] for w in a["words"]] == ["watch", "this", "clip"]
    assert a["words"][0]["start"] == 1.0 and a["words"][-1]["end"] <= 2.5
    assert b["words"][0]["start"] == 4.0 and b["end"] == 5.0
