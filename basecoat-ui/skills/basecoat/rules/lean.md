# Lean HTML with Basecoat: Do and Don't

Goal: a page built entirely from Basecoat components, Tailwind utilities, and theme tokens, with
no hand-written component CSS and no heavy libraries. Every rule below comes from a real
single-file HTML dashboard and the failure it prevents.

## 1. What a lean page is made of

| Layer | Use | Never |
|---|---|---|
| Components | Basecoat classes (`.card`, `.table`, `.item`, `.badge`, `.btn`, `.sidebar`, `.dialog`, `.sheet`, `.accordion`, `.progress`, `.breadcrumb`, `.alert`) | A custom `.panel`, `.metric`, `.bubble`, `.tabs-bar` stylesheet |
| Layout | Tailwind v4 utilities (`grid`, `flex`, `gap-*`, `min-w-0`, responsive prefixes) | Your own grid classes or media queries |
| Color | Overrides of Basecoat token values (`--primary`, `--chart-1..5`) | Raw hex, new color classes, `!important` |
| Charts | ApexCharts reading Basecoat tokens (see section 7) | Hand-written SVG chart helpers, Chart.js plus a theme plugin |
| Effects | Basecoat built-ins, Tailwind transitions, View Transitions API | GSAP, Framer Motion, AOS, Lottie |

Do keep exactly two `<style>` blocks at most: one plain block for token values, and one
`type="text/tailwindcss"` block for the `@theme inline` mapping. If you are writing selectors
for components in either block, stop: the markup is wrong, not the CSS.

## 2. CDN setup that actually works

```html
<script>/* before any CSS: avoids a flash of the wrong theme */
  try { var m = localStorage.getItem("themeMode");
    document.documentElement.classList.toggle("dark", m === "dark" || (!m && matchMedia("(prefers-color-scheme: dark)").matches)); } catch (e) {}
</script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/basecoat.cdn.min.css">
<style>/* token values only, see section 4 */</style>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4.1.11/dist/index.global.js"></script>
<style type="text/tailwindcss">
  @custom-variant dark (&:where(.dark, .dark *));
  /* Tailwind's preflight resets border-color to currentColor and beats Basecoat's base layer:
     tables and dividers turn black (light) or white (dark). Restore the token. */
  @layer base { *, ::after, ::before, ::backdrop { border-color: var(--border); } }
  @theme inline {
    --color-background: var(--background); --color-foreground: var(--foreground);
    --color-card: var(--card); --color-card-foreground: var(--card-foreground);
    --color-primary: var(--primary); --color-primary-foreground: var(--primary-foreground);
    --color-muted: var(--muted); --color-muted-foreground: var(--muted-foreground);
    --color-accent: var(--accent); --color-destructive: var(--destructive);
    --color-border: var(--border); --color-input: var(--input); --color-ring: var(--ring);
    --color-chart-1: var(--chart-1); /* … through --color-chart-5 */
  }
</style>
<script src="https://cdn.jsdelivr.net/npm/basecoat-css@1.3.0/dist/js/all.min.js" defer></script>
```

- Do add the Tailwind browser runtime only when the page needs layout utilities (`grid-cols-*`,
  `xl:col-span-2`). The Basecoat CDN bundle ships only the utilities Basecoat itself uses.
- Don't skip the `@theme inline` mapping: without it `bg-card`, `text-muted-foreground`, and
  `bg-chart-2/10` generate nothing.
- Don't load Basecoat CSS twice or mix a style pack with the default bundle.

## 3. Use the real Basecoat 1.3 markup

Short component docs can lag behind the CSS. When in doubt, the shipped CSS selectors win.

| Component | Structure the CSS expects | Trap |
|---|---|---|
| Sidebar | `aside.sidebar[data-side=left] > nav > header + section > div[role=group] > h3 + ul > li > a` (active link: `aria-current="page"`); the element right after the aside is the content and gets the left margin | Toggle with the element's own `sidebar.toggle()`. Leave `data-breakpoint` at the default 768 so the JS matches the CSS `md` breakpoint |
| Card | `.card > header + section + footer` | Never add `border`; the ring is built in. `header` is a grid, so add `flex justify-between` when a badge sits beside the title |
| Item | `.item[data-variant=outline] > figure? + section(h3, p) + aside?` | `.item p` is clamped to 2 lines: add `line-clamp-none` for text that must be read in full. On phones, put the action button inside `section`, not in `aside` |
| Table | `div.table-container > table.table` | `td` is `white-space: nowrap`: add `whitespace-normal min-w-48` to long text columns |
| Progress | `div.progress[role=progressbar] > span[style="width:N%"]` | Recolor with `*:bg-destructive`, not a new class |
| Dialog / Sheet | `dialog.dialog > div > header + section + footer + button[aria-label=Close]`; `dialog.sheet[data-side=right] > div` | Open with `showModal()`, close on backdrop click with `e.target === dialog` |
| Badge | `data-variant` = `primary`, `secondary`, `outline`, `destructive`, `ghost`, `link` | There is no success or warning variant (see section 4) |

- Don't reuse Basecoat class names for your own markup. `.bubble`, `.alert`, `.item`, `.field`,
  and `.tabs` are all Basecoat components; a chat `.bubble` inherits a primary-colored first child.

