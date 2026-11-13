import { useEffect, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { ForceGraph } from "../components/ForceGraph";
import { fetchNetwork, fetchRelations, graphmlUrl } from "../lib/api";
import type { GraphEdge, GraphNode, NetworkResponse, Paper } from "../lib/types";
import {
  Alert,
  AnchorButton,
  Button,
  Card,
  Chip,
  Input,
  LoadingLine,
  PageHeader,
  Spinner,
} from "../components/ui";

function nodeIdForPaper(paper: Paper): string {
  if (paper.doi) return `doi:${paper.doi}`;
  const firstId = Object.entries(paper.ids ?? {})[0];
  if (firstId) return `${firstId[0]}:${firstId[1]}`;
  return `title:${paper.title}`;
}

function identifierForNode(node: GraphNode): string | null {
  if (node.doi) return node.doi;
  const match = /^[a-z]+:(.+)$/i.exec(node.id);
  return match ? match[1] : null;
}

function paperToNode(paper: Paper, kind: GraphNode["kind"]): GraphNode {
  return {
    id: nodeIdForPaper(paper),
    label: paper.title || paper.doi || "(untitled)",
    kind,
    doi: paper.doi,
    year: paper.year,
    authors: paper.authors,
    venue: paper.venue,
    citation_count: paper.citation_count,
    url: paper.url,
    abstract: paper.abstract,
    pdf_url: paper.pdf_url,
    is_open_access: paper.is_open_access,
    type: paper.type,
    sources: paper.sources,
  };
}

function mergeExpanded(
  current: NetworkResponse,
  parentId: string,
  papers: Paper[],
  kind: GraphNode["kind"],
): NetworkResponse {
  const nodes = [...(current.nodes ?? [])];
  const edges = [...(current.edges ?? [])];
  const known = new Set(nodes.map((node) => node.id));

  for (const paper of papers) {
    const node = paperToNode(paper, kind);
    if (node.id === parentId) continue;
    if (!known.has(node.id)) {
      nodes.push(node);
      known.add(node.id);
    }
    const edge: GraphEdge =
      kind === "reference"
        ? { source: parentId, target: node.id, type: "cites", weight: 1 }
        : { source: node.id, target: parentId, type: "cites", weight: 1 };
    const duplicate = edges.some(
      (existing) =>
        existing.type === edge.type &&
        existing.source === edge.source &&
        existing.target === edge.target,
    );
    if (!duplicate) edges.push(edge);
  }

  return { ...current, nodes, edges };
}

export function GraphPage() {
  const { identifier } = useSearch({ from: "/graph" });
  const navigate = useNavigate({ from: "/graph" });
  const [seedInput, setSeedInput] = useState(identifier ?? "");
  const [limit, setLimit] = useState(20);
  const [citingLimit, setCitingLimit] = useState(10);
  const [data, setData] = useState<NetworkResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanding, setExpanding] = useState<"references" | "citations" | null>(null);
  const [timeline, setTimeline] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSeedInput(identifier ?? "");
  }, [identifier]);

  useEffect(() => {
    if (!identifier) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchNetwork(identifier, limit, citingLimit, 200)
      .then((payload) => {
        if (cancelled) return;
        if (payload.error) {
          setError(payload.error);
          setData(null);
        } else {
          setData(payload);
          setSelectedId(payload.seed ?? null);
        }
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "Could not build the network.");
        setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identifier, limit, citingLimit]);

  const selected: GraphNode | null =
    data?.nodes?.find((node) => node.id === selectedId) ?? null;

  const expand = async (kind: "references" | "citations") => {
    if (!selected) return;
    const identifierForLookup = identifierForNode(selected);
    if (!identifierForLookup) {
      setError("This node has no DOI or provider id to expand from.");
      return;
    }
    setExpanding(kind);
    setError(null);
    try {
      const payload = await fetchRelations(kind, identifierForLookup, undefined, limit);
      if (!payload.results?.length) {
        setError(`No ${kind} returned for this record.`);
        return;
      }
      setData((current) =>
        current
          ? mergeExpanded(
              current,
              selected.id,
              payload.results,
              kind === "references" ? "reference" : "citation",
            )
          : current,
      );
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : `Could not load ${kind}.`);
    } finally {
      setExpanding(null);
    }
  };

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Citation graph"
        description="Direct citations, second-hop references, bibliographic coupling and co-citation around one seed paper. Click a node to inspect it, then expand it to keep exploring."
      />

      <Card className="p-2.5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const value = seedInput.trim();
            if (value) {
              navigate({ search: { identifier: value } });
            }
          }}
        >
          <div className="flex flex-col gap-2 lg:flex-row lg:items-end">
            <label className="flex min-w-0 flex-1 flex-col gap-1 text-[11px] text-slate-400">
              Seed identifier (DOI, Scopus id, OpenAlex id)
              <Input
                value={seedInput}
                onChange={(event) => setSeedInput(event.target.value)}
                placeholder="10.1145/3292500.3330701"
              />
            </label>
            <div className="flex flex-wrap items-end gap-1.5">
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                refs / cites
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value) || 20)}
                  controlSize="sm"
                  className="w-24"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                citing refs
                <Input
                  type="number"
                  min={0}
                  max={50}
                  value={citingLimit}
                  onChange={(event) => setCitingLimit(Number(event.target.value) || 0)}
                  controlSize="sm"
                  className="w-24"
                />
              </label>
              <Button type="submit" disabled={loading}>
                {loading ? (
                  <>
                    <Spinner size="xs" />
                    Building…
                  </>
                ) : (
                  "Build graph"
                )}
              </Button>
              <Button
                type="button"
                onClick={() => setTimeline((value) => !value)}
                variant={timeline ? "primary" : "ghost"}
              >
                {timeline ? "Timeline: on" : "Timeline"}
              </Button>
              {identifier && (
                <AnchorButton href={graphmlUrl(identifier, limit, citingLimit)}>
                  Export GraphML
                </AnchorButton>
              )}
            </div>
          </div>
        </form>
      </Card>

      {loading && <LoadingLine>Building network…</LoadingLine>}

      {error && <Alert>{error}</Alert>}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <Alert tone="warn">
          {Object.entries(data.errors).map(([source, message]) => (
            <div key={source}>
              <strong>{source}:</strong> {message}
            </div>
          ))}
        </Alert>
      )}

      {data?.stats && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(data.stats).map(([key, value]) => (
            <Chip key={key}>
              {key.replace(/_/g, " ")}: {value}
            </Chip>
          ))}
        </div>
      )}

      {data?.nodes && data.nodes.length > 0 ? (
        <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <ForceGraph
            nodes={data.nodes}
            edges={data.edges ?? []}
            selectedId={selectedId}
            onSelect={setSelectedId}
            timeline={timeline}
          />
          <Card className="scroll-thin max-h-[640px] overflow-auto p-3">
            {selected ? (
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <span className="inline-block rounded border border-slate-700 bg-slate-800/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                    {selected.kind}
                  </span>
                  {selected.community != null && <Chip>cluster {selected.community}</Chip>}
                  {selected.is_open_access && <Chip>open access</Chip>}
                </div>
                <h2 className="m-0 text-[13px] font-semibold leading-snug text-slate-100">
                  {selected.label}
                </h2>
                <p className="m-0 text-[11px] leading-relaxed text-slate-400">
                  {selected.authors.slice(0, 6).join(", ") || "Unknown authors"}
                  {selected.year ? ` · ${selected.year}` : ""}
                </p>
                {selected.venue && (
                  <p className="m-0 text-[11px] leading-relaxed text-slate-400">
                    {selected.venue}
                  </p>
                )}

                <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-400">
                  <span>cites out: {selected.out_degree ?? "–"}</span>
                  <span>·</span>
                  <span>cited by: {selected.in_degree ?? "–"}</span>
                  <span>·</span>
                  <span>citations: {selected.citation_count ?? "n/a"}</span>
                </div>

                {selected.type && (
                  <p className="m-0 text-[11px] text-slate-400">Type: {selected.type}</p>
                )}

                {selected.abstract ? (
                  <p className="m-0 whitespace-pre-line text-[11px] leading-relaxed text-slate-300">
                    {selected.abstract}
                  </p>
                ) : (
                  <p className="m-0 text-[11px] italic text-slate-500">
                    No abstract in the graph payload. Expand the record to fetch details.
                  </p>
                )}

                {selected.doi && (
                  <p className="m-0 break-all text-[11px] text-slate-400">
                    DOI: {selected.doi}
                  </p>
                )}

                <div className="flex flex-wrap gap-1.5 pt-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => expand("references")}
                    disabled={expanding != null}
                  >
                    {expanding === "references" ? <Spinner size="xs" /> : null}
                    Expand references
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => expand("citations")}
                    disabled={expanding != null}
                  >
                    {expanding === "citations" ? <Spinner size="xs" /> : null}
                    Expand citations
                  </Button>
                </div>

                <div className="flex flex-wrap gap-3 pt-1">
                  {selected.url && (
                    <a
                      href={selected.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-sky-400 no-underline hover:text-sky-300"
                    >
                      Source record
                    </a>
                  )}
                  {selected.pdf_url && (
                    <a
                      href={selected.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-sky-400 no-underline hover:text-sky-300"
                    >
                      Open PDF
                    </a>
                  )}
                  {selected.doi && (
                    <a
                      href={`https://doi.org/${selected.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-sky-400 no-underline hover:text-sky-300"
                    >
                      doi.org
                    </a>
                  )}
                </div>
              </div>
            ) : (
              <p className="m-0 text-[11px] text-slate-400">
                Click a node in the graph to inspect it.
              </p>
            )}
          </Card>
        </div>
      ) : (
        !loading &&
        !error && (
          <p className="m-0 text-[13px] text-slate-400">
            Enter a DOI or provider id to build a network.
          </p>
        )
      )}
    </div>
  );
}

