---
name: component
description: Print Basecoat markup for one component
argument-hint: <component-name>
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/basecoat/components/$ARGUMENTS.md` and output its Anatomy HTML adapted to the user's content. Keep every `class` and `data-*` attribute intact.

If the file does not exist, list the closest filenames from `${CLAUDE_PLUGIN_ROOT}/skills/basecoat/components/` and stop without inventing markup.

Before finishing, apply the matching rules from `${CLAUDE_PLUGIN_ROOT}/skills/basecoat/rules/` and note any state attributes the component requires.
