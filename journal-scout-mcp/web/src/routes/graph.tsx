import { useEffect, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { ForceGraph } from "../components/ForceGraph";
import { fetchNetwork, graphmlUrl } from "../lib/api";
import type { GraphNode, NetworkResponse } from "../lib/types";
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

export function GraphPage() {
  const { identifier } = useSearch({ from: "/graph" });
  const navigate = useNavigate({ from: "/graph" });
  const [seedInput, setSeedInput] = useState(identifier ?? "");
  const [limit, setLimit] = useState(20);
  const [citingLimit, setCitingLimit] = useState(10);
  const [data, setData] = useState<NetworkResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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
        setError(exc instanceof Error ? exc.message : String(exc));
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

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Citation graph"
        description="Direct citations, bibliographic coupling and co-citation around one seed paper. Click any node to inspect the underlying record."
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
        <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <ForceGraph
            nodes={data.nodes}
            edges={data.edges ?? []}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <Card className="scroll-thin max-h-[560px] overflow-auto p-3">
            {selected ? (
              <div className="space-y-2">
                <span className="inline-block rounded border border-slate-700 bg-slate-800/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                  {selected.kind}
                </span>
                <h2 className="m-0 text-[13px] font-semibold leading-snug text-slate-100">
                  {selected.label}
                </h2>
                <p className="m-0 text-[11px] leading-relaxed text-slate-400">
                  {selected.authors.slice(0, 4).join(", ") || "Unknown authors"}
                  {selected.year ? ` · ${selected.year}` : ""}
                </p>
                {selected.venue && (
                  <p className="m-0 text-[11px] leading-relaxed text-slate-400">{selected.venue}</p>
                )}
                <p className="m-0 text-[11px] text-slate-400">
                  Citations: {selected.citation_count ?? "n/a"}
                </p>
                {selected.doi && (
                  <p className="m-0 break-all text-[11px] text-slate-400">DOI: {selected.doi}</p>
                )}
                {selected.url && (
                  <a
                    href={selected.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-block text-[11px] text-sky-400 no-underline hover:text-sky-300"
                  >
                    Open source record
                  </a>
                )}
              </div>
            ) : (
              <p className="m-0 text-[11px] text-slate-400">Click a node, or tab into the node list, to inspect it.</p>
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
