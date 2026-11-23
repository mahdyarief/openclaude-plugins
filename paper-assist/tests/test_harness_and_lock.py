from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from engine.run_lock import RunLockTimeoutError, run_lock
from paperassist.harness import harness_status

ROOT = Path(__file__).resolve().parents[1]


def _plugin_root(tmp_path: Path, *, plugin_servers: dict, mcp_json: dict | None = None) -> Path:
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "paper-assist", "mcpServers": plugin_servers}), encoding="utf-8"
    )
    if mcp_json is not None:
        (root / ".mcp.json").write_text(json.dumps({"mcpServers": mcp_json}), encoding="utf-8")
    return root


def test_mcp_servers_come_from_plugin_manifest(tmp_path):
    root = _plugin_root(tmp_path, plugin_servers={"paperassist": {"command": "python"}})
    status = harness_status(tmp_path, root=root)
    assert status["checks"]["mcp_manifest"] is True
    assert status["mcp_servers"] == ["paperassist"]


def test_standalone_mcp_json_is_merged(tmp_path):
    root = _plugin_root(
        tmp_path,
        plugin_servers={"paperassist": {}},
        mcp_json={"extra": {}},
    )
    assert harness_status(tmp_path, root=root)["mcp_servers"] == ["extra", "paperassist"]


def test_no_declared_servers_is_reported(tmp_path):
    root = _plugin_root(tmp_path, plugin_servers={})
    status = harness_status(tmp_path, root=root)
    assert status["checks"]["mcp_manifest"] is False
    assert status["mcp_servers"] == []


def test_lock_wait_message_never_touches_stdout(tmp_path, capsys):
    holder = textwrap.dedent(
        f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from engine.run_lock import run_lock
        with run_lock(Path({str(tmp_path)!r}), verbose=False):
            print("held", flush=True)
            time.sleep(10)
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", holder], stdout=subprocess.PIPE, text=True
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "held"
        with pytest.raises(RunLockTimeoutError), run_lock(tmp_path, timeout=1, poll_interval=0.1):
            pass
    finally:
        proc.kill()
        proc.wait()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[LOCK] waiting for run lock" in captured.err
