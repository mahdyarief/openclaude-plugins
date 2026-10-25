export type Paper = {
  doi: string | null;
  title: string;
  abstract: string | null;
  year: number | null;
  authors: string[];
  venue: string | null;
  citation_count: number | null;
  url: string | null;
  pdf_url: string | null;
  is_open_access: boolean | null;
  type: string | null;
  sources: string[];
  ids: Record<string, string>;
  is_retracted?: boolean | null;
  cited_by_percentile?: number | null;
  citations_by_year?: Record<string, number>;
  topics?: string[];
  keywords?: string[];
  institutions?: string[];
  funders?: string[];
  publication_types?: string[];
  language?: string | null;
  license?: string | null;
  tldr?: string | null;
};

export type RelationResponse = {
  results: Paper[];
  errors?: Record<string, string>;
  counts?: Record<string, number>;
};

export type SearchResponse = {
  results: Paper[];
  errors: Record<string, string>;
  counts: Record<string, number>;
  filters_applied?: Record<string, string[]>;
  filters_ignored?: string[];
  query_warnings?: { source: string; operator: string; message: string }[];
  query_translated?: Record<string, string>;
};

export type GraphNode = {
  id: string;
  label: string;
  kind: "seed" | "reference" | "citation" | "cocited";
  doi: string | null;
  year: number | null;
  authors: string[];
  venue: string | null;
  citation_count: number | null;
  url: string | null;
  abstract?: string | null;
  pdf_url?: string | null;
  is_open_access?: boolean | null;
  type?: string | null;
  sources: string[];
  in_degree?: number;
  out_degree?: number;
  degree?: number;
  community?: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  type: "cites" | "coupled" | "cocited";
  weight: number;
};

export type NetworkResponse = {
  seed?: string;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  stats?: {
    nodes: number;
    edges: number;
    references: number;
    citations: number;
    coupled_edges: number;
    cocited_edges: number;
    communities?: number;
  };
  seed_paper?: Paper;
  errors?: Record<string, string>;
  counts?: Record<string, unknown>;
  error?: string;
  format?: string;
};

export type SearchHistoryRow = {
  id: string;
  query: string;
  author: string | null;
  sources: string[] | null;
  filters: Record<string, unknown> | null;
  result_count: number;
  created_at: number;
  size_bytes?: number;
  age_seconds?: number;
};

export type SearchHistoryResponse = {
  searches: SearchHistoryRow[];
  persistent: boolean;
};

export type CitationsByYearRow = {
  year: number;
  papers: number;
  citations: number;
  cumulative_citations: number;
};

export type MetricsResponse = {
  papers: number;
  total_citations: number;
  h_index: number;
  i10_index: number;
  g_index: number;
  e_index?: number;
  max_citations: number;
  mean_citations: number;
  citation_velocity: number | null;
  cites_year?: number;
  cites_paper?: number;
  cites_author?: number;
  papers_author?: number;
  authors_paper?: number;
  by_year?: CitationsByYearRow[];
  errors?: Record<string, string>;
  counts?: Record<string, number>;
  mode?: "basic" | "extended";
  hc_index?: number;
  hI_index?: number;
  hI_norm?: number;
  AWCR?: number;
  AW_index?: number;
  AWCRpA?: number;
  hm_index?: number;
};

export type MergeResponse = {
  results: Paper[];
  input_count: number;
  merged_count: number;
};

export type SearchArchive = {
  format: string;
  version: number;
  query: string | null;
  author: string | null;
  sources: string[] | null;
  filters: Record<string, unknown> | null;
  created_at: number | null;
  results: Paper[];
};

export type QuotaSource = {
  source: string;
  limit: string;
  used: string | null;
  remaining: string | null;
  reset: string | null;
  notes: string;
};

export type QuotaResponse = { sources: Record<string, QuotaSource> };

export type ImportResponse = { format: string; count: number; papers: Paper[] };

export type CacheClearResponse = { cleared: number };

export type SplitResponse = { ids: string[]; count: number };

export type CacheEntryInfo = {
  key: string;
  size_bytes: number;
  expires_in_seconds?: number;
  ttl_remaining?: number;
  age_seconds: number;
  expired: boolean;
};

export type CacheInfoResponse = {
  memory: CacheEntryInfo[] | null;
  store: CacheEntryInfo[] | null;
};

export type DuplicateResponse = { id: string };

export type DeleteSearchResponse = { id: string; deleted: boolean };

export type WorkspaceArchive = {
  format: string;
  version: number;
  count: number;
  searches: SearchArchive[];
};

export type WorkspaceImportResponse = { ids: string[]; count: number };

export type ReplayResponse = {
  id: string;
  query: string;
  author: string | null;
  sources: string[] | null;
  filters: Record<string, unknown> | null;
  result_count: number;
  created_at: number;
  results: Paper[];
  stale: boolean;
};
