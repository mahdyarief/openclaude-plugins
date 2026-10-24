import { useState } from "react";
import { ExportMenu } from "../components/ExportMenu";
import { PaperCard } from "../components/PaperCard";
import { searchPapers } from "../lib/api";
import type { SearchResponse } from "../lib/types";
import {
  ALERT_ERROR,
  ALERT_WARN,
  CARD,
  CHIP,
  EYEBROW,
  FIELD,
  FIELD_SM,
  H1,
  LEDE,
  PAGE,
  PRIMARY_BTN,
} from "../lib/ui";

const PROVIDERS = [
  "scopus",
  "arxiv",
  "openalex",
  "semanticscholar",
  "crossref",
  "pubmed",
  "dblp",
];

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [techOnly, setTechOnly] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [offset, setOffset] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleSource(source: string) {
    setSelectedSources((current) =>
      current.includes(source)
        ? current.filter((item) => item !== source)
        : [...current, source],
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await searchPapers(trimmed, {
          limitPerSource: limit,
          yearFrom: yearFrom ? Number(yearFrom) : undefined,
          yearTo: yearTo ? Number(yearTo) : undefined,
          techOnly: techOnly || undefined,
          offset: offset ? Number(offset) : undefined,
          sources: selectedSources,
        }),
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={PAGE}>
      <section className="space-y-3">
        <p className={EYEBROW}>Multi-source discovery</p>
        <h1 className={H1}>Literature search</h1>
        <p className={LEDE}>
          One query fans out across Scopus, OpenAlex, Semantic Scholar, Crossref, arXiv and DBLP,
          then duplicate records are merged DOI-first into a single result set.
        </p>
      </section>

      <form onSubmit={submit} className={`${CARD} space-y-4 p-4 sm:p-5`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. graph neural networks for citation recommendation"
            className={`${FIELD} h-11 min-w-0 flex-1`}
          />
          <div className="flex items-center gap-3">
            <label className="flex shrink-0 items-center gap-2 text-xs text-slate-400">
              per source
              <input
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value) || 10)}
                className={`${FIELD_SM} h-9 w-16`}
              />
            </label>
            <button type="submit" disabled={loading} className={`${PRIMARY_BTN} flex-1 sm:flex-none`}>
              {loading ? "Searching…" : "Search"}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-slate-800/70 pt-4 text-xs text-slate-400">
          <span className="text-slate-500">Year range</span>
          <label className="flex items-center gap-2">
            from
            <input
              type="number"
              min={1900}
              max={2100}
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
              placeholder="—"
              className={`${FIELD_SM} h-9 w-24`}
            />
          </label>
          <label className="flex items-center gap-2">
            to
            <input
              type="number"
              min={1900}
              max={2100}
              value={yearTo}
              onChange={(event) => setYearTo(event.target.value)}
              placeholder="—"
              className={`${FIELD_SM} h-9 w-24`}
            />
          </label>
          <label className="flex items-center gap-2">
            offset
            <input
              type="number"
              min={0}
              value={offset}
              onChange={(event) => setOffset(event.target.value)}
              placeholder="0"
              className={`${FIELD_SM} h-9 w-20`}
            />
          </label>
          <label className="flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={techOnly}
              onChange={(event) => setTechOnly(event.target.checked)}
              className="h-4 w-4 accent-sky-500"
            />
            tech only
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-800/70 pt-4 text-xs text-slate-400">
          <span className="text-slate-500">Sources</span>
          {PROVIDERS.map((provider) => (
            <button
              key={provider}
              type="button"
              onClick={() => toggleSource(provider)}
              className={`rounded-md border px-2 py-1 transition-colors ${
                selectedSources.includes(provider)
                  ? "border-sky-500/40 bg-sky-500/15 text-sky-200"
                  : "border-slate-800 bg-slate-900/60 text-slate-400 hover:text-slate-200"
              }`}
            >
              {provider}
            </button>
          ))}
          {selectedSources.length > 0 && (
            <button
              type="button"
              onClick={() => setSelectedSources([])}
              className="px-1 text-slate-500 underline-offset-2 hover:text-slate-300 hover:underline"
            >
              all providers
            </button>
          )}
        </div>
      </form>

      {error && <div className={ALERT_ERROR}>{error}</div>}

      {data && (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <span className={`${CHIP} text-slate-300`}>
              {data.results.length} merged results
            </span>
            {Object.entries(data.counts || {}).map(([source, count]) => (
              <span key={source} className={CHIP}>
                {source}: {count}
              </span>
            ))}
            {data.results.length > 0 && <ExportMenu papers={data.results} />}
          </div>

          {(data.filters_ignored?.length ?? 0) > 0 && (
            <div className={ALERT_WARN}>
              <strong>Filters ignored:</strong>{" "}
              {data.filters_ignored?.join(", ")} — not every source honours these filters, so
              results may include records that do not match them.
            </div>
          )}

          {Object.keys(data.filters_applied || {}).length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="text-slate-500">Filters applied</span>
              {Object.entries(data.filters_applied || {}).map(([provider, filters]) => (
                <span key={provider} className={CHIP}>
                  {provider}: {filters.join(", ")}
                </span>
              ))}
            </div>
          )}

          {Object.keys(data.errors || {}).length > 0 && (
            <div className={ALERT_WARN}>
              {Object.entries(data.errors).map(([source, message]) => (
                <div key={source}>
                  <strong>{source}:</strong> {message}
                </div>
              ))}
            </div>
          )}

          {data.results.length === 0 ? (
            <p className="text-sm text-slate-500">No results.</p>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {data.results.map((paper, index) => (
                <PaperCard key={`${paper.doi ?? paper.title}-${index}`} paper={paper} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
