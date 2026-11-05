from chapters import out_time, ts
from vlog_cut import merge, read_script_ids, retake_flags, subtract


def test_subtract_and_merge():
    assert subtract([(0.0, 10.0)], (2.0, 3.0)) == [(0.0, 2.0), (3.0, 10.0)]
    assert subtract([(0.0, 2.0)], (5.0, 6.0)) == [(0.0, 2.0)]
    assert merge([(0.0, 1.0), (1.05, 2.0), (3.0, 4.0)], 0.1) == [(0.0, 2.0), (3.0, 4.0)]


def test_script_lines_kept_and_deleted(tmp_path):
    p = tmp_path / "script.txt"
    p.write_text("# header\n[0001] 00:00.0 hello\n# [0002] 00:01.0 cut me\n[0003] 00:02.0 keep\n", encoding="utf-8")
    assert read_script_ids(p) == {1, 3}


def test_retake_flagged_when_the_next_line_repeats_it():
    segs = [
        {"id": 1, "words": [{"w": w} for w in "so today we are testing the new car".split()]},
        {"id": 2, "words": [{"w": w} for w in "so today we are testing the brand new car".split()]},
        {"id": 3, "words": [{"w": w} for w in "it is fast".split()]},
    ]
    assert retake_flags(segs) == {1: 2}


def test_chapter_times_follow_the_cut():
    mapping = {
        "ranges": [
            {"src_start": 0.0, "src_end": 5.0, "out_start": 0.0},
            {"src_start": 8.0, "src_end": 12.0, "out_start": 5.0},
        ]
    }
    assert out_time(9.0, mapping) == 6.0
    assert out_time(6.0, mapping) == 5.0  # cut out: jumps to the next kept part
    assert out_time(20.0, mapping) is None
    assert ts(75) == "1:15" and ts(3725) == "1:02:05"


def test_montage_lands_the_action_on_the_cut():
    from build_montage import take_at_peak

    clip = {"start": 0.0, "end": 10.0, "cursor": 0.0, "peak": 6.0}
    start, length = take_at_peak(clip, 1.0)
    assert start < 6.0 < start + 0.2 and length == 1.0  # the peak shows right after the cut
    assert clip["peak_used"] and clip["cursor"] == start + length


def test_montage_cuts_follow_the_song():
    from build_montage import cut_points

    beats = [round(0.5 * i, 3) for i in range(1, 97)]  # 48 s at 120 bpm
    strength = [0.2] * 32 + [0.9] * 64  # quiet intro, then loud
    data = {"beats": beats, "beat_strength": strength, "downbeats": []}
    pts = cut_points(data, 48.0, 2, True, 1.0, drops=[16.0])
    gaps = lambda a, b: [y - x for x, y in zip(pts, pts[1:]) if a <= x < b]  # noqa: E731
    assert min(gaps(1, 14)) >= 2.0  # quiet: every 4 beats
    assert max(gaps(16, 19.5)) <= 0.5  # just after the drop: every beat
    assert set(gaps(24, 46)) == {1.0}  # loud: the recipe's every 2 beats
    flat = cut_points(data, 48.0, 2, True, 1.0, drops=[16.0], adaptive=False)
    assert max(y - x for x, y in zip(flat[1:], flat[2:-1])) <= 1.0  # old behaviour: same spacing throughout


def test_render_check_hears_a_click_at_a_cut():
    import numpy as np

    from check_render import pop_at

    sr = 8000
    t = np.arange(sr * 2) / sr
    x = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    assert pop_at(x, sr, 1.0) < 6  # smooth audio: no click
    x[sr : sr + 8] = 0.9  # a hard edge, like an unfaded cut
    assert pop_at(x, sr, 1.0) > 12
