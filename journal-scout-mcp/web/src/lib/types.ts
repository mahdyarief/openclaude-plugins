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
};

export type SearchResponse = {
  results: Paper[];
  errors: Record<string, string>;
  counts: Record<string, number>;
  filters_applied?: Record<string, string[]>;
  filters_ignored?: string[];
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
  sources: string[];
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
  };
  seed_paper?: Paper;
  errors?: Record<string, string>;
  counts?: Record<string, unknown>;
  error?: string;
  format?: string;
};

export type MetricsResponse = {
  papers: number;
  total_citations: number;
  h_index: number;
  i10_index: number;
  g_index: number;
  max_citations: number;
  mean_citations: number;
  citation_velocity: number | null;
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
