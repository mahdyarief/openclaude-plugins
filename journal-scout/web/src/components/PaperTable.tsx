import { useMemo, useState } from "react";
import type { Paper } from "../lib/types";
import { cn } from "./ui";
import { ChevronDownIcon } from "./icons";

export type SortKey = "year" | "title" | "authors" | "venue" | "type" | "citations";

export type PaperRow = { paper: Paper; key: string };

function authorSummary(authors: string[]): string {
  if (authors.length === 0) return "Unknown authors";
  if (authors.length <= 2) return authors.join(", ");
  return `${authors[0]} et al.`;
}

function compare(a: Paper, b: Paper, key: SortKey): number {
  switch (key) {
    case "year":
      return (a.year ?? 0) - (b.year ?? 0);
    case "citations":
      return (a.citation_count ?? 0) - (b.citation_count ?? 0);
    case "title":
      return (a.title || "").localeCompare(b.title || "");
    case "authors":
      return (a.authors[0] ?? "").localeCompare(b.authors[0] ?? "");
    case "venue":
      return (a.venue ?? "").localeCompare(b.venue ?? "");
    case "type":
      return (a.type ?? "").localeCompare(b.type ?? "");
  }
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
  className,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey | null;
  direction: "asc" | "desc";
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const active = activeKey === sortKey;
  return (
    <th
      scope="col"
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
      className={cn(
        "sticky top-0 z-10 border-b border-slate-800 bg-surface-alt px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "touch-target inline-flex items-center gap-1 uppercase tracking-wide transition-colors hover:text-slate-100",
          active && "text-sky-300",
        )}
      >
        {label}
        <ChevronDownIcon
          className={cn(
            "h-3 w-3 shrink-0 transition-transform",
            !active && "opacity-0",
            active && direction === "asc" && "rotate-180",
          )}
        />
      </button>
    </th>
  );
}

export function PaperTable({
  rows,
  selectedIds,
  onToggle,
  onOpen,
  activeKey,
}: {
  rows: PaperRow[];
  selectedIds: Set<string>;
  onToggle: (key: string) => void;
  onOpen: (paper: Paper) => void;
  activeKey?: string | null;
}) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [direction, setDirection] = useState<"asc" | "desc">("desc");

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDirection(
        key === "title" || key === "authors" || key === "venue" || key === "type"
          ? "asc"
          : "desc",
      );
    }
  }

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const result = compare(a.paper, b.paper, sortKey);
      return direction === "asc" ? result : -result;
    });
    return copy;
  }, [rows, sortKey, direction]);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full min-w-[980px] border-collapse text-[12px]">
        <caption className="sr-only">Search results</caption>
        <thead>
          <tr>
            <th scope="col" className="w-8 border-b border-slate-800 bg-surface-alt px-2 py-1.5">
              <span className="sr-only">Select</span>
            </th>
            <SortHeader
              label="Year"
              sortKey="year"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
              className="w-16"
            />
            <SortHeader
              label="Title"
              sortKey="title"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
            />
            <SortHeader
              label="Authors"
              sortKey="authors"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
              className="w-40"
            />
            <SortHeader
              label="Venue"
              sortKey="venue"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
              className="w-48"
            />
            <SortHeader
              label="Type"
              sortKey="type"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
              className="w-28"
            />
            <SortHeader
              label="Cited"
              sortKey="citations"
              activeKey={sortKey}
              direction={direction}
              onSort={handleSort}
              className="w-16 text-right"
            />
            <th
              scope="col"
              className="w-40 border-b border-slate-800 bg-surface-alt px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400"
            >
              Source
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ paper, key }) => {
            const selected = selectedIds.has(key);
            const isActive = activeKey === key;
            return (
              <tr
                key={key}
                tabIndex={0}
                onClick={() => onOpen(paper)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpen(paper);
                  }
                }}
                className={cn(
                  "cursor-pointer border-b border-slate-800/70 transition-colors last:border-b-0 focus-visible:outline focus-visible:outline-1 focus-visible:-outline-offset-2 focus-visible:outline-sky-400",
                  selected ? "bg-sky-500/[0.07]" : "hover:bg-slate-800/40",
                  isActive && "bg-slate-800/60 shadow-[inset_2px_0_0_0_var(--color-accent)]",
                )}
              >
                <td className="px-2 py-1.5 align-top" onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => onToggle(key)}
                    aria-label={`Select ${paper.title || "untitled"}`}
                    className="mt-0.5 h-3.5 w-3.5 accent-sky-500"
                  />
                </td>
                <td className="px-2 py-1.5 align-top tabular-nums text-slate-300">
                  {paper.year ?? "—"}
                </td>
                <td className="px-2 py-1.5 align-top">
                  <span className="line-clamp-2 font-medium leading-snug text-slate-100">
                    {paper.title || "(untitled)"}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-1">
                    {paper.is_retracted && (
                      <span className="rounded border border-rose-600/50 bg-rose-500/10 px-1 py-0.5 text-[10px] uppercase tracking-wide text-rose-300">
                        retracted
                      </span>
                    )}
                    {paper.is_open_access && (
                      <span className="rounded border border-emerald-600/40 bg-emerald-500/10 px-1 py-0.5 text-[10px] uppercase tracking-wide text-emerald-300">
                        open access
                      </span>
                    )}
                    {paper.topics?.[0] && (
                      <span
                        className="max-w-[16rem] truncate rounded border border-slate-700 bg-slate-800/60 px-1 py-0.5 text-[10px] text-slate-300"
                        title={paper.topics.join(", ")}
                      >
                        {paper.topics[0]}
                      </span>
                    )}
                  </span>
                </td>
                <td className="px-2 py-1.5 align-top text-slate-400">
                  <span className="line-clamp-2">{authorSummary(paper.authors)}</span>
                </td>
                <td className="px-2 py-1.5 align-top text-slate-400">
                  <span className="line-clamp-2">{paper.venue || "—"}</span>
                </td>
                <td className="px-2 py-1.5 align-top text-slate-400">
                  <span className="line-clamp-2">{paper.type || "—"}</span>
                </td>
                <td className="px-2 py-1.5 align-top text-right tabular-nums text-slate-200">
                  {paper.citation_count ?? "—"}
                  {paper.cited_by_percentile != null && (
                    <span
                      className="block text-[10px] font-normal text-slate-400"
                      title="Citation percentile within its field and year"
                    >
                      top {100 - paper.cited_by_percentile}%
                    </span>
                  )}
                </td>
                <td className="px-2 py-1.5 align-top">
                  <span className="flex flex-wrap gap-1">
                    {paper.sources.map((source) => (
                      <span
                        key={source}
                        className="rounded border border-slate-700 bg-slate-800/60 px-1 py-0.5 text-[10px] uppercase tracking-wide text-slate-300"
                      >
                        {source}
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
