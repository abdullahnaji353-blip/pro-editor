import argparse
import math

import numpy as np
import pytest

import avatar_art as art
from avatar import Life, OneEuro, bubble, metrics, plan_frames


def hand(open_=True, dx=0.0, dy=0.0):
    """21 MediaPipe-style landmarks (normalised x, y) for an upright hand."""
    pts = [(0.5, 0.9)]  # wrist
    pts += [(0.40, 0.80), (0.34, 0.72), (0.30, 0.66), (0.27, 0.61)]  # thumb
    for x in (0.42, 0.48, 0.54, 0.60):  # index, middle, ring, pinky
        if open_:
            pts += [(x, 0.62), (x, 0.48), (x, 0.40), (x, 0.33)]
        else:  # curled back toward the palm
            pts += [(x, 0.62), (x, 0.52), (x, 0.58), (x, 0.66)]
    return [[x + dx, y + dy] for x, y in pts]


def args(**kw):
    base = dict(
        anchor="palm", hand="auto", size=1.0, start=None, end=None, summon=False, tilt=0.5, boop=True, pos=[0.5, 0.8]
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_finger_states():
    W, H = 1080, 1920
    m_open, m_fist = metrics(hand(True), W, H), metrics(hand(False), W, H)
    assert m_open["is_open"] and not m_open["is_fist"] and m_open["n_ext"] == 4
    assert m_fist["is_fist"] and not m_fist["is_open"]
    # the avatar stands between the wrist and the knuckles
    assert 0.62 * H < m_open["c"][1] < 0.9 * H


def test_one_euro_smooths_jitter_but_follows_moves():
    rng = np.random.default_rng(0)
    f = OneEuro(1.0, 0.004)
    noisy = 500 + rng.normal(0, 4, 120)
    out = np.array([f(float(v), 1 / 30) for v in noisy])
    assert out[30:].std() < noisy[30:].std() * 0.5
    g = OneEuro(1.0, 0.004)
    step = [100.0] * 30 + [400.0] * 30
    res = [g(v, 1 / 30) for v in step]
    assert abs(res[-1] - 400.0) < 10  # catches up within a second


def test_fixed_anchor_window_and_exit():
    fps = 10
    plans = plan_frames(None, 40, 1280, 720, fps, args(anchor="fixed", start=1.0, end=2.0))
    shown = [i for i, p in enumerate(plans) if p["shown"]]
    assert shown[0] == 10 and shown[-1] == 20
    assert plans[15]["appear"] == 1.0
    assert plans[30]["exit"] is not None and not plans[30]["shown"]


def test_tracking_holds_short_gaps_and_hides_after_long_ones():
    fps, n = 30, 120
    frames = []
    for i in range(n):
        lost = 30 <= i < 36 or 60 <= i < 90  # 0.2 s gap, then a 1 s gap
        frames.append([] if lost else [{"lm": hand(True, dx=0.001 * i), "s": 0.9}])
    plans = plan_frames({"frames": frames}, n, 1080, 1920, fps, args())
    assert all(plans[i]["shown"] for i in range(30, 36))  # held through the short drop
    assert not plans[85]["shown"]  # faded out during the long one
    assert plans[100]["shown"] and plans[100]["appear"] > 2.9


def test_avatar_follows_the_palm():
    fps, n = 30, 60
    frames = [[{"lm": hand(True, dx=0.2 * i / n), "s": 0.9}] for i in range(n)]
    plans = plan_frames({"frames": frames}, n, 1000, 1000, fps, args())
    xs = [p["x"] for p in plans]
    assert xs[-1] > xs[0] + 100  # moved right with the hand
    assert all(b >= a - 1e-6 for a, b in zip(xs, xs[1:]))  # smoothly, no jumping back


def test_summon_open_and_fist():
    fps = 30
    seq = [True] * 30 + [False] * 30 + [True] * 30
    frames = [[{"lm": hand(o), "s": 0.9}] for o in seq]
    plans = plan_frames({"frames": frames}, len(seq), 1000, 1000, fps, args(summon=True))
    assert plans[20]["shown"] and not plans[50]["shown"] and plans[85]["shown"]


def test_poke_with_the_other_hand():
    fps, n, W, H = 30, 60, 1000, 1000
    base = hand(True)
    still = plan_frames({"frames": [[{"lm": base, "s": 0.9}]] * n}, n, W, H, fps, args())
    p = still[40]
    head = [p["x"] / W, (p["y"] - 0.6 * p["h"]) / H]  # where the avatar's head is
    frames = []
    for i in range(n):
        hands = [{"lm": base, "s": 0.9}]
        if i >= 30:  # the other hand arrives with its index fingertip on the head
            other = hand(True, dx=0.35)
            other[8] = head
            hands.append({"lm": other, "s": 0.9})
        frames.append(hands)
    plans = plan_frames({"frames": frames}, n, W, H, fps, args())
    assert all(q["boop"] < 0 for q in plans[:30])
    assert any(q["boop"] >= 1.0 for q in plans[30:])


def test_life_blinks_are_brief_and_repeatable():
    a, b = Life(seed=7), Life(seed=7)
    ts = np.arange(0, 30, 1 / 30)
    blinks_a = [a.blink(t) for t in ts]
    assert blinks_a == [b.blink(t) for t in ts]
    closed = sum(1 for v in blinks_a if v > 0)
    assert 0 < closed < len(ts) * 0.1


@pytest.mark.parametrize(
    "state", [{}, {"expr": "happy", "wave": 1}, {"mouth": 0.8}, {"expr": "heart"}, {"expr": "squeeze", "squash": 0.8}]
)
def test_render_is_premultiplied_and_has_feet_at_the_bottom(state):
    img = art.render(state, 200)
    a = img[..., 3]
    assert img.shape[2] == 4 and 0.0 <= a.min() and a.max() <= 1.0
    rows = np.nonzero(a.max(axis=1) > 0.5)[0]
    fx, fy = art.anchor_px(200)
    assert abs(rows.max() - fy) < 6  # feet land on the anchor
    assert math.isclose(fx, img.shape[1] / 2)


def test_hex_colors():
    assert art.hex_rgb("#FF8000", None) == (1.0, 128 / 255, 0.0)
    assert art.hex_rgb("nope", (1, 2, 3)) == (1, 2, 3)


def test_speech_bubble_reads_left_to_right_on_both_sides():
    left, right = bubble("Hi there", 400, "left"), bubble("Hi there", 400, "right")
    assert left.shape == right.shape and left.shape[2] == 4
    # same text block, tail on different sides: the text area must not be mirrored
    h = left.shape[0] // 2
    assert np.allclose(left[:h], right[:h], atol=1e-6)
