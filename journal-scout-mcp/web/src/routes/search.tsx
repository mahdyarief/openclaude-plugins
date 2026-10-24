import { useState } from "react";
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

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      setData(await searchPapers(trimmed, limit));
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

      <form onSubmit={submit} className={`${CARD} p-4 sm:p-5`}>
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
          </div>

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
