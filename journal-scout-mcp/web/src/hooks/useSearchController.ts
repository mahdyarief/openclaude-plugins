import { useEffect, useMemo, useState } from "react";
import { useSearch } from "@tanstack/react-router";
import { replaySearch, searchPapers, type SearchOptions } from "../lib/api";
import { paperKey } from "../lib/papers";
import type { Paper, SearchCondition, SearchResponse } from "../lib/types";

export type SearchSort = "relevance" | "citations" | "year" | "title";
export type SearchOrder = "asc" | "desc";

function splitSources(value: string | undefined): string[] {
  return value
    ? value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item !== "")
    : [];
}

export function useSearchController() {
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
  const [author, setAuthor] = useState(params.author ?? "");
  const [venue, setVenue] = useState(params.venue ?? "");
  const [affiliation, setAffiliation] = useState(params.affiliation ?? "");
  const [issn, setIssn] = useState(params.issn ?? "");
  const [orcid, setOrcid] = useState(params.orcid ?? "");
  const [doi, setDoi] = useState(params.doi ?? "");
  const [conditions, setConditions] = useState<SearchCondition[]>([]);
  const [topicFilter, setTopicFilter] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<"relevance" | "citations" | "year" | "title">("relevance");
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
    setAuthor("");
    setVenue("");
    setAffiliation("");
    setIssn("");
    setOrcid("");
    setDoi("");
    setSelectedSources([]);
    setTopicFilter("");
    setConditions([]);
  }

  // Counts only the advanced filters, so the badge on the Filters button
  // tells the user what is hiding behind the collapsed panel.
  const activeFilterCount =
    (yearFrom ? 1 : 0) +
    (yearTo ? 1 : 0) +
    (offset ? 1 : 0) +
    (techOnly ? 1 : 0) +
    (author.trim() ? 1 : 0) +
    (venue.trim() ? 1 : 0) +
    (affiliation.trim() ? 1 : 0) +
    (issn.trim() ? 1 : 0) +
    (orcid.trim() ? 1 : 0) +
    (doi.trim() ? 1 : 0) +
    selectedSources.length +
    conditions.filter((condition) => condition.value.trim() !== "").length;

  async function run(term: string, options: SearchOptions) {
    const hasConditions = (options.conditions ?? []).some(
      (condition) => condition.value.trim() !== "",
    );
    if (!term && !hasConditions) return;
    setLoading(true);
    setError(null);
    setSelectedIds(new Set());
    setTopicFilter("");
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

  function addCondition() {
    setConditions((current) => [
      ...current,
      { field: "title", value: "", operator: "AND" },
    ]);
  }

  function updateCondition(index: number, patch: Partial<SearchCondition>) {
    setConditions((current) =>
      current.map((condition, position) =>
        position === index ? { ...condition, ...patch } : condition,
      ),
    );
  }

  function removeCondition(index: number) {
    setConditions((current) =>
      current.filter((_, position) => position !== index),
    );
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
      author: author.trim() || undefined,
      venue: venue.trim() || undefined,
      affiliation: affiliation.trim() || undefined,
      issn: issn.trim() || undefined,
      orcid: orcid.trim() || undefined,
      doi: doi.trim() || undefined,
      sort: sort || undefined,
      order,
      conditions: conditions.filter(
        (condition) => condition.value.trim() !== "",
      ),
    });
  }

  const results = data?.results ?? [];
  const selectedPapers = results.filter((paper, index) =>
    selectedIds.has(paperKey(paper, index)),
  );

  // Topic vocabularies differ per provider, so this filter runs locally on the
  // merged set. It never issues another request: changing it is instant.
  const availableTopics = useMemo(() => {
    const counts = new Map<string, number>();
    for (const paper of results) {
      for (const topic of paper.topics ?? []) {
        const value = topic.trim();
        if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
      }
    }
    return [...counts.entries()].sort(
      (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
    );
  }, [results]);

  const topicNeedle = topicFilter.trim().toLowerCase();
  const visibleRows = useMemo(() => {
    const indexed = results.map((paper, index) => ({ paper, index }));
    if (!topicNeedle) return indexed;
    return indexed.filter(({ paper }) =>
      (paper.topics ?? []).some((topic) =>
        topic.toLowerCase().includes(topicNeedle),
      ),
    );
  }, [results, topicNeedle]);

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

  return {
    query,
    setQuery,
    limit,
    setLimit,
    yearFrom,
    setYearFrom,
    yearTo,
    setYearTo,
    techOnly,
    setTechOnly,
    selectedSources,
    setSelectedSources,
    offset,
    setOffset,
    author,
    setAuthor,
    venue,
    setVenue,
    affiliation,
    setAffiliation,
    issn,
    setIssn,
    orcid,
    setOrcid,
    doi,
    setDoi,
    conditions,
    topicFilter,
    setTopicFilter,
    data,
    loading,
    error,
    selectedIds,
    sort,
    setSort,
    order,
    setOrder,
    warningsDismissed,
    setWarningsDismissed,
    advancedOpen,
    setAdvancedOpen,
    drawerPaper,
    setDrawerPaper,
    toggleSelected,
    selectAll,
    selectCited,
    clearSelection,
    toggleSource,
    resetFilters,
    activeFilterCount,
    addCondition,
    updateCondition,
    removeCondition,
    submit,
    results,
    selectedPapers,
    availableTopics,
    topicNeedle,
    visibleRows,
  };
}

export type SearchController = ReturnType<typeof useSearchController>;
