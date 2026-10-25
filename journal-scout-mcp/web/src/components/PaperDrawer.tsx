import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { fetchPaper, fetchRelations } from "../lib/api";
import type { Paper } from "../lib/types";
import { useDialogFocus } from "../lib/useDialogFocus";
import { AnchorButton, Button, buttonClass, cn, LoadingLine, Spinner } from "./ui";
import { CloseIcon } from "./icons";

type RelationKind = "related" | "citations";

// Keys of ``Paper.ids`` whose value is only meaningful to the provider that
// produced it. A bare number is read as a CorpusId by Semantic Scholar, a PMID
// by PubMed, and a Scopus id by Scopus, so the drawer must name the owner.
const ID_SOURCES = [
  "openalex",
  "scopus",
  "semanticscholar",
  "crossref",
  "garuda",
  "arxiv",
  "pubmed",
  "dblp",
];

function identifierFor(paper: Paper): { identifier: string; source?: string } | null {
  if (paper.doi) return { identifier: paper.doi };
  for (const key of ID_SOURCES) {
    const value = paper.ids[key];
    if (value) return { identifier: value, source: key };
  }
  return null;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-2 border-b border-slate-800/60 py-1.5 last:border-b-0">
      <dt className="m-0 text-[11px] uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="m-0 min-w-0 break-words text-[12px] leading-relaxed text-slate-200">
        {children}
      </dd>
    </div>
  );
}

