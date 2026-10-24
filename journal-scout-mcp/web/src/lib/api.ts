import type {
  MetricsResponse,
  NetworkResponse,
  Paper,
  SearchResponse,
} from "./types";

async function getJson<T>(path: string, params: Record<string, string | number | undefined | null>): Promise<T> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const response = await fetch(`${path}?${search.toString()}`);
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      (payload as { error?: string }).error || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload as T;
}

export type SearchOptions = {
  limitPerSource?: number;
  yearFrom?: number;
  yearTo?: number;
  techOnly?: boolean;
  offset?: number;
  sources?: string[];
};

export function searchPapers(query: string, options: SearchOptions = {}): Promise<SearchResponse> {
  const sources = options.sources?.filter((source) => source.trim() !== "") ?? [];
  return getJson<SearchResponse>("/api/search", {
    query,
    limit_per_source: options.limitPerSource,
    year_from: options.yearFrom,
    year_to: options.yearTo,
    tech_only: options.techOnly ? "true" : undefined,
    offset: options.offset,
    source: sources.length > 0 ? sources.join(",") : undefined,
  });
}

export function fetchPaper(identifier: string): Promise<{ paper: Paper | null; errors?: Record<string, string> }> {
  return getJson("/api/paper", { identifier });
}

export function fetchNetwork(
  identifier: string,
  limit: number,
  citingLimit: number,
  maxNodes: number,
): Promise<NetworkResponse> {
  return getJson<NetworkResponse>("/api/network", {
    identifier,
    limit,
    citing_limit: citingLimit,
    max_nodes: maxNodes,
  });
}

export function fetchMetrics(params: {
  author?: string;
  query?: string;
  limitPerSource?: number;
  yearFrom?: number;
  yearTo?: number;
  mode?: "basic" | "extended";
}): Promise<MetricsResponse> {
  return getJson<MetricsResponse>("/api/metrics", {
    author: params.author,
    query: params.query,
    limit_per_source: params.limitPerSource,
    year_from: params.yearFrom,
    year_to: params.yearTo,
    mode: params.mode,
  });
}

export function graphmlUrl(identifier: string, limit: number, citingLimit: number): string {
  const search = new URLSearchParams({
    identifier,
    limit: String(limit),
    citing_limit: String(citingLimit),
    format: "graphml",
  });
  return `/api/network?${search.toString()}`;
}
