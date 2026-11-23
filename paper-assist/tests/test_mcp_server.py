from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mcp_servers.runner import load_server
from mcp_servers.stdio import SERVER_VERSION

ROOT = Path(__file__).resolve().parents[1]
STDIO = ROOT / "mcp_servers" / "stdio.py"

PAPER = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "Intro sentence.\n"
    "% PAPERASSIST-PROTECTED-EXPERIMENT-START\n"
    "Accuracy is 91.2\\%.\n"
    "% PAPERASSIST-PROTECTED-EXPERIMENT-END\n"
    "\\end{document}\n"
)


@pytest.fixture(scope="module")
def servers():
    return [load_server("paperassist"), load_server("writing")]


def _rpc(*requests: dict) -> list[dict]:
    lines = "".join(json.dumps(request) + "\n" for request in requests)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(STDIO)],
        input=lines,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=True,
    )
    # Every stdout line must be JSON-RPC; anything else corrupts the stream.
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_every_tool_publishes_a_real_schema(servers):
    for server in servers:
        for spec in server.tools():
            schema = server.tool_schema(spec)
            assert schema["type"] == "object"
            assert schema["additionalProperties"] is False
            assert schema["properties"], spec.name
            for name in schema.get("required", []):
                assert name in schema["properties"]


def test_schema_carries_types_defaults_and_payload_keys(servers):
    paperassist, writing = servers
    by_name = {spec.name: spec for spec in paperassist.tools()}
    quality = paperassist.tool_schema(by_name["quality_score"])
    assert quality["required"] == ["workspace", "target_path"]
    assert quality["properties"]["depth_target"] == {"type": "integer", "default": 500}
    assert quality["properties"]["allow_em_dash"]["type"] == "boolean"
    scaffold = paperassist.tool_schema(by_name["pack_scaffold"])
    assert {"topic", "venue", "num_ideas"} <= set(scaffold["properties"])
    research = paperassist.tool_schema(by_name["research_os"])
    assert {"records_path", "source_path", "ris_paths"} <= set(research["properties"])
    pack = writing.tool_schema(next(s for s in writing.tools() if s.name == "writing_pack"))
    assert {"topic", "document_kind", "thesis_profile"} <= set(pack["properties"])


@pytest.mark.parametrize(
    ("server_index", "tool", "arguments"),
    [
        (0, "pack_scaffold", {"kind": "ideation", "topik": "x"}),
        (0, "research_os", {"target": "main.tex"}),
        (1, "writing_pack", {"titel": "x"}),
    ],
)
def test_unknown_payload_keys_are_rejected(servers, tmp_path, server_index, tool, arguments):
    with pytest.raises(ValueError, match="unknown argument"):
        servers[server_index].call_tool(tool, workspace=str(tmp_path), **arguments)


def test_only_declared_tools_are_callable(servers):
    for name in ("read_resource", "capabilities", "tools", "workspace_lock"):
        with pytest.raises(ValueError, match="Unsupported tool"):
            servers[0].call_tool(name)


def test_pack_task_refuses_path_traversal(servers, tmp_path):
    with pytest.raises(Exception, match="invalid task_id"):
        servers[0].call_tool(
            "pack_task",
            workspace=str(tmp_path),
            kind="ideation",
            run_id="r1",
            task_id="../../../secret",
        )
    with pytest.raises(Exception, match="invalid task_id"):
        servers[1].call_tool(
            "writing_task", workspace=str(tmp_path), run_id="r1", task_id="..\\x"
        )


def test_writing_patch_replacement_path_cannot_escape(servers, tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "main.tex").write_text(PAPER, encoding="utf-8", newline="")
    (tmp_path / "outside.tex").write_text("Leaked sentence.", encoding="utf-8")
    sha = hashlib.sha256(PAPER.encode("utf-8")).hexdigest()
    with pytest.raises(Exception, match="escapes|unsafe"):
        servers[1].call_tool(
            "writing_patch",
            workspace=str(workspace),
            run_id="p1",
            target="main.tex",
            anchor="Intro sentence.",
            replacement_path="../outside.tex",
            source_sha256=sha,
        )
    assert (workspace / "main.tex").read_text(encoding="utf-8") == PAPER


def test_stdio_protocol_round_trip(tmp_path):
    responses = _rpc(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "quality_score",
                "arguments": {"workspace": str(tmp_path), "target_path": "missing.tex"},
            },
        },
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}},
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "paperassist://journal-profiles?scope=indonesia"},
        },
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "harness_status", "arguments": {"workspace": str(tmp_path)}},
        },
    )
    by_id = {response.get("id"): response for response in responses}
    assert by_id[1]["result"]["serverInfo"]["version"] == SERVER_VERSION
    tools = by_id[2]["result"]["tools"]
    assert len(tools) == 18
    assert all(tool["inputSchema"]["properties"] for tool in tools)
    # Execution failure is a tool result the harness can read, not a protocol error.
    assert by_id[3]["result"]["isError"] is True
    assert "missing.tex" in by_id[3]["result"]["content"][0]["text"]
    assert by_id[4]["error"]["code"] == -32602
    contents = by_id[5]["result"]["contents"][0]
    assert json.loads(contents["text"])["result"]["scope"] == "indonesia"
    status = json.loads(by_id[6]["result"]["content"][0]["text"])
    assert "paperassist" in status["harness"]["mcp_servers"]


def test_resource_read_with_query_parameters(tmp_path):
    responses = _rpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": f"paperassist://pack?workspace={tmp_path}&kind=review&run_id=x"},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/read",
            "params": {"uri": "paperassist://nope"},
        },
    )
    by_id = {response["id"]: response for response in responses}
    # A missing pack is reported, proving the parameters reached the server.
    assert "review pack not found" in by_id[1]["error"]["message"]
    assert by_id[2]["error"]["code"] == -32602