export function PaperDrawer({
  paper,
  onClose,
}: {
  paper: Paper | null;
  onClose: () => void;
}) {
  const [resolved, setResolved] = useState<Paper | null>(null);
  const [detailState, setDetailState] = useState<"idle" | "loading" | "error">("idle");
  const [copied, setCopied] = useState(false);
  const [openPanel, setOpenPanel] = useState<RelationKind | null>(null);
  const [relationState, setRelationState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [relations, setRelations] = useState<Paper[]>([]);
  const [relationError, setRelationError] = useState<string | null>(null);
  const relationRequest = useRef(0);
  const dialogRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setResolved(null);
    setDetailState("idle");
    setCopied(false);
    setOpenPanel(null);
    setRelationState("idle");
    setRelations([]);
    setRelationError(null);
    relationRequest.current += 1;
  }, [paper]);

  const open = paper !== null;
  useDialogFocus(open, dialogRef, onClose);
  const target = paper ? identifierFor(paper) : null;
  const detail = resolved ?? paper;
  const body = detail?.abstract ?? null;

  // One resolve fills both the abstract and a PDF link that the search result
  // did not carry, which is what the old "Find open-access copy" button did.
  async function loadDetail() {
    if (!target) return;
    setDetailState("loading");
    try {
      const { paper: fetched } = await fetchPaper(target.identifier, target.source);
      if (fetched) {
        setResolved(fetched);
        setDetailState("idle");
      } else {
        setDetailState("error");
      }
    } catch {
      setDetailState("error");
    }
  }

  async function toggleRelations(kind: RelationKind) {
    if (openPanel === kind) {
      setOpenPanel(null);
      return;
    }
    setOpenPanel(kind);
    if (!target) return;
    const current = relationRequest.current + 1;
    relationRequest.current = current;
    setRelationState("loading");
    setRelationError(null);
    try {
      const { results } = await fetchRelations(kind, target.identifier, target.source);
      if (relationRequest.current !== current) return;
      setRelations(results);
      setRelationState("ready");
    } catch (exc) {
      if (relationRequest.current !== current) return;
      setRelationError(exc instanceof Error ? exc.message : String(exc));
      setRelationState("error");
    }
  }

  async function copyDoi() {
    if (!detail?.doi) return;
    try {
      await navigator.clipboard.writeText(detail.doi);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      aria-hidden={!open}
      className={cn(
        "fixed inset-0 z-40 transition-opacity duration-200",
        open ? "opacity-100" : "pointer-events-none opacity-0",
      )}
    >
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Paper details"
        inert={!open}
        className={cn(
          "absolute right-0 top-0 flex h-dvh w-full max-w-[520px] flex-col border-l border-slate-800 bg-canvas shadow-2xl transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        {detail && (
          <>
            <header className="flex items-start gap-2 border-b border-slate-800 px-4 py-3">
              <h2 className="m-0 flex-1 text-[14px] font-semibold leading-snug text-slate-50">
                {detail.title || "(untitled)"}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close details"
                className="touch-target shrink-0 rounded p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </header>

            <div className="scroll-thin flex-1 overflow-y-auto px-4 py-3">
              <dl className="m-0">
                <Field label="Authors">
                  {detail.authors.length > 0 ? detail.authors.join(", ") : "Unknown authors"}
                </Field>
                <Field label="Year">{detail.year ?? "—"}</Field>
                <Field label="Venue">{detail.venue || "—"}</Field>
                <Field label="Type">{detail.type || "—"}</Field>
                <Field label="Cited">
                  {detail.citation_count != null ? detail.citation_count : "—"}
                </Field>
                <Field label="Sources">
                  <span className="flex flex-wrap gap-1">
                    {detail.sources.map((source) => (
                      <span
                        key={source}
                        className="rounded border border-slate-700 bg-slate-800/60 px-1 py-0.5 text-[10px] uppercase tracking-wide text-slate-300"
                      >
                        {source}
                      </span>
                    ))}
                    {detail.is_open_access && (
                      <span className="rounded border border-emerald-600/40 bg-emerald-500/10 px-1 py-0.5 text-[10px] uppercase tracking-wide text-emerald-300">
                        open access
                      </span>
                    )}
                  </span>
                </Field>
                <Field label="DOI">
                  {detail.doi ? (
                    <a
                      href={`https://doi.org/${detail.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400 no-underline hover:underline"
                    >
                      {detail.doi}
                    </a>
                  ) : (
                    "—"
                  )}
                </Field>
                <Field label="IDs">
                  {Object.keys(detail.ids).length > 0 ? (
                    <span className="flex flex-col gap-0.5">
                      {Object.entries(detail.ids).map(([key, value]) => (
                        <span key={key} className="text-[11px] text-slate-400">
                          <span className="uppercase tracking-wide">{key}</span>: {value}
                        </span>
                      ))}
                    </span>
                  ) : (
                    "—"
                  )}
                </Field>
              </dl>

              <section className="mt-4">
                <div className="flex items-center justify-between">
                  <h3 className="m-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                    Abstract
                  </h3>
                  {!body && target && (
                    <Button
                      variant="accent"
                      size="sm"
                      onClick={loadDetail}
                      disabled={detailState === "loading"}
                    >
                      {detailState === "loading" ? (
                        <>
                          <Spinner size="xs" />
                          Loading…
                        </>
                      ) : (
                        "Fetch details"
                      )}
                    </Button>
                  )}
                </div>
                {body ? (
                  <p className="mb-0 mt-1.5 whitespace-pre-wrap text-[12px] leading-relaxed text-slate-300">
                    {body}
                  </p>
                ) : (
                  <p className="mb-0 mt-1.5 text-[12px] text-slate-400">
                    {detailState === "error"
                      ? "No abstract available from the source."
                      : "No abstract in the search result."}
                  </p>
                )}
              </section>

              {target && (
                <section className="mt-4">
                  <div className="flex items-center justify-between gap-1.5">
                    <h3 className="m-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                      Related
                    </h3>
                    <span className="flex gap-1">
                      <Button
                        variant={openPanel === "related" ? "accent" : "ghost"}
                        size="sm"
                        onClick={() => toggleRelations("related")}
                        disabled={openPanel === "related" && relationState === "loading"}
                      >
                        {openPanel === "related" && relationState === "loading" ? (
                          <>
                            <Spinner size="xs" />
                            Loading…
                          </>
                        ) : (
                          "Related works"
                        )}
                      </Button>
                      <Button
                        variant={openPanel === "citations" ? "accent" : "ghost"}
                        size="sm"
                        onClick={() => toggleRelations("citations")}
                        disabled={openPanel === "citations" && relationState === "loading"}
                      >
                        {openPanel === "citations" && relationState === "loading" ? (
                          <>
                            <Spinner size="xs" />
                            Loading…
                          </>
                        ) : (
                          "Citing works"
                        )}
                      </Button>
                    </span>
                  </div>
                  {openPanel && (
                    <div className="mt-1.5 rounded-md border border-slate-800 bg-slate-950/60 px-2 py-1.5">
                      {relationState === "loading" && (
                        <LoadingLine className="text-[11px]">
                          Loading {openPanel === "related" ? "related works" : "citing works"}…
                        </LoadingLine>
                      )}
                      {relationState === "error" && (
                        <p className="m-0 text-[11px] text-rose-300">
                          {relationError ?? "Request failed"}
                        </p>
                      )}
                      {relationState === "ready" && relations.length === 0 && (
                        <p className="m-0 text-[11px] text-slate-400">No results.</p>
                      )}
                      {relationState === "ready" && relations.length > 0 && (
                        <ul className="m-0 list-none space-y-1 p-0">
                          {relations.slice(0, 10).map((item, index) => (
                            <li
                              key={`${item.doi ?? item.title}-${index}`}
                              className="text-[11px] leading-snug"
                            >
                              <span className="text-slate-200">{item.title || "(untitled)"}</span>
                              <span className="text-slate-400">
                                {[item.year, item.venue].filter(Boolean).join(" · ")}
                              </span>
                              {item.doi && (
                                <a
                                  href={`https://doi.org/${item.doi}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="ml-1 text-sky-400 no-underline hover:underline"
                                >
                                  DOI
                                </a>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </section>
              )}
            </div>

            <footer className="flex flex-wrap items-center gap-1.5 border-t border-slate-800 px-4 py-3">
              {detail?.pdf_url ? (
                <AnchorButton
                  href={detail.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download PDF
                </AnchorButton>
              ) : detail?.url ? (
                <AnchorButton href={detail.url} target="_blank" rel="noreferrer">
                  Open source page
                </AnchorButton>
              ) : null}
              {detail?.doi && (
                <Button variant="ghost" onClick={copyDoi}>
                  {copied ? "Copied" : "Copy DOI"}
                </Button>
              )}
              {target && (
                <Link
                  to="/graph"
                  search={{ identifier: target.identifier }}
                  className={buttonClass("ghost", "md")}
                >
                  Citation graph
                </Link>
              )}
            </footer>
          </>
        )}
      </aside>
    </div>
  );
}
