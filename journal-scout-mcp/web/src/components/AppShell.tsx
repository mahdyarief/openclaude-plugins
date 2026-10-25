/*
 * App shell: collapsible left rail on desktop, off-canvas drawer below md.
 * One accent (sky), one radius scale, no decorative gradients.
 */
import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useDialogFocus } from "../lib/useDialogFocus";
import { cn } from "./ui";
import {
  GraphIcon,
  HistoryIcon,
  MetricsIcon,
  PanelToggleIcon,
  SearchIcon,
} from "./icons";

const NAV = [
  { to: "/", label: "Search", Icon: SearchIcon },
  { to: "/graph", label: "Citation graph", Icon: GraphIcon },
  { to: "/metrics", label: "Metrics", Icon: MetricsIcon },
  { to: "/history", label: "History", Icon: HistoryIcon },
] as const;

const COLLAPSE_KEY = "josc.sidebar.collapsed";

const NAV_ITEM_CLASS =
  "flex h-9 shrink-0 items-center gap-2.5 rounded-md text-[13px] no-underline transition-colors";

const NAV_ACTIVE =
  "bg-slate-800/80 text-slate-50 shadow-[inset_2px_0_0_0_var(--color-accent)]";
const NAV_IDLE = "text-slate-400 hover:bg-slate-800/40 hover:text-slate-100";

function BrandMark() {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-sky-400 text-[11px] font-bold tracking-tight text-slate-950">
      JS
    </span>
  );
}

function SidebarBody({
  collapsed,
  onNavigate,
  onToggle,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
  onToggle?: () => void;
}) {
  return (
    <>
      <div
        className={cn(
          "flex h-14 shrink-0 items-center gap-2.5 border-b border-slate-800",
          collapsed ? "justify-center px-0" : "px-3",
        )}
      >
        <Link
          to="/"
          search={{}}
          onClick={onNavigate}
          className="flex items-center gap-2.5 no-underline"
          aria-label="Journal Scout home"
        >
          <BrandMark />
          {!collapsed && (
            <span className="truncate text-[13px] font-semibold tracking-tight text-slate-50">
              Journal Scout
            </span>
          )}
        </Link>
      </div>

      <nav
        aria-label="Main"
        className={cn(
          "scroll-thin flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto py-3",
          collapsed ? "px-2" : "px-2",
        )}
      >
        {NAV.map(({ to, label, Icon }) => (
          <Link
            key={to}
            to={to}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            aria-label={collapsed ? label : undefined}
            activeProps={{ className: NAV_ACTIVE }}
            inactiveProps={{ className: NAV_IDLE }}
            className={cn(NAV_ITEM_CLASS, collapsed ? "justify-center px-0" : "px-2.5")}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </Link>
        ))}
      </nav>

      {onToggle && (
        <div
          className={cn(
            "flex h-12 shrink-0 items-center border-t border-slate-800",
            collapsed ? "justify-center px-0" : "justify-end px-2.5",
          )}
        >
          <button
            type="button"
            onClick={onToggle}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "touch-target flex h-8 items-center justify-center gap-2 rounded-md text-[11px] text-slate-400 transition-colors hover:bg-slate-800/60 hover:text-slate-100",
              collapsed ? "w-8" : "px-2",
            )}
          >
            <PanelToggleIcon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      )}
    </>
  );
}

export function AppShell() {
  // Collapsed by default: only an explicit "0" (the user expanded it before)
  // keeps the rail open, so a fresh session starts with maximum content width.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) !== "0";
    } catch {
      return true;
    }
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const mobileNavRef = useRef<HTMLDivElement | null>(null);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  useDialogFocus(drawerOpen, mobileNavRef, () => setDrawerOpen(false));

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      // Storage can be unavailable in private mode; the rail still toggles for the session.
    }
  }, [collapsed]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [drawerOpen]);

  return (
    <div className="flex min-h-dvh bg-canvas">
      <aside
        aria-label="Primary"
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-slate-800 bg-rail md:flex",
          collapsed ? "w-16" : "w-[232px]",
        )}
      >
        <SidebarBody collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-800 bg-canvas/95 px-4 backdrop-blur-sm md:hidden">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation"
            aria-controls="mobile-nav"
            aria-expanded={drawerOpen}
            className="touch-target flex h-8 w-8 items-center justify-center rounded-md text-slate-300 transition-colors hover:bg-slate-800/60 hover:text-slate-100"
          >
            <PanelToggleIcon className="h-5 w-5" />
          </button>
          <Link to="/" search={{}} className="flex items-center gap-2 no-underline">
            <BrandMark />
            <span className="text-[13px] font-semibold tracking-tight text-slate-50">
              Journal Scout
            </span>
          </Link>
        </header>

        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 pb-10 pt-5 sm:px-6 lg:px-8">
          <Outlet />
        </main>

        <footer className="border-t border-slate-800">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-4 text-[11px] text-slate-400 sm:px-6 lg:px-8">
            Powered by journal-scout-mcp. Scopus, OpenAlex, Semantic Scholar, Crossref,
            arXiv, PubMed, DBLP.
          </div>
        </footer>
      </div>

      <div
        className={cn(
          "fixed inset-0 z-40 md:hidden",
          drawerOpen ? "pointer-events-auto" : "pointer-events-none",
        )}
        aria-hidden={!drawerOpen}
      >
        <div
          onClick={() => setDrawerOpen(false)}
          className={cn(
            "absolute inset-0 bg-black/60 transition-opacity duration-150",
            drawerOpen ? "opacity-100" : "opacity-0",
          )}
        />
        <div
          ref={mobileNavRef}
          id="mobile-nav"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          inert={!drawerOpen}
          className={cn(
            "absolute inset-y-0 left-0 flex w-[248px] flex-col border-r border-slate-800 bg-rail transition-transform duration-200",
            drawerOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <SidebarBody collapsed={false} onNavigate={() => setDrawerOpen(false)} />
        </div>
      </div>
    </div>
  );
}
