---
title: Paper-mode results are author-owned; prose may only restate numbers from the protected block
author: Mahdy
date: 2026-11-20
branch: main
cost: { minutes: 34, tokens: 232504 }
id: l-41fa9e3f
scope: repo
status: active
src: agent
touches:
  - ".claude-plugin/marketplace.json"
  - ".claude-plugin/plugin.json"
  - CHANGELOG.md
  - README.md
  - engine/run_lock.py
  - mcp_servers/README.md
  - mcp_servers/base.py
  - mcp_servers/paperassist/server.py
  - mcp_servers/stdio.py
  - mcp_servers/writing/server.py
---

## Decided
- In paper mode, Experimental Setup and Results live inside the protected experiment block and are written by the authors. The writing pack skips their tasks by default, and adds Discussion and Limitations instead.
- The import gate accepts a result-like sentence outside the protected block only when every number in it already appears inside the block, or when it has no number and points at a table/figure label defined there. Years and \cite/\ref arguments are ignored when comparing numbers.
- Declarations (interests, funding, data, CRediT, AI use) are a second protected, author-owned block. The gate rejects chat-assistant residue in prose, because AI-use disclosure is the authors' statement, not harness prose.

## Tried and ruled out
- Leaving Results tasks on by default: the gate refused every Results draft (heading and percentages), so the task could never pass.
- Relaxing the gate to allow any number with a citation: it would let invented results through as long as something was cited.

## Watch out
- Source files once held literal backspace characters where a regex needed \b (claim_ledger "persen" pattern), so the regex silently never matched. test_sources_contain_no_control_characters guards this; write regexes with an editor, not through shell heredocs.

In the code: paperassist/writing.py (_unsupported_result_sentences, _ASSISTANT_RESIDUE), paperassist/writing_pack.py (DEFAULT_SECTIONS, _declarations_block, skip_experimental default), tests/test_paper_mode.py, tests/test_release_consistency.py
