---
name: basecoat
description: Build HTML UI with Basecoat CSS (shadcn/ui look without React). Covers single-file CDN and Tailwind v4 setup, guardrails, and an on-disk reference of 58 components with variants, FSM states, and anti-patterns. Use for basecoat, basecoat-css, shadcn-like HTML, or component selection.
---

# Basecoat UI

Basecoat is a headless component library: pure CSS classes on semantic HTML with no React runtime. This skill resolves components from local Markdown files instead of an MCP server, so it runs no background process.

## When to Use

- Building or refactoring HTML, Astro, Next.js, SvelteKit, Vite, or HTMX UI in the shadcn aesthetic.
- Any request mentioning `basecoat`, `basecoat-css`, `tailwind v4`, or "shadcn look without React".
- Choosing which component fits an interaction, such as a menu, dialog, data table, or form field.

## Setup

### Single-file HTML via CDN, no build

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/basecoat.cdn.min.css">
<script src="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/js/all.min.js" defer></script>
```

The CDN bundle contains only the Tailwind utilities that Basecoat itself uses. For layout utilities and token utilities such as `bg-primary`, add the Tailwind v4 browser runtime with an `@theme inline` mapping and the border-color reset described in [rules/lean.md](./rules/lean.md). Without the runtime, use semantic tokens such as `var(--primary)`. For a fully offline file, inline both assets, roughly 295KB CSS and 56KB JS.

Style packs replace the filename: `basecoat-{nova|maia|lyra|mira|luma|sera|rhea}.cdn.min.css`. The plain `basecoat.cdn.min.css` is Vega, the default. Dark mode is `class="dark"` on `<html>`.

### Tailwind v4 build

```css
@import "tailwindcss";
@import "basecoat-css/base.css";
@import "basecoat-css/components/button.css";
@import "basecoat-css/styles/vega.css";
```

Read [install.md](./install.md) for Astro, Vite, Next.js, SvelteKit, and HTMX specifics.

## Guardrails

1. Never use DaisyUI classes such as `btn-primary`, `card-body`, or `form-control`.
2. `.card` already renders a 1px ring. Never add `border` to it.
3. Interactive components declare explicit state with `data-state`, plus the `aria-*` attributes named in the component file.
4. Icons use `data-icon="inline-start"` or `data-icon="inline-end"`. Never add sizing classes to icon SVGs.
5. Utility order: Basecoat class, layout, position, alignment, sizing, spacing, typography, background, border, effects, state.
6. No raw colors and no `space-x/y-*`; use `flex gap-*`. Use `size-*` for symmetrical elements.
7. Stay lean: no hand-written component CSS, no class names that collide with Basecoat components, theme only by overriding token values, and no animation libraries. Read [rules/lean.md](./rules/lean.md) before building a full page.

## Component Workflow

1. Identify the intent, not the name. "Confirm a destructive action" maps to alert-dialog, not button.
2. Read `components/<name>.md` before writing markup. Never invent Basecoat class names.
3. Copy the Anatomy HTML, keep its `class` and `data-*` attributes, and replace only the content.
4. Apply the matching rule file: lean pages [rules/lean.md](./rules/lean.md), composition [rules/composition.md](./rules/composition.md), forms [rules/forms.md](./rules/forms.md), icons [rules/icons.md](./rules/icons.md), styling [rules/styling.md](./rules/styling.md).
5. Re-read the Incorrect Anti-Pattern example in the component file before finishing.
