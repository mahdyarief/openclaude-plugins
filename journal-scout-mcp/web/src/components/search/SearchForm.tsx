import { Link } from "@tanstack/react-router";
import { ChevronDownIcon, SlidersIcon } from "../icons";
import type { SearchCondition, SearchField } from "../../lib/types";
import type { SearchController } from "../../hooks/useSearchController";
import {
  Button,
  Card,
  Chip,
  Input,
  Select,
  Spinner,
  LINK_CLASS,
  cn,
} from "../ui";

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

export function SearchForm({ controller }: { controller: SearchController }) {
  const {
    query,
    setQuery,
    limit,
    setLimit,
    sort,
    setSort,
    order,
    setOrder,
    advancedOpen,
    setAdvancedOpen,
    activeFilterCount,
    submit,
    yearFrom,
    setYearFrom,
    yearTo,
    setYearTo,
    offset,
    setOffset,
    techOnly,
    setTechOnly,
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
    selectedSources,
    setSelectedSources,
    toggleSource,
    conditions,
    addCondition,
    updateCondition,
    removeCondition,
    resetFilters,
    loading,
  } = controller;

  return (
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
              setSort(event.target.value as "relevance" | "citations" | "year" | "title")
            }
            aria-label="Sort results"
          >
            <option value="relevance">Relevance</option>
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
                Author
                <Input
                  value={author}
                  onChange={(event) => setAuthor(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-slate-400">
                Venue
                <Input
                  value={venue}
                  onChange={(event) => setVenue(event.target.value)}
                  placeholder="any"
                  controlSize="sm"
                />
              </label>
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

            <div className="space-y-1.5 border-t border-slate-800 pt-2">
              <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                <span className="font-medium uppercase tracking-wide">
                  Field filters
                </span>
                <span className="text-slate-500">
                  compiled per provider; unsupported fields degrade to free text
                </span>
                <Button variant="ghost" size="sm" onClick={addCondition}>
                  + condition
                </Button>
              </div>
              {conditions.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Optional. Add a field-scoped clause such as{" "}
                  <span className="text-slate-300">title contains "data quality"</span>{" "}
                  to search titles only where the provider supports it.
                </p>
              ) : (
                conditions.map((condition, index) => (
                  <div
                    key={index}
                    className="flex flex-wrap items-center gap-1.5"
                  >
                    {index > 0 ? (
                      <Select
                        value={condition.operator}
                        onChange={(event) =>
                          updateCondition(index, {
                            operator: event.target.value as SearchCondition["operator"],
                          })
                        }
                        aria-label={`Operator for condition ${index + 1}`}
                        className="w-20"
                      >
                        <option value="AND">AND</option>
                        <option value="OR">OR</option>
                        <option value="NOT">NOT</option>
                      </Select>
                    ) : (
                      <span className="w-20 text-[11px] text-slate-500">where</span>
                    )}
                    <Select
                      value={condition.field}
                      onChange={(event) =>
                        updateCondition(index, {
                          field: event.target.value as SearchField,
                        })
                      }
                      aria-label={`Field for condition ${index + 1}`}
                      className="w-32"
                    >
                      <option value="title">title</option>
                      <option value="abstract">abstract</option>
                      <option value="author">author</option>
                      <option value="venue">venue</option>
                      <option value="all">all fields</option>
                    </Select>
                    <Input
                      value={condition.value}
                      onChange={(event) =>
                        updateCondition(index, { value: event.target.value })
                      }
                      placeholder="value"
                      aria-label={`Value for condition ${index + 1}`}
                      controlSize="sm"
                      className="min-w-0 flex-1"
                    />
                    <button
                      type="button"
                      onClick={() => removeCondition(index)}
                      className="touch-target px-1 text-[11px] text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
                      aria-label={`Remove condition ${index + 1}`}
                    >
                      remove
                    </button>
                  </div>
                ))
              )}
            </div>

            {activeFilterCount > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-800 pt-2 text-[11px] text-slate-400">
                <span className="font-medium uppercase tracking-wide">Active</span>
                {yearFrom && <Chip className="tabular-nums">from {yearFrom}</Chip>}
                {yearTo && <Chip className="tabular-nums">to {yearTo}</Chip>}
                {offset && <Chip className="tabular-nums">offset {offset}</Chip>}
                {techOnly && <Chip>tech only</Chip>}
                {author.trim() && <Chip>author: {author.trim()}</Chip>}
                {venue.trim() && <Chip>venue: {venue.trim()}</Chip>}
                {affiliation.trim() && <Chip>affiliation: {affiliation.trim()}</Chip>}
                {issn.trim() && <Chip>issn: {issn.trim()}</Chip>}
                {orcid.trim() && <Chip>orcid: {orcid.trim()}</Chip>}
                {doi.trim() && <Chip>doi: {doi.trim()}</Chip>}
                {conditions
                  .filter((condition) => condition.value.trim() !== "")
                  .map((condition, index) => (
                    <Chip key={`${condition.field}-${index}`}>
                      {condition.field}: {condition.value.trim()}
                    </Chip>
                  ))}
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
  );
}
