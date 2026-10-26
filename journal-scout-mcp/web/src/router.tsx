import {
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { AppShell } from "./components/AppShell";
import { GraphPage } from "./routes/graph";
import { HistoryPage } from "./routes/history";
import { MetricsPage } from "./routes/metrics";
import { SearchPage } from "./routes/search";

const rootRoute = createRootRoute({ component: AppShell });

const searchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    q?: string;
    sources?: string;
    author?: string;
    venue?: string;
    affiliation?: string;
    issn?: string;
    orcid?: string;
    doi?: string;
    cached?: string;
  } => {
    const text = (value: unknown): string | undefined =>
      typeof value === "string" ? value : undefined;
    return {
      q: text(search.q),
      sources: text(search.sources),
      author: text(search.author),
      venue: text(search.venue),
      affiliation: text(search.affiliation),
      issn: text(search.issn),
      orcid: text(search.orcid),
      doi: text(search.doi),
      // A search id to load from the history archive instead of querying again.
      cached: text(search.cached),
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
