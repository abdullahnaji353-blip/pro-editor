from captions import build, chunk, pick_emphasis


def words(text, start=0.0):
    out, t = [], start
    for w in text.split():
        out.append({"w": w, "start": round(t, 3), "end": round(t + 0.3, 3)})
        t += 0.36
    return out


def test_chunks_respect_size_and_sentence_ends():
    ws = words("one two three four. five six")
    chs = chunk(ws, 3, 30)
    assert [len(c) for c in chs] == [3, 1, 2]


def test_emphasis_prefers_numbers_and_stays_rare():
    ws = words("we were down 2 to 0 then I won $50 on the wager and it was a crazy comeback")
    chs = chunk(ws, 3, 30)
    em = pick_emphasis(ws, chs, "auto")
    picked = {ws[i]["w"] for i in em}
    assert "$50" in picked
    assert len(em) <= len(chs) // 3 + 1
    for ch in chs:  # at most one per group
        ids = {id(w) for w in ch}
        assert sum(1 for i in em if id(ws[i]) in ids) <= 1


def test_emphasis_uses_loudness_and_keywords():
    ws = words("then my teammate said just go for it")
    chs = chunk(ws, 3, 30)
    loud = [0.0] * len(ws)
    loud[1] = 9.0  # "my" is a stopword: loudness alone can't pick it
    loud[2] = 9.0  # "teammate" said much louder
    em = pick_emphasis(ws, chs, "auto", loud)
    assert ws[2]["w"] in {ws[i]["w"] for i in em}
    em_kw = pick_emphasis(ws, chs, "said,go")
    assert {ws[i]["w"] for i in em_kw} >= {"said"}


def test_build_marks_emphasis_and_none_turns_it_off():
    ws = words("I hit a 1v4 clutch for $50")
    ass, srt, n, n_em = build(ws, 1080, 1920, emphasis="auto")
    assert n_em >= 1 and "fscx" in ass and "Dialogue:" in ass
    ass0, _, _, n0 = build(ws, 1080, 1920, emphasis="none")
    assert n0 == 0
    assert srt.startswith("1\n00:00:00,000 --> ")


def test_emphasis_with_few_candidate_words():
    # many caption groups, only one with a word worth colouring: used to crash (IndexError)
    from captions import pick_emphasis

    words = [{"w": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate("so the and it was a 1v4".split())]
    chunks = [[w] for w in words]
    out = pick_emphasis(words, chunks, "auto")
    assert out == {6}
