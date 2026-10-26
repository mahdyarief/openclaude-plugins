import type {
  CacheClearResponse,
  CacheInfoResponse,
  DeleteSearchResponse,
  DuplicateResponse,
  ImportResponse,
  MergeResponse,
  MetricsResponse,
  NetworkResponse,
  Paper,
  QuotaResponse,
  RelationResponse,
  ReplayResponse,
  SearchArchive,
  SearchCondition,
  SearchHistoryResponse,
  SearchResponse,
  SplitResponse,
  WorkspaceArchive,
  WorkspaceImportResponse,
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
  author?: string;
  venue?: string;
  affiliation?: string;
  issn?: string;
  orcid?: string;
  doi?: string;
  sort?: "relevance" | "citations" | "year" | "title";
  order?: "asc" | "desc";
  topic?: string;
  conditions?: SearchCondition[];
};

export function searchPapers(query: string, options: SearchOptions = {}): Promise<SearchResponse> {
  const sources = options.sources?.filter((source) => source.trim() !== "") ?? [];
  const conditions = (options.conditions ?? []).filter(
    (condition) => condition.value.trim() !== "",
  );
  return getJson<SearchResponse>("/api/search", {
    query,
    limit_per_source: options.limitPerSource,
    year_from: options.yearFrom,
    year_to: options.yearTo,
    tech_only: options.techOnly ? "true" : undefined,
    offset: options.offset,
    source: sources.length > 0 ? sources.join(",") : undefined,
    author: options.author,
    venue: options.venue,
    affiliation: options.affiliation,
    issn: options.issn,
    orcid: options.orcid,
    doi: options.doi,
    sort: options.sort,
    order: options.order,
    topic: options.topic,
    conditions: conditions.length > 0 ? JSON.stringify(conditions) : undefined,
  });
}

export function fetchSearches(limit = 20): Promise<SearchHistoryResponse> {
  return getJson<SearchHistoryResponse>("/api/searches", { limit });
}

export function fetchPaper(
  identifier: string,
  source?: string,
): Promise<{ paper: Paper | null; errors?: Record<string, string> }> {
  return getJson("/api/paper", { identifier, source });
}

export function fetchRelations(
  kind: "related" | "citations" | "references",
  identifier: string,
  source?: string,
  limit = 10,
): Promise<RelationResponse> {
  return getJson<RelationResponse>(`/api/${kind}`, { identifier, source, limit });
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

function metricsParams(params: {
  author?: string;
  query?: string;
  limitPerSource?: number;
  yearFrom?: number;
  yearTo?: number;
  mode?: "basic" | "extended";
}): URLSearchParams {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries({
    author: params.author,
    query: params.query,
    limit_per_source: params.limitPerSource,
    year_from: params.yearFrom,
    year_to: params.yearTo,
    mode: params.mode,
  })) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  return search;
}

export function metricsCsvUrl(params: Parameters<typeof metricsParams>[0]): string {
  return `/api/metrics/export?${metricsParams(params).toString()}`;
}

export function metricsReportUrl(params: Parameters<typeof metricsParams>[0]): string {
  return `/api/metrics/report?${metricsParams(params).toString()}`;
}

async function sendJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    ...(body !== undefined
      ? {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
  });
  const text = await response.text();
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = JSON.parse(text) as { error?: string };
      if (payload.error) message = payload.error;
    } catch {
      // Non-JSON error body; keep the status message.
    }
    throw new Error(message);
  }
  return JSON.parse(text) as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

export function mergePapers(papers: Paper[]): Promise<MergeResponse> {
  return postJson<MergeResponse>("/api/merge", { papers });
}

export function searchArchiveUrl(searchId: string): string {
  return `/api/searches/${encodeURIComponent(searchId)}/export`;
}

export function importSearchArchive(
  archive: SearchArchive,
): Promise<{ id: string; result_count: number }> {
  return postJson("/api/searches/import", archive);
}

export function fetchQuota(): Promise<QuotaResponse> {
  return getJson<QuotaResponse>("/api/quota", {});
}

export function importPapers(content: string, format?: string): Promise<ImportResponse> {
  return postJson<ImportResponse>("/api/import", {
    content,
    ...(format !== undefined ? { format } : {}),
  });
}

export function clearCache(prefix?: string): Promise<CacheClearResponse> {
  return postJson<CacheClearResponse>("/api/cache/clear", {
    ...(prefix !== undefined ? { prefix } : {}),
  });
}

export function splitSearch(id: string, size: number): Promise<SplitResponse> {
  return postJson<SplitResponse>(`/api/searches/${encodeURIComponent(id)}/split`, { size });
}

export function duplicateSearch(id: string): Promise<DuplicateResponse> {
  return postJson<DuplicateResponse>(`/api/searches/${encodeURIComponent(id)}/duplicate`, {});
}

export function replaySearch(id: string): Promise<ReplayResponse> {
  return getJson<ReplayResponse>(`/api/searches/${encodeURIComponent(id)}/replay`, {});
}

export function deleteSearch(id: string): Promise<DeleteSearchResponse> {
  return sendJson<DeleteSearchResponse>(
    "DELETE",
    `/api/searches/${encodeURIComponent(id)}`,
  );
}

export function workspaceArchiveUrl(): string {
  return "/api/searches/export";
}

export function importWorkspaceArchive(
  archive: WorkspaceArchive,
): Promise<WorkspaceImportResponse> {
  return postJson<WorkspaceImportResponse>("/api/searches/import-workspace", archive);
}

export function fetchCacheInfo(prefix?: string, limit = 200): Promise<CacheInfoResponse> {
  return getJson<CacheInfoResponse>("/api/cache/info", { prefix, limit });
}

export const EXPORT_FORMATS = [
  "bibtex", "ris", "csv", "json", "endnote",
  "isi", "csv_header", "apa", "chicago", "harvard", "vancouver",
  "mla", "csiro", "xls", "csv_bom", "csv_plain", "xls_plain",
] as const;

export type ExportFormat = (typeof EXPORT_FORMATS)[number];

export async function exportPapers(papers: Paper[], format: ExportFormat): Promise<string> {
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ papers, format }),
  });
  const text = await response.text();
  if (!response.ok) {
    let message = `Export failed (${response.status})`;
    try {
      const payload = JSON.parse(text) as { error?: string };
      if (payload.error) message = payload.error;
    } catch {
      // Non-JSON error body; keep the status message.
    }
    throw new Error(message);
  }
  return text;
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
