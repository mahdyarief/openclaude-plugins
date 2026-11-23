from __future__ import annotations

import json
import re
from pathlib import Path

from mcp_servers.stdio import SERVER_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _versions() -> dict[str, str]:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    entry = next(p for p in marketplace["plugins"] if p["name"] == plugin["name"])
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    return {
        "plugin.json": plugin["version"],
        "marketplace.json": entry["version"],
        "stdio.SERVER_VERSION": SERVER_VERSION,
        "pyproject.toml": re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1),
        "README badge": re.search(r"badge/version-v([0-9.]+)-", readme).group(1),
    }


def test_versions_agree_everywhere():
    versions = _versions()
    assert len(set(versions.values())) == 1, versions


def test_changelog_has_no_release_newer_than_the_package():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    released = re.findall(r"^## (\d+\.\d+\.\d+)", changelog, re.M)
    current = tuple(int(x) for x in _versions()["plugin.json"].split("."))
    assert all(tuple(int(x) for x in v.split(".")) <= current for v in released)


def test_marketplace_points_at_this_plugin():
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert marketplace["name"] == "mahdyarief"
    assert [p["name"] for p in marketplace["plugins"]] == ["paper-assist"]
    assert marketplace["plugins"][0]["source"] == "./"


def test_readme_counts_match_the_code():
    from mcp_servers.runner import load_server
    from paperassist.manuscript_quality import DEFAULT_WEIGHTS

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    tools = sum(len(load_server(name).tools()) for name in ("paperassist", "writing"))
    assert f"MCP tools ({tools})" in readme
    assert f"{len(DEFAULT_WEIGHTS)} dimensi" in readme
    stale = [n for n in re.findall(r"\b(\d+) dimensi", readme) if int(n) != len(DEFAULT_WEIGHTS)]
    assert not stale, stale


def test_sources_contain_no_control_characters():
    # A regex written as "\b" in a non-raw string, or pasted through a shell,
    # can land as a literal backspace (0x08); the pattern then silently never
    # matches. This happened twice (claim_ledger "persen", ledger fixtures).
    offenders = []
    for path in [*ROOT.glob("paperassist/**/*.py"), *ROOT.glob("mcp_servers/**/*.py"),
                 *ROOT.glob("engine/*.py"), *ROOT.glob("tests/*.py")]:
        text = path.read_text(encoding="utf-8")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
