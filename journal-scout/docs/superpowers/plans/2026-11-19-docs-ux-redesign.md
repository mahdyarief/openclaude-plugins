# Docs Page UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `/docs` page easier to scan, search, and use for MCP setup while retaining its existing single-page structure and content.

**Architecture:** Change only `journal-scout/web/src/routes/docs.tsx`. Add local tool-search and disclosure state, extend the existing sticky section navigation with active-section tracking, and add a copy action to the existing MCP config block. Reuse the existing `Card`, `Chip`, `Button`, `Input`, `PageHeader`, and `LINK_CLASS`; add no dependencies.

**Tech Stack:** React 19, Vite 7, Tailwind 4 utility classes, `lucide-react`.

## Global Constraints

- Do not add routes, dependencies, or backend changes.
- Keep the existing `TOOLS` data and tool descriptions; search only filters presentation.
- Search and Papers are open by default; other tool groups are closed.
- The copy action uses the Clipboard API and reports temporary success.
- Preserve the existing dark visual system, responsive layout, navigation and accurate authentication explanation.
- `web/` has no test runner in `package.json`; do not add a test dependency. Verify with `npm run typecheck`, `npm run build`, and manual browser checks.
- Repository root is `D:/Github/agent-workspace/openclaude-plugins`; the target is under `journal-scout/web/`.

## Existing code map

`journal-scout/web/src/routes/docs.tsx` contains:
- `ToolEntry` with six group values: `Search`, `Papers`, `Graph & metrics`, `Export & archive`, `Review (SLR)`, `Keys`.
- `MCP_URL`, 35 `TOOLS`, and `GROUPS` in display order.
- A `DocsPage` connection section with existing `JOSC_MCP_TOKEN` explanation, `/healthz` link and inline JSON config snippet.
- Existing two-column layout, sticky desktop sidebar and responsive wrapping nav. Links point to `#workflow` and each `#tools-{normalized-group}` section.
- Existing workflow card and one section per tool group, each with heading, count chip and description list.

`web/src/components/ui.tsx` already exports `Input`, `Button`, `Card`, `Chip`, `LINK_CLASS`, and `cn`. `Chip` variants are `default`, `secondary`, and `outline`; do not use `ghost`. `Button` accepts `variant="outline"` and `controlSize="sm"`.

`src/josc/server.py` reads `JOSC_MCP_TOKEN` to enable optional HTTP MCP authentication. Preserve the current statement that clients must send a bearer token when authentication is enabled. The existing `/healthz` route and endpoint remain unchanged.

---

### Task 1: Search and filter tool groups

**Files:**
- Modify: `journal-scout/web/src/routes/docs.tsx`

**Interfaces:**
- Produces `query: string`, `setQuery`, filtered `groups: { group: ToolEntry["group"]; tools: ToolEntry[] }[]`, used by Task 2.

- [ ] **Step 1: Add filtering logic**

Import `useMemo` and `useState` from React and `Input` from the existing UI module. Add a pure helper near `GROUPS`:

```tsx
function filterTools(query: string) {
  const normalized = query.trim().toLocaleLowerCase();
  return GROUPS.map((group) => ({
    group,
    tools: TOOLS.filter((tool) => {
      if (!normalized) return tool.group === group;
      return [tool.name, tool.purpose, tool.group].some((value) =>
        value.toLocaleLowerCase().includes(normalized),
      );
    }),
  })).filter(({ tools }) => tools.length > 0);
}
```

Inside `DocsPage`, define `const [query, setQuery] = useState("");` and `const groups = useMemo(() => filterTools(query), [query]);`.

- [ ] **Step 2: Render search and empty state**

Above the mapped group sections, add:

```tsx
<div className="space-y-3">
  <Input
    aria-label="Cari tool"
    placeholder="Cari tool berdasarkan nama, deskripsi, atau grup…"
    value={query}
    onChange={(event) => setQuery(event.target.value)}
  />
  {groups.length === 0 && (
    <p role="status" className="text-sm text-slate-400">
      Tidak ada tool yang cocok dengan “{query.trim()}”.{" "}
      <button type="button" className={LINK_CLASS} onClick={() => setQuery("")}>
        Hapus pencarian
      </button>
    </p>
  )}
</div>
```

