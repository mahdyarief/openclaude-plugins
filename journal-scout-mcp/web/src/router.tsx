import {
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
} from "@tanstack/react-router";
import { GraphPage } from "./routes/graph";
import { HistoryPage } from "./routes/history";
import { MetricsPage } from "./routes/metrics";
import { SearchPage } from "./routes/search";

const NAV = [
  { to: "/", label: "Search" },
  { to: "/graph", label: "Citation graph" },
  { to: "/metrics", label: "Metrics" },
  { to: "/history", label: "History" },
] as const;

function RootLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-slate-800/70 bg-[#070b14]/85 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-[1180px] flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8 lg:px-12">
          <Link to="/" search={{}} className="group flex flex-col no-underline">
            <span className="text-lg font-semibold tracking-tight text-slate-50">
              Journal <span className="text-sky-400">Scout</span>
            </span>
            <span className="text-[11px] leading-tight text-slate-500">
              literature search · citation networks · bibliometrics
            </span>
          </Link>

          <nav className="scroll-thin -mx-1 flex max-w-full gap-1 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 p-1">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                activeProps={{ className: "bg-slate-800 text-slate-50" }}
                inactiveProps={{ className: "text-slate-400 hover:text-slate-200" }}
                className="shrink-0 rounded-lg px-3.5 py-2 text-sm no-underline transition-colors"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1180px] flex-1 px-5 pb-16 pt-10 sm:px-8 sm:pt-12 lg:px-12">
        <Outlet />
      </main>

      <footer className="border-t border-slate-800/60">
        <div className="mx-auto w-full max-w-[1180px] px-5 py-6 text-xs text-slate-600 sm:px-8 lg:px-12">
          Powered by journal-scout-mcp · Scopus · OpenAlex · Semantic Scholar · Crossref
        </div>
      </footer>
    </div>
  );
}

const rootRoute = createRootRoute({ component: RootLayout });

const searchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    q?: string;
    sources?: string;
    affiliation?: string;
    issn?: string;
    orcid?: string;
    doi?: string;
  } => {
    const text = (value: unknown): string | undefined =>
      typeof value === "string" ? value : undefined;
    return {
      q: text(search.q),
      sources: text(search.sources),
      affiliation: text(search.affiliation),
      issn: text(search.issn),
      orcid: text(search.orcid),
      doi: text(search.doi),
    };
  },
  component: SearchPage,
});

const graphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/graph",
  validateSearch: (search: Record<string, unknown>) => ({
    identifier: typeof search.identifier === "string" ? search.identifier : "",
  }),
  component: GraphPage,
});

const metricsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/metrics",
  component: MetricsPage,
});

const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/history",
  component: HistoryPage,
});

const routeTree = rootRoute.addChildren([searchRoute, graphRoute, metricsRoute, historyRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
