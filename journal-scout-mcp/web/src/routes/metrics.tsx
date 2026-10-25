import { useState } from "react";
import { fetchMetrics, metricsCsvUrl, metricsReportUrl } from "../lib/api";
import type { MetricsResponse } from "../lib/types";
import {
  Alert,
  AnchorButton,
  Button,
  Card,
  Input,
  PageHeader,
  LoadingLine,
  Spinner,
} from "../components/ui";

type MetricCard = { key: string; label: string; hint: string };

type MetricsQuery = {
  author?: string;
  query?: string;
  limitPerSource?: number;
  yearFrom?: number;
  yearTo?: number;
  mode?: "basic" | "extended";
};

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
    <section className="space-y-2">
      <h2 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {title}
      </h2>
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {cards.map((card) => {
          const raw = (data as unknown as Record<string, unknown>)[card.key];
          const display =
            raw === null || raw === undefined ? "-" : typeof raw === "number" ? raw : String(raw);
          return (
            <Card key={card.key} className="px-3 py-2.5">
              <p className="m-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                {card.label}
              </p>
              <p className="m-0 mt-1 text-xl font-semibold tabular-nums leading-tight text-slate-50">
                {display}
              </p>
              <p className="m-0 mt-0.5 text-[11px] leading-snug text-slate-400">{card.hint}</p>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function CitationsByYearTable({ data }: { data: MetricsResponse }) {
  const rows = data.by_year ?? [];
  if (rows.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        Citations per year
      </h2>
      <Card className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-wide text-slate-400">
              <th className="px-3 py-2 font-medium">Year</th>
              <th className="px-3 py-2 text-right font-medium">Papers</th>
              <th className="px-3 py-2 text-right font-medium">Citations</th>
              <th className="px-3 py-2 text-right font-medium">Cumulative</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.year} className="border-b border-slate-800/60 last:border-0">
                <td className="px-3 py-1.5 tabular-nums text-slate-300">{row.year}</td>
                <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">{row.papers}</td>
                <td className="px-3 py-1.5 text-right tabular-nums text-slate-300">
                  {row.citations}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-slate-400">
                  {row.cumulative_citations}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
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
  const [lastQuery, setLastQuery] = useState<MetricsQuery | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    const params = {
      [searchBy]: trimmed,
      limitPerSource: limit,
      yearFrom: yearFrom ? Number(yearFrom) : undefined,
      yearTo: yearTo ? Number(yearTo) : undefined,
      mode: metricMode,
    };
    setLastQuery(params);
    try {
      setData(await fetchMetrics(params));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Bibliometrics"
        description="Indicators for an author name or a topic query, computed over the merged multi-source result set rather than a single index."
      />

      <Card className="space-y-2 p-2.5">
        <form onSubmit={submit} className="space-y-2">
        <div className="flex flex-col gap-1.5 lg:flex-row lg:items-center">
          <div className="flex shrink-0 rounded-md border border-slate-500 bg-slate-800/40 p-0.5 text-[11px]">
            {(["author", "query"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setSearchBy(option)}
                aria-pressed={searchBy === option}
                className={`touch-target rounded px-2.5 py-1 transition-colors ${
                  searchBy === option
                    ? "bg-slate-700 text-slate-50"
                    : "text-slate-400 hover:text-slate-100"
                }`}
              >
                {option === "author" ? "Author" : "Topic query"}
              </button>
            ))}
          </div>

          <div className="flex shrink-0 rounded-md border border-slate-500 bg-slate-800/40 p-0.5 text-[11px]">
            {(["basic", "extended"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setMetricMode(option)}
                aria-pressed={metricMode === option}
                className={`touch-target rounded px-2.5 py-1 transition-colors ${
                  metricMode === option
                    ? "bg-slate-700 text-slate-50"
                    : "text-slate-400 hover:text-slate-100"
                }`}
              >
                {option === "basic" ? "Basic" : "Extended"}
              </button>
            ))}
          </div>

          <Input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={searchBy === "author" ? "e.g. Harzing, Anne-Wil" : "e.g. bibliometric analysis"}
            aria-label={searchBy === "author" ? "Author name" : "Topic query"}
            className="min-w-0 flex-1"
          />

          <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-slate-400">
            per source
            <Input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value) || 50)}
              controlSize="sm"
              className="w-20"
            />
          </label>

          <Button type="submit" disabled={loading}>
            {loading ? (
              <>
                <Spinner size="xs" />
                Computing…
              </>
            ) : (
              "Compute"
            )}
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
          <span className="font-medium uppercase tracking-wide">Year range</span>
          <label className="flex items-center gap-1.5">
            from
            <Input
              type="number"
              min={1900}
              max={2100}
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
              placeholder="any"
              controlSize="sm"
              className="w-20"
            />
          </label>
          <label className="flex items-center gap-1.5">
            to
            <Input
              type="number"
              min={1900}
              max={2100}
              value={yearTo}
              onChange={(event) => setYearTo(event.target.value)}
              placeholder="any"
              controlSize="sm"
              className="w-20"
            />
          </label>
        </div>
        </form>
      </Card>

      {error && <Alert>{error}</Alert>}

      {loading && (
        <LoadingLine>Collecting citations from every provider…</LoadingLine>
      )}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <Alert tone="warn">
          {Object.entries(data.errors).map(([source, message]) => (
            <div key={source}>
              <strong>{source}:</strong> {message}
            </div>
          ))}
        </Alert>
      )}

      {data && (
        <div className="space-y-4">
          {lastQuery && (
            <div className="flex flex-wrap items-center gap-1.5">
              <Card className="px-2.5 py-1 text-[11px] tabular-nums text-slate-300">
                {data.papers} papers · {data.total_citations} citations
              </Card>
              <AnchorButton
                href={metricsCsvUrl(lastQuery)}
                download="metrics.csv"
              >
                Download CSV
              </AnchorButton>
              <AnchorButton
                href={metricsReportUrl({ ...lastQuery, mode: metricMode })}
                download="metrics-report.txt"
              >
                Download search report
              </AnchorButton>
            </div>
          )}
          <MetricGroup title="Basic" cards={BASIC_CARDS} data={data} />
          <MetricGroup title="Extended" cards={EXTENDED_CARDS} data={data} />
          <CitationsByYearTable data={data} />
        </div>
      )}
    </div>
  );
}
