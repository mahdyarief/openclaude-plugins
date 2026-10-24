import { useState } from "react";
import { fetchMetrics } from "../lib/api";
import type { MetricsResponse } from "../lib/types";
import {
  ALERT_ERROR,
  ALERT_WARN,
  CARD,
  EYEBROW,
  FIELD,
  FIELD_SM,
  H1,
  LEDE,
  PAGE,
  PRIMARY_BTN,
} from "../lib/ui";

type MetricCard = { key: string; label: string; hint: string };

const BASIC_CARDS: MetricCard[] = [
  { key: "papers", label: "Papers", hint: "works matched" },
  { key: "total_citations", label: "Total citations", hint: "sum across works" },
  { key: "h_index", label: "h-index", hint: "h papers with >= h citations" },
  { key: "i10_index", label: "i10-index", hint: "papers with >= 10 citations" },
  { key: "g_index", label: "g-index", hint: "top g works total >= g²" },
  { key: "e_index", label: "e-index", hint: "sqrt of citation tail above h²" },
  { key: "max_citations", label: "Max citations", hint: "most cited work" },
  { key: "mean_citations", label: "Mean citations", hint: "average per work" },
  { key: "citation_velocity", label: "Citation velocity", hint: "citations per year" },
  { key: "cites_year", label: "Cites / year", hint: "citations per calendar year" },
  { key: "cites_paper", label: "Cites / paper", hint: "average citations per work" },
  { key: "cites_author", label: "Cites / author", hint: "citations per authorship" },
  { key: "papers_author", label: "Papers / author", hint: "productivity" },
  { key: "authors_paper", label: "Authors / paper", hint: "collaboration" },
];

const EXTENDED_CARDS: MetricCard[] = [
  { key: "hc_index", label: "hc-index", hint: "h-index over recent years" },
  {
    key: "hI_index",
    label: "hI-index",
    hint: "Batista's individual h-index: h divided by the mean number of authors of the papers in the h-core",
  },
  {
    key: "hI_norm",
    label: "hI norm",
    hint: "h-index over per-paper citations divided by author count (Publish or Perish)",
  },
  { key: "AWCR", label: "AWCR", hint: "age-weighted citation rate" },
  { key: "AW_index", label: "AW-index", hint: "sqrt of AWCR" },
  { key: "AWCRpA", label: "AWCR per author", hint: "AWCR divided by authors" },
  {
    key: "hm_index",
    label: "hm-index",
    hint: "Schreiber's hm-index: each paper counts 1/a of an effective rank; largest rank still supported by citations",
  },
];

function MetricGroup({
  title,
  cards,
  data,
}: {
  title: string;
  cards: MetricCard[];
  data: MetricsResponse;
}) {
  return (
    <section className="space-y-3">
      <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const raw = (data as unknown as Record<string, unknown>)[card.key];
          const display =
            raw === null || raw === undefined ? "—" : typeof raw === "number" ? raw : String(raw);
          return (
            <div key={card.key} className={`${CARD} p-5`}>
              <p className="m-0 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                {card.label}
              </p>
              <p className="m-0 mt-2 text-3xl font-semibold tabular-nums text-slate-50">
                {display}
              </p>
              <p className="m-0 mt-1.5 text-[11px] leading-snug text-slate-500">{card.hint}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function MetricsPage() {
  const [searchBy, setSearchBy] = useState<"author" | "query">("author");
  const [metricMode, setMetricMode] = useState<"basic" | "extended">("extended");
  const [value, setValue] = useState("");
  const [limit, setLimit] = useState(50);
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await fetchMetrics({
          [searchBy]: trimmed,
          limitPerSource: limit,
          yearFrom: yearFrom ? Number(yearFrom) : undefined,
          yearTo: yearTo ? Number(yearTo) : undefined,
          mode: metricMode,
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
        <p className={EYEBROW}>Publish or Perish</p>
        <h1 className={H1}>Bibliometrics</h1>
        <p className={LEDE}>
          Indicators for an author name or a topic query, computed over the merged multi-source
          result set rather than a single index.
        </p>
      </section>

      <form onSubmit={submit} className={`${CARD} space-y-4 p-4 sm:p-5`}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="flex shrink-0 rounded-xl border border-slate-800 bg-slate-900/60 p-1 text-xs">
            {(["author", "query"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setSearchBy(option)}
                className={`rounded-lg px-3 py-2 transition-colors ${
                  searchBy === option
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {option === "author" ? "Author" : "Topic query"}
              </button>
            ))}
          </div>

          <div className="flex shrink-0 rounded-xl border border-slate-800 bg-slate-900/60 p-1 text-xs">
            {(["basic", "extended"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setMetricMode(option)}
                className={`rounded-lg px-3 py-2 transition-colors ${
                  metricMode === option
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {option === "basic" ? "Basic" : "Extended"}
              </button>
            ))}
          </div>

          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={searchBy === "author" ? "e.g. Harzing, Anne-Wil" : "e.g. bibliometric analysis"}
            className={`${FIELD} h-11 min-w-0 flex-1`}
          />

          <label className="flex shrink-0 items-center gap-2 text-xs text-slate-400">
            per source
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value) || 50)}
              className={`${FIELD_SM} h-9 w-20`}
            />
          </label>

          <button type="submit" disabled={loading} className={PRIMARY_BTN}>
            {loading ? "Computing…" : "Compute"}
          </button>
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
        </div>
      </form>

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

      {data && (
        <div className="space-y-6">
          <MetricGroup title="Basic" cards={BASIC_CARDS} data={data} />
          <MetricGroup title="Extended" cards={EXTENDED_CARDS} data={data} />
        </div>
      )}
    </div>
  );
}