## 4. Color and theming through tokens only

- Do theme by overriding token values in a plain, unlayered `<style>` after the Basecoat CSS.
  This is the official customization path, the same as shadcn themes.
- Do redefine every token you override in `:root` again inside `.dark`. An unlayered `:root`
  beats Basecoat's layered `.dark`, so a light `--border` leaks into dark mode and every outline
  turns bright.
- Do give status colors a fixed meaning in the chart tokens. One working map is
  `--chart-1` brand, `--chart-2` ok (green), `--chart-3` warning (amber), `--chart-4` comparison,
  `--chart-5` dark accent, with `--destructive` as the breach color.
- Do build status badges from a variant plus token utilities plus an icon, for example
  `class="badge border-chart-2/50 bg-chart-2/10 *:text-chart-2" data-variant="outline"`
  with a check icon. Tint only the icon (`*:`) so the label keeps full contrast.
- Don't rely on color alone: pair every status with an icon and a text label.
- Healthcare or clinical apps: a calm blue primary, cool near-white surfaces, and the standard
  green, amber, and red for status read as trustworthy and familiar.

## 5. Mobile-first without custom CSS

- Do put `min-w-0` on every grid and flex child that holds a table, chart, or long text.
  Without it, a flex item refuses to shrink and the whole page scrolls sideways.
- Do use the sidebar for navigation with more than about five sections. A horizontal tab bar
  with ten tabs overflows on phones.
- Do move secondary panels, such as a chat or a filter rail, into a `dialog.sheet` below `xl`
  and keep them as a column at `xl` and up. Move the same DOM node; don't render it twice.
- Do let wide data scroll inside its card: tables in `.table-container`, heatmaps in
  `overflow-x-auto` with a `min-w-xl` inner wrapper.
- Do test at 390 px and check `document.documentElement.scrollWidth === clientWidth`.
- Do style scrollbars with Basecoat's built-in classes, never with your own
  `::-webkit-scrollbar` CSS: `.scrollbar` on `<html>` for the page, and
  `.scrollbar .scrollbar-thin` on every inner scroll area (`.table-container`,
  `overflow-x-auto` heatmap wrappers, chat logs, sheet bodies). The colors come from
  `--scrollbar-thumb` and `--scrollbar-track`, so they follow light and dark mode.

## 6. Effects that cost nothing

1. Basecoat built-ins: dialog and sheet enter and exit, accordion height animation through
   `::details-content`, the sidebar slide. They are already on; don't re-implement them.
2. Tailwind utilities on clickable cards:
   `transition hover:-translate-y-0.5 hover:shadow-md motion-reduce:transition-none motion-reduce:hover:translate-y-0`.
   Use `animate-pulse` for loading text and `animate-spin` for spinners.
3. View Transitions API for view switches, 0 KB:
   ```js
   const reduce = matchMedia("(prefers-reduced-motion: reduce)");
   function render(animate = true) {
     if (animate && document.startViewTransition && !reduce.matches) document.startViewTransition(renderNow);
     else renderNow();
   }
   ```
   Skip the transition on the first render and on theme changes.
4. Chart entry animation: ApexCharts `animations: { enabled: !reduce.matches, speed: 450,
   animateGradually: { enabled: false } }`.
5. Only if you need staggered enter animations: `tw-animate-css` (about 4 KB, CSS only, the
   library shadcn uses). Nothing heavier.

## 7. Charts that follow the theme

- Do resolve tokens to `rgb()` before passing them to ApexCharts. CSS variable strings break its
  opacity and gradient math, and it cannot parse `oklch()`:
  ```js
  const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  function col(token, a = 1) {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return a === 1 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${a})`;
  }
  ```
- Do destroy and re-create charts on `basecoat:themechange` so the new token values are read.
- Do give charts a numeric `chart.height` in pixels. The Tailwind browser runtime generates
  classes asynchronously, so `h-64` may not exist yet when the chart measures its container.
- Do set heatmap data labels to a color that contrasts with the cells in both themes (dark text
  on amber), and set axis and legend text to `--muted-foreground`.
- Don't mix hand-drawn SVG charts with ApexCharts on the same page.

## 8. Theme switching

- Do use the built-in API `window.basecoat.theme.toggle()`. It writes `localStorage.themeMode`
  and dispatches `basecoat:themechange`. Match that key in the head bootstrap script.
- Do swap sun and moon icons with `dark:hidden` and `hidden dark:block`, not with JavaScript.

## Self-check before finishing

- [ ] No stylesheet besides Basecoat, the token block, and the `@theme inline` block.
- [ ] No class name that collides with a Basecoat component.
- [ ] Every token overridden in `:root` is redefined in `.dark`.
- [ ] Border reset to `var(--border)` is present when the Tailwind runtime is loaded.
- [ ] No horizontal page scroll at 390 px; wide tables and heatmaps scroll inside their card.
- [ ] Every scroll area carries `.scrollbar` (plus `.scrollbar-thin` inside the page).
- [ ] Statuses use variant plus icon plus label, not color alone.
- [ ] Charts read tokens through `col()` and re-render on `basecoat:themechange`.
- [ ] All motion is disabled under `prefers-reduced-motion`.
