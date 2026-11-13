import { Alert, Button, Chip, Input } from "../ui";
import { ExportMenu } from "../ExportMenu";
import { PaperTable } from "../PaperTable";
import { paperKey } from "../../lib/papers";
import type { SearchController } from "../../hooks/useSearchController";
import { QueryScopingPanel } from "./QueryScopingPanel";

export function SearchResults({ controller }: { controller: SearchController }) {
  const {
    data,
    selectedIds,
    selectAll,
    selectCited,
    clearSelection,
    selectedPapers,
    availableTopics,
    topicFilter,
    setTopicFilter,
    topicNeedle,
    visibleRows,
    results,
    warningsDismissed,
    setWarningsDismissed,
    toggleSelected,
    drawerPaper,
    setDrawerPaper,
  } = controller;

  return (
    <>
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

          {availableTopics.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
              <label className="flex items-center gap-1.5">
                <span className="font-medium uppercase tracking-wide">Topic</span>
                <Input
                  value={topicFilter}
                  onChange={(event) => setTopicFilter(event.target.value)}
                  placeholder="filter by topic…"
                  controlSize="sm"
                  className="w-48"
                  aria-label="Filter results by topic"
                />
              </label>
              {topicNeedle ? (
                <>
                  <Chip className="text-slate-200">
                    {visibleRows.length} of {results.length} match
                  </Chip>
                  <Button variant="ghost" size="sm" onClick={() => setTopicFilter("")}>
                    Clear
                  </Button>
                </>
              ) : (
                availableTopics.slice(0, 6).map(([topic, count]) => (
                  <button
                    key={topic}
                    type="button"
                    onClick={() => setTopicFilter(topic)}
                    className="touch-target rounded border border-slate-700 bg-slate-800/60 px-1.5 py-0.5 text-[10px] text-slate-300 transition-colors hover:border-sky-600 hover:text-sky-200"
                    title={`Filter by "${topic}" (${count})`}
                  >
                    {topic} <span className="text-slate-500">{count}</span>
                  </button>
                ))
              )}
            </div>
          )}

          {(data.filters_ignored?.length ?? 0) > 0 && (
            <Alert tone="warn">
              <strong>Filters ignored:</strong>{" "}
              {data.filters_ignored?.join(", ")}. Not every source honours these filters, so
              results may include records that do not match them.
            </Alert>
          )}

          <QueryScopingPanel scoping={data.query_scoping} />

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
          ) : visibleRows.length === 0 ? (
            <p className="m-0 text-[13px] text-slate-400">
              No results match the topic filter.
            </p>
          ) : (
            <PaperTable
              rows={visibleRows.map(({ paper, index }) => ({
                paper,
                key: paperKey(paper, index),
              }))}
              selectedIds={selectedIds}
              onToggle={toggleSelected}
              onOpen={setDrawerPaper}
              activeKey={
                drawerPaper
                  ? paperKey(
                      drawerPaper,
                      results.indexOf(drawerPaper),
                    )
                  : null
              }
            />
          )}
        </div>
      )}
    </>
  );
}
