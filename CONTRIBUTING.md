# Contributing

Bug reports and ideas are welcome: open an issue with what you asked Claude to do and what happened.

## How the plugin is put together

```
skills/<name>/SKILL.md     instructions Claude follows for each command (/montage, /talk, ...)
scripts/*.py               the tools those instructions run (plain Python + ffmpeg, no server)
docs/MANUAL.md             the user manual
tests/                     unit tests for the logic that doesn't need real footage
```

Skills decide *what* to do and talk to the user. Scripts do the work and print plain-language
results that Claude can read back. Every script runs on its own from a terminal and has `--help`.

## Development setup

```
python -m pip install -r requirements-dev.txt   # plus ffmpeg on PATH
ruff check scripts tests                        # lint
pytest                                          # unit tests, a few seconds
python scripts/selftest.py                      # end-to-end: runs every tool on generated clips
```

To try your local copy as a plugin in Claude Code: `claude --plugin-dir .`

## Guidelines

- Keep scripts dependency-light. Anything beyond numpy/librosa/soundfile must be optional, and the
  script should say how to install it when it's missing.
- Never modify the user's original files. Write new files next to them.
- Previews first: anything that renders should have a fast `--preview` mode.
- Messages are for creators, not engineers: say what happened and what to do about it.
- Add a unit test for new logic, and run the self-test before opening a pull request.
