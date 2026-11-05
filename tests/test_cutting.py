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
