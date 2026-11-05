"""The Claude app's plugin checks, run on every push (they're stricter than `claude plugin validate`)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def descriptions():
    for f in ("plugin.json", "marketplace.json"):
        d = json.loads((ROOT / ".claude-plugin" / f).read_text())
        if d.get("description"):
            yield f, d["description"]
        for p in d.get("plugins", []):
            if p.get("description"):
                yield f"{f}: {p.get('name')}", p["description"]


def test_plugin_descriptions_fit():
    for where, text in descriptions():
        assert len(text) <= 500, f"{where}: {len(text)} characters (max 500)"


def test_versions_match():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert {p["version"] for p in market["plugins"]} == {plugin["version"]}


def test_skill_frontmatter():
    for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
        front = skill.read_text().split("---")[1]
        name = re.search(r"^name:\s*(\S+)", front, re.M).group(1)
        desc = " ".join(front.split("description:", 1)[1].split("metadata:")[0].replace(">", "", 1).split())
        assert name == skill.parent.name, skill
        assert len(desc) <= 1024, f"{skill}: description is {len(desc)} characters (max 1024)"
        assert not re.search(r"<[^>]*>", desc), f"{skill}: description can't contain XML-like tags"
