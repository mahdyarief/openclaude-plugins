import { useEffect, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { ForceGraph } from "../components/ForceGraph";
import { fetchNetwork, graphmlUrl } from "../lib/api";
import type { GraphNode, NetworkResponse } from "../lib/types";
import {
  ALERT_ERROR,
  ALERT_WARN,
  CARD,
  CHIP,
  EYEBROW,
  FIELD,
  FIELD_SM,
  GHOST_BTN,
  H1,
  LEDE,
  PAGE,
  PRIMARY_BTN,
} from "../lib/ui";

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
    <div className={PAGE}>
      <section className="space-y-3">
        <p className={EYEBROW}>Connected papers</p>
        <h1 className={H1}>Citation graph</h1>
        <p className={LEDE}>
          Direct citations, bibliographic coupling and co-citation around one seed paper. Click any
          node to inspect the underlying record.
        </p>
      </section>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          const value = seedInput.trim();
          if (value) {
            navigate({ search: { identifier: value } });
          }
        }}
        className={`${CARD} p-4 sm:p-5`}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-xs text-slate-400">
            Seed identifier (DOI, Scopus id, OpenAlex id)
            <input
              value={seedInput}
              onChange={(event) => setSeedInput(event.target.value)}
              placeholder="10.1145/3292500.3330701"
              className={`${FIELD} h-11`}
            />
          </label>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5 text-xs text-slate-400">
              refs / cites
              <input
                type="number"
                min={1}
                max={100}
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value) || 20)}
                className={`${FIELD_SM} h-11 w-24`}
              />
            </label>
            <label className="flex flex-col gap-1.5 text-xs text-slate-400">
              citing refs
              <input
                type="number"
                min={0}
                max={50}
                value={citingLimit}
                onChange={(event) => setCitingLimit(Number(event.target.value) || 0)}
                className={`${FIELD_SM} h-11 w-24`}
              />
            </label>
            <button type="submit" className={PRIMARY_BTN}>
              Build graph
            </button>
            {identifier && (
              <a href={graphmlUrl(identifier, limit, citingLimit)} className={GHOST_BTN}>
                Export GraphML
              </a>
            )}
          </div>
        </div>
      </form>

      {loading && <p className="text-sm text-slate-400">Building network…</p>}

      {error && <div className={ALERT_ERROR}>{error}</div>}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <div className={ALERT_WARN}>
          {Object.entries(data.errors).map(([source, message]) => (
            <div key={source}>
              <strong>{source}:</strong> {message}
            </div>
          ))}
        </div>
      )}

      {data?.stats && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.stats).map(([key, value]) => (
            <span key={key} className={CHIP}>
              {key.replace(/_/g, " ")}: {value}
            </span>
          ))}
        </div>
      )}

      {data?.nodes && data.nodes.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <ForceGraph
            nodes={data.nodes}
            edges={data.edges ?? []}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <aside
            className={`${CARD} scroll-thin max-h-[560px] overflow-auto p-5`}
          >
            {selected ? (
              <div className="space-y-2.5">
                <span className="inline-block rounded border border-slate-700 bg-slate-800/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                  {selected.kind}
                </span>
                <h2 className="m-0 text-sm font-semibold leading-snug text-slate-100">
                  {selected.label}
                </h2>
                <p className="m-0 text-xs leading-relaxed text-slate-400">
                  {selected.authors.slice(0, 4).join(", ") || "Unknown authors"}
                  {selected.year ? ` · ${selected.year}` : ""}
                </p>
                {selected.venue && (
                  <p className="m-0 text-xs leading-relaxed text-slate-500">{selected.venue}</p>
                )}
                <p className="m-0 text-xs text-slate-400">
                  Citations: {selected.citation_count ?? "n/a"}
                </p>
                {selected.doi && (
                  <p className="m-0 break-all text-[11px] text-slate-500">DOI: {selected.doi}</p>
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
              <p className="m-0 text-xs text-slate-500">Click a node to inspect it.</p>
            )}
          </aside>
        </div>
      ) : (
        !loading &&
        !error && (
          <p className="text-sm text-slate-500">
            Enter a DOI or provider id to build a network.
          </p>
        )
      )}
    </div>
  );
}