Replace `GROUPS.map((group) => { const tools = TOOLS.filter(...) ... })` with `groups.map(({ group, tools }) => { ... })`. Preserve the current group section IDs and descriptions.

- [ ] **Step 3: Verify search**

Run from `journal-scout/web/`: `npm run typecheck` — expected PASS.
Run `npm run dev` and check `/docs`: query `slr` shows only Review (SLR); a non-matching query displays the empty state and reset; clearing the query restores every group and tool.

- [ ] **Step 4: Commit this task**

```bash
cd D:/Github/agent-workspace/openclaude-plugins
git add journal-scout/web/src/routes/docs.tsx
git commit -m "feat(web): add tool search to Docs page"
```

---

### Task 2: Collapsible tool groups

**Files:**
- Modify: `journal-scout/web/src/routes/docs.tsx`

**Interfaces:**
- Consumes filtered `groups` and `query` from Task 1.
- Produces `openGroups: Record<ToolEntry["group"], boolean>` and `setOpenGroups`, used by navigation in Task 3.

- [ ] **Step 1: Add default disclosure state**

Add a complete default map at module scope:

```tsx
const DEFAULT_OPEN_GROUPS: Record<ToolEntry["group"], boolean> = {
  Search: true,
  Papers: true,
  "Graph & metrics": false,
  "Export & archive": false,
  "Review (SLR)": false,
  Keys: false,
};
```

Inside `DocsPage`, add:

```tsx
const [openGroups, setOpenGroups] = useState(DEFAULT_OPEN_GROUPS);
const searching = query.trim().length > 0;
```

- [ ] **Step 2: Make group headings accessible disclosure buttons**

Import `ChevronDown` from `lucide-react` and `cn` from the existing UI module. In each section, derive:

