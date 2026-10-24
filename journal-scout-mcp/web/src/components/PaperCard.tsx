import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { fetchPaper } from "../lib/api";
import type { Paper } from "../lib/types";

function identifierFor(paper: Paper): string | null {
  if (paper.doi) return paper.doi;
  for (const key of ["openalex", "scopus", "semanticscholar", "crossref"]) {
    const value = paper.ids[key];
    if (value) return value;
  }
  return null;
}

export function PaperCard({ paper: initialPaper }: { paper: Paper }) {
  const [paper, setPaper] = useState(initialPaper);
  const [lookupState, setLookupState] = useState<"idle" | "loading" | "not-found" | "error">("idle");
  const identifier = identifierFor(paper);
  const canLookup = identifier !== null && !paper.pdf_url;

  async function handleFindOpenAccess() {
    if (!identifier) return;
    setLookupState("loading");
    try {
      const { paper: resolved } = await fetchPaper(identifier);
      if (resolved && (resolved.pdf_url || resolved.is_open_access === true)) {
        setPaper((prev) => ({
          ...prev,
          pdf_url: resolved.pdf_url ?? prev.pdf_url,
          is_open_access: resolved.is_open_access ?? prev.is_open_access,
        }));
        setLookupState("idle");
      } else {
        setLookupState("not-found");
      }
    } catch {
      setLookupState("error");
    } finally {
      setLookupState((state) => (state === "loading" ? "idle" : state));
    }
  }
  const authors =
    paper.authors.length > 4
      ? `${paper.authors.slice(0, 4).join(", ")} +${paper.authors.length - 4}`
      : paper.authors.join(", ");

  return (
    <article className="rounded-2xl border border-slate-800/80 bg-slate-900/30 p-5 transition-colors hover:border-slate-700">
      <div className="flex items-start justify-between gap-4">
        <h3 className="m-0 text-sm font-semibold leading-snug text-slate-100">
          {paper.title || "(untitled)"}
        </h3>
        {paper.citation_count != null && (
          <span className="shrink-0 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-300">
            {paper.citation_count} cited
          </span>
        )}
      </div>

      <p className="mb-2 mt-1.5 text-xs text-slate-400">
        {authors || "Unknown authors"}
        {paper.year ? ` · ${paper.year}` : ""}
        {paper.venue ? ` · ${paper.venue}` : ""}
      </p>

      {paper.abstract && (
        <p className="mb-3 line-clamp-3 text-xs leading-relaxed text-slate-500">
          {paper.abstract}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {paper.sources.map((source) => (
          <span
            key={source}
            className="rounded border border-slate-700 bg-slate-800/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400"
          >
            {source}
          </span>
        ))}
        {paper.is_open_access && (
          <span className="rounded border border-emerald-600/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-emerald-400">
            open access
          </span>
        )}

        <span className="flex-1" />

        {canLookup && (
          <button
            type="button"
            onClick={handleFindOpenAccess}
            disabled={lookupState === "loading"}
            className="rounded-md border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[11px] text-sky-300 no-underline hover:bg-sky-500/20 disabled:cursor-default disabled:opacity-60"
          >
            {lookupState === "loading" ? "Looking…" : "Find open-access copy"}
          </button>
        )}
        {lookupState === "not-found" && (
          <span className="text-[11px] text-slate-500">No open-access copy found</span>
        )}
        {lookupState === "error" && (
          <span className="text-[11px] text-rose-400">Lookup failed</span>
        )}

        {paper.pdf_url && (
          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-slate-700 px-2 py-1 text-[11px] text-slate-300 no-underline hover:border-slate-600 hover:text-slate-100"
          >
            PDF
          </a>
        )}
        {identifier && (
          <Link
            to="/graph"
            search={{ identifier }}
            className="rounded-md border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[11px] text-sky-300 no-underline hover:bg-sky-500/20"
          >
            Citation graph
          </Link>
        )}
      </div>
    </article>
  );
}
