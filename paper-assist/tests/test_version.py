"""Every place that states the release version states the same one."""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

import paperassist
from mcp_servers.stdio import SERVER_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_versions_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    listed = next(p for p in market["plugins"] if p["name"] == "paper-assist")
    versions = {
        "pyproject": project["version"],
        "plugin.json": plugin["version"],
        "marketplace.json": listed["version"],
        "__version__": paperassist.__version__,
        "SERVER_VERSION": SERVER_VERSION,
    }
    assert len(set(versions.values())) == 1, versions


def test_changelog_heads_with_the_current_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## (\S+)", changelog, re.MULTILINE)
    assert first and first.group(1) in (paperassist.__version__, "Unreleased")
