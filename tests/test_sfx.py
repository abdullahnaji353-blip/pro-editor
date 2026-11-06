import numpy as np

from sfx import SR, SYNTHS, measure, openverse_results, peak_time, score_for, spot_events, thin


def _video(n=90, h=128, w=72):
    """Grey frames: a card appears top-half at frame 30, leaves at 60; a hard cut at 80."""
    f = np.full((n, h, w), 90, np.float32)
    f[30:60, 10:50, 8:64] = 230
    f[80:] = 20
    return f, np.abs(np.diff(f, axis=0))


def test_spot_finds_a_card_appearing_and_a_cut_but_skips_it_leaving():
    frames, d = _video()
    ev = spot_events(frames, d)
    kinds = [(round(e["t"] * 30), e["kind"], e["what"]) for e in ev]
    assert (30, "pop", "appears") in kinds
    assert (80, "whoosh", "cut") in kinds
    assert not any(w == "leaves" for *_, w in kinds)
    every = spot_events(frames, d, all_events=True)
    assert any(e["what"] == "leaves" and round(e["t"] * 30) == 60 for e in every)


def test_thin_keeps_the_strongest_and_spaces_them_out():
    ev = [{"t": 1.0, "strength": 0.3}, {"t": 1.4, "strength": 0.9}, {"t": 3.0, "strength": 0.5}]
    assert [e["t"] for e in thin(ev, per_sec=1)] == [1.4, 3.0]


def test_every_synth_peaks_where_it_should():
    for kind, fn in SYNTHS.items():
        s = fn()
        assert s.shape[1] == 2 and np.abs(s).max() <= 1.5, kind
        pk = peak_time(s)
        if kind in ("pop", "click", "tick", "impact", "ding"):
            assert pk < 0.03, (kind, pk)  # hits right away: lands on the frame
        if kind == "riser":
            assert pk > len(s) / SR * 0.8


def test_pick_prefers_a_short_sharp_pop_over_a_long_swell():
    good, _ = score_for(measure(SYNTHS["pop"]()), "pop")
    bad, why = score_for(measure(SYNTHS["riser"]()), "pop")
    assert good > bad and why


def test_openverse_results_keep_credits():
    j = {"results": [{"id": "x", "title": "Pop", "url": "https://a/p.mp3", "license": "cc0", "license_version": "1.0",
                      "creator": "sam", "foreign_landing_url": "https://src", "duration": 400, "filetype": "mp3"},
                     {"id": "y", "title": "no url"}]}  # fmt: skip
    r = openverse_results(j)
    assert len(r) == 1 and r[0]["license"] == "cc0 1.0" and r[0]["creator"] == "sam" and r[0]["duration"] == 0.4


def test_tactile_sounds_and_music_bed(tmp_path):
    import pytest

    sf = pytest.importorskip("soundfile")

    from sfx import music_bed

    for kind in ("paper", "stamp", "tape", "type", "marker"):
        s = SYNTHS[kind]()
        assert s.shape[1] == 2 and 0 < len(s) / SR < 1 and np.abs(s).max() <= 1.0001, kind
    out = music_bed(6.0, tmp_path / "bed.wav")
    x, sr = sf.read(out)
    assert abs(len(x) / sr - 6.0) < 0.01 and 0.3 < np.abs(x).max() <= 0.61
    assert np.abs(x[: int(0.05 * sr)]).max() < 0.05  # fades in
