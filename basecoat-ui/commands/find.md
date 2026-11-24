---
name: find
description: Pick the right Basecoat component for an intent
argument-hint: <intent>
---

Map the intent to a Basecoat component using the index in `${CLAUDE_PLUGIN_ROOT}/skills/basecoat/SKILL.md`. Read the chosen `${CLAUDE_PLUGIN_ROOT}/skills/basecoat/components/<name>.md` before answering.

Reply with the component name, one sentence on why it fits, and its Anatomy HTML. Offer at most two alternatives, one line each, and never invent class names.
