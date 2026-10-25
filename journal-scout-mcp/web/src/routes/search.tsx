import { useEffect, useState } from "react";
import { Link, useSearch } from "@tanstack/react-router";
import { ExportMenu } from "../components/ExportMenu";
import { PaperDrawer } from "../components/PaperDrawer";
import { PaperTable } from "../components/PaperTable";
import { replaySearch, searchPapers, type SearchOptions } from "../lib/api";
import type { Paper, SearchResponse } from "../lib/types";
import {
  Alert,
  Button,
  Card,
  Chip,
  Input,
  PageHeader,
  Select,
  Spinner,
  LoadingLine,
  LINK_CLASS,
  cn,
} from "../components/ui";
import { ChevronDownIcon, SlidersIcon } from "../components/icons";

const PROVIDERS = [
  "scopus",
  "arxiv",
  "openalex",
  "semanticscholar",
  "crossref",
  "pubmed",
  "dblp",
  "garuda",
];

function splitSources(value: string | undefined): string[] {
  return value
    ? value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item !== "")
    : [];
}

function paperKey(paper: SearchResponse["results"][number], index: number): string {
  return `${paper.doi ?? paper.title}-${index}`;
}

export function SearchPage() {
  const params = useSearch({ from: "/" });
  const [query, setQuery] = useState(params.q ?? "");
  const [limit, setLimit] = useState(10);
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [techOnly, setTechOnly] = useState(false);
  const [selectedSources, setSelectedSources] = useState<string[]>(
    splitSources(params.sources),
  );
  const [offset, setOffset] = useState("");
  const [affiliation, setAffiliation] = useState(params.affiliation ?? "");
  const [issn, setIssn] = useState(params.issn ?? "");
  const [orcid, setOrcid] = useState(params.orcid ?? "");
  const [doi, setDoi] = useState(params.doi ?? "");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<"" | "citations" | "year" | "title">("");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [warningsDismissed, setWarningsDismissed] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [drawerPaper, setDrawerPaper] = useState<Paper | null>(null);

  function toggleSelected(key: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function selectAll() {
    if (!data) return;
    setSelectedIds(new Set(data.results.map((paper, index) => paperKey(paper, index))));
  }

  function selectCited() {
    if (!data) return;
    setSelectedIds(
      new Set(
        data.results
          .map((paper, index) => ({ paper, key: paperKey(paper, index) }))
          .filter(({ paper }) => (paper.citation_count ?? 0) > 0)
          .map(({ key }) => key),
      ),
    );
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  function toggleSource(source: string) {
    setSelectedSources((current) =>
      current.includes(source)
        ? current.filter((item) => item !== source)
        : [...current, source],
    );
  }

  function resetFilters() {
    setYearFrom("");
    setYearTo("");
    setOffset("");
    setTechOnly(false);
    setAffiliation("");
    setIssn("");
    setOrcid("");
    setDoi("");
    setSelectedSources([]);
  }

  // Counts only the advanced filters, so the badge on the Filters button
  // tells the user what is hiding behind the collapsed panel.
  const activeFilterCount =
    (yearFrom ? 1 : 0) +
    (yearTo ? 1 : 0) +
    (offset ? 1 : 0) +
    (techOnly ? 1 : 0) +
    (affiliation.trim() ? 1 : 0) +
    (issn.trim() ? 1 : 0) +
    (orcid.trim() ? 1 : 0) +
    (doi.trim() ? 1 : 0) +
    selectedSources.length;

  async function run(term: string, options: SearchOptions) {
    if (!term) return;
    setLoading(true);
    setError(null);
    setSelectedIds(new Set());
    try {
      setData(await searchPapers(term, options));
      setWarningsDismissed(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  // Loads an archived result set without calling /api/search, so replaying a
  // history row never appends a duplicate entry to that same history.
  async function loadCached(searchId: string) {
    setLoading(true);
    setError(null);
    setSelectedIds(new Set());
    try {
      const payload = await replaySearch(searchId);
      setQuery(payload.query ?? "");
      setSelectedSources(payload.sources ?? []);
      setData({
        results: payload.results ?? [],
        errors: {},
        counts: {},
      });
      setWarningsDismissed(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    await run(query.trim(), {
      limitPerSource: limit,
      yearFrom: yearFrom ? Number(yearFrom) : undefined,
      yearTo: yearTo ? Number(yearTo) : undefined,
      techOnly: techOnly || undefined,
      offset: offset ? Number(offset) : undefined,
      sources: selectedSources,
      affiliation: affiliation.trim() || undefined,
      issn: issn.trim() || undefined,
      orcid: orcid.trim() || undefined,
      doi: doi.trim() || undefined,
      sort: sort || undefined,
      order,
    });
  }

  const results = data?.results ?? [];
  const selectedPapers = results.filter((paper, index) =>
    selectedIds.has(paperKey(paper, index)),
  );

  const paramQuery = params.q ?? "";
  const paramSources = params.sources ?? "";
  const paramAffiliation = params.affiliation ?? "";
  const paramIssn = params.issn ?? "";
  const paramOrcid = params.orcid ?? "";
  const paramDoi = params.doi ?? "";
  const paramCached = params.cached ?? "";

  useEffect(() => {
    if (paramCached) {
      void loadCached(paramCached);
      return;
    }
    if (!paramQuery.trim()) return;
    setQuery(paramQuery);
    setSelectedSources(splitSources(paramSources));
    setAffiliation(paramAffiliation);
    setIssn(paramIssn);
    setOrcid(paramOrcid);
    setDoi(paramDoi);
    void run(paramQuery, {
      limitPerSource: 10,
      sources: splitSources(paramSources),
      affiliation: paramAffiliation || undefined,
      issn: paramIssn || undefined,
      orcid: paramOrcid || undefined,
      doi: paramDoi || undefined,
    });
    // Re-run only when the URL-carried search changes (e.g. a history Reload).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    paramCached,
    paramQuery,
    paramSources,
    paramAffiliation,
    paramIssn,
    paramOrcid,
    paramDoi,
  ]);

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Literature search"
        description="One query fans out across Scopus, OpenAlex, Semantic Scholar, Crossref, arXiv and DBLP, then duplicate records are merged DOI-first into a single result set."
      />

      <Card className="space-y-2 p-2.5">
        <form onSubmit={submit} className="space-y-2">
        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. graph neural networks for citation recommendation"
            aria-label="Search query"
            className="min-w-0 flex-1"
          />
          <div className="flex items-center gap-2">
            <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-slate-400">
              per source
              <Input
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value) || 10)}
                controlSize="sm"
                className="w-16"
              />
            </label>
            <Button type="submit" disabled={loading} className="flex-1 sm:flex-none">
              {loading ? (
                <>
                  <Spinner size="xs" />
                  Searching…
                </>
              ) : (
                "Search"
              )}
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
          <span className="font-medium uppercase tracking-wide">Sort</span>
          <Select
            value={sort}
            onChange={(event) =>
              setSort(event.target.value as "" | "citations" | "year" | "title")
            }
            aria-label="Sort results"
          >
            <option value="">Relevance</option>
            <option value="citations">Citations</option>
            <option value="year">Year</option>
            <option value="title">Title</option>
          </Select>
          <Button
            variant="ghost"
            onClick={() => setOrder((current) => (current === "asc" ? "desc" : "asc"))}
          >
            {order === "asc" ? "Ascending" : "Descending"}
          </Button>

          <Button
            variant={advancedOpen ? "accent" : "ghost"}
            onClick={() => setAdvancedOpen((current) => !current)}
            aria-expanded={advancedOpen}
            aria-controls="search-advanced"
            className="gap-1.5"
          >
            <SlidersIcon className="h-3.5 w-3.5 shrink-0" />
            Filters
            {activeFilterCount > 0 && (
              <span className="rounded bg-sky-400 px-1 text-[10px] font-semibold leading-4 text-slate-950">
                {activeFilterCount}
              </span>
            )}
            <ChevronDownIcon
              className={cn(
                "h-3.5 w-3.5 shrink-0 transition-transform",
                advancedOpen && "rotate-180",
              )}
            />
          </Button>

          <span className="flex-1" />
          <Link to="/history" className={LINK_CLASS}>
            Import file
          </Link>
        </div>

        {advancedOpen && (
          <div
            id="search-advanced"
            className="space-y-2.5 border-t border-slate-800 pt-2"
          >
            <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                Year from
                <Input
                  type="number"
                  min={1900}
                  max={2100}
                  value={yearFrom}
                  onChange={(event) => setYearFrom(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                Year to
                <Input
                  type="number"
                  min={1900}
                  max={2100}
                  value={yearTo}
                  onChange={(event) => setYearTo(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                Offset
                <Input
                  type="number"
                  min={0}
                  value={offset}
                  onChange={(event) => setOffset(event.target.value)}
                  placeholder="0"
                  controlSize="sm"
                />
              </label>
              <label className="flex h-8 items-center gap-1.5 self-end text-[11px] text-slate-300">
                <input
                  type="checkbox"
                  checked={techOnly}
                  onChange={(event) => setTechOnly(event.target.checked)}
                  className="h-3.5 w-3.5 accent-sky-500"
                />
                tech only
              </label>
            </div>

            <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                Affiliation
                <Input
                  value={affiliation}
                  onChange={(event) => setAffiliation(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                ISSN
                <Input
                  value={issn}
                  onChange={(event) => setIssn(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                ORCID
                <Input
                  value={orcid}
                  onChange={(event) => setOrcid(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                DOI
                <Input
                  value={doi}
                  onChange={(event) => setDoi(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
              <span className="mr-1 font-medium uppercase tracking-wide">Sources</span>
              {PROVIDERS.map((provider) => {
                const active = selectedSources.includes(provider);
                return (
                  <button
                    key={provider}
                    type="button"
                    onClick={() => toggleSource(provider)}
                    aria-pressed={active}
                    className={`touch-target rounded border px-2 py-0.5 text-[11px] transition-colors active:translate-y-px ${
                      active
                        ? "border-sky-400/60 bg-sky-400/15 text-sky-200"
                        : "border-slate-500 bg-slate-800/40 text-slate-300 hover:border-slate-400 hover:text-slate-100"
                    }`}
                  >
                    {provider}
                  </button>
                );
              })}
              {selectedSources.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedSources([])}
                  className="touch-target px-1 text-[11px] text-sky-400 underline-offset-2 hover:underline"
                >
                  all providers
                </button>
              )}
            </div>

            {activeFilterCount > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
                <span className="font-medium uppercase tracking-wide">Active</span>
                {yearFrom && <Chip className="tabular-nums">from {yearFrom}</Chip>}
                {yearTo && <Chip className="tabular-nums">to {yearTo}</Chip>}
                {offset && <Chip className="tabular-nums">offset {offset}</Chip>}
                {techOnly && <Chip>tech only</Chip>}
                {affiliation.trim() && <Chip>affiliation: {affiliation.trim()}</Chip>}
                {issn.trim() && <Chip>issn: {issn.trim()}</Chip>}
                {orcid.trim() && <Chip>orcid: {orcid.trim()}</Chip>}
                {doi.trim() && <Chip>doi: {doi.trim()}</Chip>}
                {selectedSources.map((source) => (
                  <Chip key={source}>{source}</Chip>
                ))}
                <Button variant="ghost" size="sm" onClick={resetFilters}>
                  Reset
                </Button>
              </div>
            )}
          </div>
        )}
        </form>
      </Card>

      {error && <Alert>{error}</Alert>}

      {loading && (
        <LoadingLine>Searching across providers, then merging duplicates…</LoadingLine>
      )}

      {data && (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip className="text-slate-200">
              {data.results.length} merged results
            </Chip>
            {Object.entries(data.counts || {}).map(([source, count]) => (
              <Chip key={source}>
                {source}: {count}
              </Chip>
            ))}
            {data.results.length > 0 && (
              <>
                <Chip>
                  {selectedIds.size > 0
                    ? `${selectedIds.size} selected`
                    : "none selected"}
                </Chip>
                <Button variant="ghost" onClick={selectAll}>
                  Select all
                </Button>
                <Button variant="ghost" onClick={selectCited}>
                  Select cited
                </Button>
                {selectedIds.size > 0 && (
                  <Button variant="ghost" onClick={clearSelection}>
                    Clear
                  </Button>
                )}
                <ExportMenu
                  papers={selectedIds.size > 0 ? selectedPapers : data.results}
                  selectedCount={selectedIds.size}
                  totalCount={data.results.length}
                />
              </>
            )}
          </div>

          {(data.filters_ignored?.length ?? 0) > 0 && (
            <Alert tone="warn">
              <strong>Filters ignored:</strong>{" "}
              {data.filters_ignored?.join(", ")}. Not every source honours these filters, so
              results may include records that do not match them.
            </Alert>
          )}

          {!warningsDismissed && (data.query_warnings?.length ?? 0) > 0 && (
            <Alert tone="warn" className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                {data.query_warnings?.map((warning, index) => (
                  <div key={`${warning.source}-${warning.operator}-${index}`}>
                    <strong>{warning.source}:</strong> {warning.message}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setWarningsDismissed(true)}
                className="touch-target shrink-0 text-[11px] text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
              >
                Dismiss
              </button>
            </Alert>
          )}

          {Object.keys(data.filters_applied || {}).length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
              <span className="font-medium uppercase tracking-wide">Filters applied</span>
              {Object.entries(data.filters_applied || {}).map(([provider, filters]) => (
                <Chip key={provider}>
                  {provider}: {filters.join(", ")}
                </Chip>
              ))}
            </div>
          )}

          {Object.keys(data.errors || {}).length > 0 && (
            <Alert tone="warn">
              {Object.entries(data.errors).map(([source, message]) => (
                <div key={source}>
                  <strong>{source}:</strong> {message}
                </div>
              ))}
            </Alert>
          )}

          {data.results.length === 0 ? (
            <p className="m-0 text-[13px] text-slate-400">No results.</p>
          ) : (
            <PaperTable
              rows={data.results.map((paper, index) => ({
                paper,
                key: paperKey(paper, index),
              }))}
              selectedIds={selectedIds}
              onToggle={toggleSelected}
              onOpen={setDrawerPaper}
              activeKey={drawerPaper ? paperKey(drawerPaper, data.results.indexOf(drawerPaper)) : null}
            />
          )}
        </div>
      )}

      <PaperDrawer paper={drawerPaper} onClose={() => setDrawerPaper(null)} />
    </div>
  );
}
