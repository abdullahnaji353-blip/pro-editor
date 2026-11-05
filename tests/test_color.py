import numpy as np

from color import build_lut, correction, look_chain
from conftest import needs_ffmpeg


def read_cube(path):
    rows = [ln.split() for ln in open(path, encoding="utf-8") if ln[:1].isdigit() or ln[:1] == "-"]
    rows = [r for r in rows if len(r) == 3]
    return np.array(rows, float)


def test_identity_lut_without_a_chain(tmp_path):
    p = build_lut("", tmp_path / "id.cube", n=9)
    lut = read_cube(p)
    assert lut.shape == (9**3, 3)
    assert np.allclose(lut[0], 0) and np.allclose(lut[-1], 1)
    assert np.allclose(lut[1], [1 / 8, 0, 0])  # red changes fastest (.cube order)


@needs_ffmpeg
def test_warm_look_lut_warms_neutral_grey(tmp_path):
    lut = read_cube(build_lut(look_chain("warm", 1.0), tmp_path / "w.cube", n=9))
    grey = lut[4 + 4 * 9 + 4 * 81]  # input (0.5, 0.5, 0.5)
    assert grey[0] > grey[2]  # more red than blue


def test_correction_lifts_dark_footage():
    frames = np.full((4, 20, 20, 3), 0.18, np.float32)
    frames[:, :5] = 0.02
    chain, stats = correction(frames, 0.7)
    assert "colorlevels" in chain and stats["gamma"] > 1.0  # in ffmpeg's eq, gamma > 1 brightens mid-tones
