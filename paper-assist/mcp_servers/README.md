# MCP servers

This directory holds the MCP bridge the plugin exposes:

- `base.py`: shared server / tool / resource abstractions and input-schema
  generation from tool signatures
- `runner.py`: single entry point for loading and calling a server from a shell
- `stdio.py`: the JSON-RPC stdio server the plugin exposes; it merges both
  servers below into one toolset
- `paperassist/`: pack and Research OS tools (`harness_status`, `pack_scaffold`,
  `pack_plan`, `pack_task`, `pack_import`, `corpus_bind`, `claim_audit`,
  `quality_score`, `research_os`, `improvement_verify`, `journal_lookup`,
  `thesis_lookup`, `design_lookup`)
- `writing/`: writing pack tools (`writing_pack`, `writing_plan`,
  `writing_task`, `writing_import`, `writing_patch`)

Both servers are live, deterministic and model-free.

## Protocol behaviour

- `tools/list` returns a real `inputSchema` per tool, built from the method
  signature (plus declared `payload_keys` for `**payload` tools).
- Unknown arguments are rejected with the list of accepted ones.
- Tool execution failures come back as `isError: true` results; only an
  unknown tool or malformed request is a JSON-RPC error.
- `resources/read` takes per-run parameters in the URI query string, e.g.
  `paperassist://task?workspace=<ws>&kind=review&run_id=<id>&task_id=<task>`.
- Nothing may write to stdout except the JSON-RPC stream; diagnostics go to
  stderr.

## Design principles

- MCP connects external capabilities; it does not own the workflow state machine.
- Every tool is model-free: no provider calls, no credentials, no prompts sent
  to a remote service.
- Write operations must take the workspace lock.