```tsx
const id = `tools-${group.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
const expanded = searching || openGroups[group];
```

Replace the heading/count row with a disclosure button wrapped in the existing `h2` (preserve document outline), keeping `id={`${id}-title`}` on the `h2` so `aria-labelledby` still works:

```tsx
<h2 id={`${id}-title`} className="w-full">
  <button
    type="button"
    aria-expanded={expanded}
    aria-controls={`${id}-list`}
    onClick={() => setOpenGroups((current) => ({ ...current, [group]: !current[group] }))}
    className="flex w-full items-center justify-between gap-3 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
  >
    <span className="flex min-w-0 items-center gap-2">
      <ChevronDown
        aria-hidden="true"
        className={cn("h-4 w-4 shrink-0 transition-transform", !expanded && "-rotate-90")}
      />
      <span className="text-sm font-semibold text-slate-100">{group}</span>
    </span>
    <Chip variant="secondary">{tools.length} tools</Chip>
  </button>
</h2>
```

Render the existing `dl` only when `expanded`, with `id={`${id}-list`}`. While a query is active, matching groups always stay open; clearing search returns to the user’s disclosure state. Do not alter the section IDs used by current nav anchors.

- [ ] **Step 3: Verify disclosure behavior**

Run `npm run typecheck` — expected PASS.
Manual check: Search and Papers are initially open, other sections closed; buttons toggle groups and expose the right `aria-expanded`; while searching, each matching group opens and non-matching sections are absent; clearing search restores the saved open/closed state.

- [ ] **Step 4: Commit this task**

```bash
git add journal-scout/web/src/routes/docs.tsx
git commit -m "feat(web): make Docs tool groups collapsible"
```

---

### Task 3: Active section navigation and responsive tool navigation

**Files:**
- Modify: `journal-scout/web/src/routes/docs.tsx`

**Interfaces:**
- Consumes existing `GROUPS`, `openGroups`, and `setOpenGroups`.
- Produces `activeId: string` for active navigation styling.

- [ ] **Step 1: Observe existing workflow and group sections**

Import `useEffect` and `useState` (merge React imports). Define refs for the existing `workflow` section and each group section, and add an effect using `IntersectionObserver` with `rootMargin: "-56px 0px -65% 0px"`. The mobile header is `h-14` (56px); use the matching offset. In the callback, set `activeId` to the intersecting target’s `id`; disconnect the observer on cleanup. Register targets through callback refs on the workflow `Card` (which accepts div props) and each existing group `<section>`.

- [ ] **Step 2: Add active state and navigation opening behavior**

On each existing sidebar anchor, preserve its `href`, add `aria-current={activeId === targetId ? "location" : undefined}`, and set active classes using the existing `cn` helper. When a group nav item is clicked, update that group’s state to open before the anchor scrolls. Keep the current six group links; do not replace them with one generic tools link. On workflow link clicks, no group state changes.

Keep the existing responsive nav as-is: on mobile it wraps as chips inside `flex flex-wrap gap-1`, on desktop it becomes a vertical list (`lg:flex-col`). Do not add a new horizontal scroll container. Ensure group sections keep their `scroll-mt-*` offset so anchored scrolls clear the sticky mobile header (56px) on small screens.

- [ ] **Step 3: Verify scrollspy and anchor opening**

Run `npm run typecheck` — expected PASS.
Manual check on desktop and mobile: scroll through workflow and tool groups; current nav link is highlighted; clicking a closed group link opens its section before scrolling to it; keyboard focus is visible; mobile nav remains usable without horizontal page overflow.

- [ ] **Step 4: Commit this task**

```bash
git add journal-scout/web/src/routes/docs.tsx
git commit -m "feat(web): highlight active Docs section in navigation"
```

---

### Task 4: Copy MCP config snippet

**Files:**
- Modify: `journal-scout/web/src/routes/docs.tsx`

**Interfaces:**
- Consumes the existing inline JSON snippet and `Button` component.
- Adds no interfaces used by later tasks.

- [ ] **Step 1: Add copy button state and action**

Import `useRef` and `useEffect` from React, `Check` and `Copy` from `lucide-react`, and `Button` from the existing UI module. Extract the current template string to a module-level `CONFIG_SNIPPET` constant without changing its JSON content, including the `${MCP_URL}` interpolation.

Add `CopySnippetButton({ snippet }: { snippet: string })` before `DocsPage`. It should call `navigator.clipboard.writeText(snippet)` on click, set local `copied` state on success, display `Tersalin` with `Check` for 2 seconds, and clear its timer on unmount. Use an accessible button label and a visible text label; no silent fallback is required if the Clipboard API rejects.

- [ ] **Step 2: Integrate with the existing connection section**

Wrap the current `<pre>` in a `relative` container and position `<CopySnippetButton snippet={CONFIG_SNIPPET} />` in its upper-right corner. Add sufficient top padding to `<pre>` so the button does not overlap the first JSON line. Keep the existing connection explanation, `/healthz` link, and `JOSC_MCP_TOKEN` statement unchanged; do not add a contradictory second auth explanation.

- [ ] **Step 3: Verify clipboard behavior**

Run `npm run typecheck` — expected PASS.
Manual check in a secure browser origin: click the copy button, paste into a text editor to verify exact JSON, and confirm the button changes to `Tersalin` then resets after 2 seconds.

- [ ] **Step 4: Commit this task**

```bash
git add journal-scout/web/src/routes/docs.tsx
git commit -m "feat(web): add copy action to Docs MCP config"
```

---

### Task 5: Final build and visual review

**Files:**
- Modify: `journal-scout/web/src/routes/docs.tsx` only if visual review finds an issue.

- [ ] **Step 1: Run final checks**

```bash
cd D:/Github/agent-workspace/openclaude-plugins/journal-scout/web
npm run typecheck && npm run build
```

Expected: both commands PASS.

- [ ] **Step 2: Review desktop and mobile rendering**

Run `npm run dev` and inspect `/docs` at ~1280px and ~390px widths. Verify no horizontal page overflow, sticky nav behavior, active states, tool filtering, group disclosure, copy feedback, and visual consistency with the existing dark theme and `search.tsx` spacing. Fix issues within `docs.tsx` only.

- [ ] **Step 3: Commit final polish if needed**

```bash
git add journal-scout/web/src/routes/docs.tsx
git commit -m "polish(web): refine Docs page layout"
```
