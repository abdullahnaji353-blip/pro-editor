import subprocess
import sys
import textwrap

import pytest

from common import concat_line, frame_size, get_model, preview_size, probe, resolve_res
from conftest import SCRIPTS, make_video, needs_ffmpeg


def run_python(code):
    """Run a snippet in a fresh interpreter, so it has a real stderr file descriptor."""
    code = f"import os, sys\nsys.path.insert(0, {str(SCRIPTS)!r})\n" + textwrap.dedent(code)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_sizes():
    assert frame_size("16:9", 2160) == (3840, 2160)
    assert frame_size("9:16", 1440) == (1440, 2560)
    assert preview_size(3840, 2160) == (960, 540)
    assert resolve_res("4k") == 2160 and resolve_res("1080") == 1080


def test_concat_line_escapes_quotes(tmp_path):
    line = concat_line(tmp_path / "kill feed's best.mp4")
    assert line.startswith("file '") and "'\\''" in line


def test_model_override_from_environment(tmp_path, monkeypatch):
    f = tmp_path / "m.task"
    f.write_bytes(b"x" * 20000)
    monkeypatch.setenv("PRO_EDITOR_TEST_MODEL", str(f))
    assert get_model("m.task", "https://example.invalid/m", "PRO_EDITOR_TEST_MODEL") == str(f)


@needs_ffmpeg
def test_probe_reports_upright_size_for_rotated_phone_video(tmp_path):
    src = make_video(tmp_path / "land.mp4", size="320x180")
    rot = tmp_path / "rot.mp4"
    attempts = [
        ["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(src), "-c", "copy", str(rot)],
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c", "copy", "-metadata:s:v:0", "rotate=90", str(rot)],
    ]
    if not any(subprocess.run(c, capture_output=True).returncode == 0 for c in attempts):
        pytest.skip("this ffmpeg can't write rotation metadata")
    info = probe(rot)
    if not info.get("rotation"):
        pytest.skip("this ffmpeg doesn't report rotation")
    assert (info["width"], info["height"]) == (180, 320)
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(rot), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    ).stdout
    assert len(decoded) == 180 * 320 * 3  # matches what ffmpeg actually decodes


def test_quiet_native_logs_hides_library_output():
    r = run_python("""
        from common import quiet_native_logs
        with quiet_native_logs():
            os.write(2, b"I0000 calculator_graph.cc:1] native log line\\n")
        print("done")
    """)
    assert r.stdout.strip() == "done" and r.stderr == ""


def test_quiet_native_logs_keeps_our_own_errors():
    # die() inside the block (e.g. "MediaPipe isn't installed") must still reach the user
    r = run_python("""
        from common import die, quiet_native_logs
        with quiet_native_logs():
            die("Hand tracking needs MediaPipe")
    """)
    assert r.returncode == 1 and "ERROR: Hand tracking needs MediaPipe" in r.stderr


def test_quiet_native_logs_shows_hidden_lines_when_something_fails():
    r = run_python("""
        from common import quiet_native_logs
        with quiet_native_logs():
            os.write(2, b"E0000 model.cc:7] could not open the model file\\n")
            raise RuntimeError("load failed")
    """)
    assert "could not open the model file" in r.stderr and "RuntimeError: load failed" in r.stderr
