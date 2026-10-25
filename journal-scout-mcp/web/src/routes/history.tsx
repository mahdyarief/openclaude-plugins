import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  deleteSearch,
  duplicateSearch,
  fetchSearches,
  importPapers,
  importSearchArchive,
  importWorkspaceArchive,
  mergePapers,
  replaySearch,
  searchArchiveUrl,
  splitSearch,
  workspaceArchiveUrl,
} from "../lib/api";
import type { Paper, SearchArchive, SearchHistoryRow } from "../lib/types";
import {
  Alert,
  Button,
  Card,
  Chip,
  PageHeader,
  LoadingLine,
  Spinner,
  LINK_CLASS,
} from "../components/ui";

const SEARCH_LIMIT = 20;

function saveJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString();
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}

// The backend records all four filter keys, mostly as null, so drop empty ones.
function filterEntries(row: SearchHistoryRow): [string, string][] {
  return Object.entries(row.filters ?? {})
    .filter(([, value]) => typeof value === "string" && value.trim() !== "")
    .map(([key, value]) => [key, String(value)]);
}

export function HistoryPage() {
  const navigate = useNavigate({ from: "/history" });
  const [rows, setRows] = useState<SearchHistoryRow[]>([]);
  const [persistent, setPersistent] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [importResult, setImportResult] = useState<{ count: number; format: string } | null>(
    null,
  );
  const [replay, setReplay] = useState<{ id: string; query: string; papers: Paper[] } | null>(
    null,
  );
  const fileInput = useRef<HTMLInputElement | null>(null);
  const importFileInput = useRef<HTMLInputElement | null>(null);
  const workspaceFileInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSearches(SEARCH_LIMIT)
      .then((payload) => {
        if (cancelled) return;
        setRows(payload.searches ?? []);
        setPersistent(payload.persistent !== false);
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : String(exc));
        setRows([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  function toggleRow(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function fetchArchive(row: SearchHistoryRow): Promise<SearchArchive> {
    const response = await fetch(searchArchiveUrl(row.id));
    if (!response.ok) {
      throw new Error(`Could not export "${row.query}" (${response.status})`);
    }
    return (await response.json()) as SearchArchive;
  }

  async function exportArchive(row: SearchHistoryRow) {
    setBusy(`export:${row.id}`);
    setNotice(null);
    setError(null);
    try {
      saveJson(await fetchArchive(row), `search-${row.id}.json`);
      setNotice(`Exported archive for "${row.query}"`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function mergeSelected() {
    const selected = rows.filter((row) => selectedIds.has(row.id));
    if (selected.length === 0) return;
    setBusy("merge");
    setNotice(null);
    setError(null);
    try {
      const archives = await Promise.all(selected.map(fetchArchive));
      const papers = archives.flatMap((archive) => archive.results ?? []);
      if (papers.length === 0) {
        throw new Error(
          "The selected searches have no archived results. Searches recorded before archives were stored cannot be merged; re-run them to capture their results.",
        );
      }
      const merged = await mergePapers(papers);
      saveJson(
        {
          format: "josc-search-archive",
          version: 1,
          query: selected.map((row) => row.query).join(" OR "),
          author: null,
          sources: null,
          filters: null,
          created_at: Date.now() / 1000,
          results: merged.results,
        } satisfies SearchArchive,
        "merged-search.json",
      );
      setNotice(
        `Merged ${merged.input_count} papers into ${merged.merged_count} unique results`,
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function importArchive(file: File) {
    setBusy("import");
    setNotice(null);
    setError(null);
    try {
      const archive = JSON.parse(await file.text()) as SearchArchive;
      if (!Array.isArray(archive.results)) {
        throw new Error("Archive is missing a 'results' array.");
      }
      const imported = await importSearchArchive(archive);
      setNotice(`Imported ${imported.result_count} results`);
      setRefreshKey((key) => key + 1);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function importFile(file: File) {
    setBusy("import-file");
    setNotice(null);
    setError(null);
    setImportResult(null);
    try {
      const imported = await importPapers(await file.text(), undefined);
      setImportResult({ count: imported.count, format: imported.format });
      setNotice(`Imported ${imported.count} papers (format: ${imported.format})`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
      if (importFileInput.current) importFileInput.current.value = "";
    }
  }

  async function splitRow(row: SearchHistoryRow) {
    const raw = window.prompt(`Split "${row.query}" into chunks of how many results?`, "50");
    if (raw === null) return;
    const size = Number.parseInt(raw, 10);
    if (!Number.isFinite(size) || size < 1) {
      setError("Chunk size must be a whole number of at least 1.");
      return;
    }
    setBusy(`split:${row.id}`);
    setNotice(null);
    setError(null);
    try {
      const split = await splitSearch(row.id, size);
      setNotice(`Split into ${split.count} searches`);
      setRefreshKey((key) => key + 1);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function duplicateRow(row: SearchHistoryRow) {
    setBusy(`duplicate:${row.id}`);
    setNotice(null);
    setError(null);
    try {
      const copy = await duplicateSearch(row.id);
      setNotice(`Duplicated "${row.query}" as ${copy.id.slice(0, 8)}`);
      setRefreshKey((key) => key + 1);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function deleteRow(row: SearchHistoryRow) {
    const label = row.query || row.id;
    if (!window.confirm(`Delete the history entry "${label}"? This cannot be undone.`)) {
      return;
    }
    setBusy(`delete:${row.id}`);
    setNotice(null);
    setError(null);
    try {
      await deleteSearch(row.id);
      setSelectedIds((current) => {
        const next = new Set(current);
        next.delete(row.id);
        return next;
      });
      if (replay?.id === row.id) setReplay(null);
      setNotice(`Deleted "${label}"`);
      setRefreshKey((key) => key + 1);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function replayRow(row: SearchHistoryRow) {
    setBusy(`replay:${row.id}`);
    setNotice(null);
    setError(null);
    setReplay(null);
    try {
      const payload = await replaySearch(row.id);
      setReplay({ id: row.id, query: row.query, papers: payload.results ?? [] });
      setNotice(`Served ${payload.results?.length ?? 0} cached results (no network)`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function exportWorkspace() {
    setBusy("export-workspace");
    setNotice(null);
    setError(null);
    try {
      const response = await fetch(workspaceArchiveUrl());
      if (!response.ok) {
        throw new Error(`Could not export workspace (${response.status})`);
      }
      const archive = await response.json();
      saveJson(archive, "journal-scout-workspace.json");
      setNotice(`Exported ${archive.count ?? 0} searches`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }

  async function importWorkspace(file: File) {
    setBusy("import-workspace");
    setNotice(null);
    setError(null);
    try {
      const archive = JSON.parse(await file.text());
      if (!Array.isArray(archive.searches)) {
        throw new Error("Workspace archive is missing a 'searches' array.");
      }
      const imported = await importWorkspaceArchive(archive);
      setNotice(`Imported ${imported.count} searches`);
      setRefreshKey((key) => key + 1);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
      if (workspaceFileInput.current) workspaceFileInput.current.value = "";
    }
  }

  function reload(row: SearchHistoryRow) {
    const filters = (row.filters ?? {}) as Record<string, unknown>;
    const text = (value: unknown): string | undefined =>
      typeof value === "string" && value.trim() !== "" ? value : undefined;
    navigate({
      to: "/",
      search: {
        q: row.query,
        sources: row.sources?.length ? row.sources.join(",") : undefined,
        affiliation: text(filters.affiliation),
        issn: text(filters.issn),
        orcid: text(filters.orcid),
        doi: text(filters.doi),
      },
    });
  }

  // Opens the archived result set on the search page without re-running the
  // query, so the history table does not gain a duplicate row.
  function loadCached(row: SearchHistoryRow) {
    navigate({ to: "/", search: { cached: row.id } });
  }

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="Search history"
        description="Recent searches recorded by the server, newest first. Reload one to re-run it with the same query, sources and filters."
      />

      <div className="flex flex-wrap items-center gap-1.5">
        <Button
          variant="ghost"
          onClick={() => fileInput.current?.click()}
          disabled={busy !== null}
        >
          {busy === "import" ? (
            <>
              <Spinner size="xs" />
              Importing…
            </>
          ) : (
            "Import archive"
          )}
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importArchive(file);
          }}
        />
        <Button
          variant="ghost"
          onClick={() => importFileInput.current?.click()}
          disabled={busy !== null}
        >
          {busy === "import-file" ? (
            <>
              <Spinner size="xs" />
              Importing…
            </>
          ) : (
            "Import file"
          )}
        </Button>
        <input
          ref={importFileInput}
          type="file"
          accept=".ris,.bib,.bibtex,.enw,.csv,.txt,.ciw"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importFile(file);
          }}
        />
        <Button variant="ghost" onClick={exportWorkspace} disabled={busy !== null}>
          {busy === "export-workspace" ? (
            <>
              <Spinner size="xs" />
              Exporting…
            </>
          ) : (
            "Export workspace"
          )}
        </Button>
        <Button
          variant="ghost"
          onClick={() => workspaceFileInput.current?.click()}
          disabled={busy !== null}
        >
          {busy === "import-workspace" ? (
            <>
              <Spinner size="xs" />
              Importing…
            </>
          ) : (
            "Import workspace"
          )}
        </Button>
        <input
          ref={workspaceFileInput}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importWorkspace(file);
          }}
        />
        <Button
          onClick={mergeSelected}
          disabled={busy !== null || selectedIds.size === 0}
        >
          {busy === "merge" ? (
            <>
              <Spinner size="xs" />
              Merging…
            </>
          ) : (
            `Merge selected (${selectedIds.size})`
          )}
        </Button>
        {selectedIds.size > 0 && (
          <Button variant="ghost" onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        )}
      </div>

      {notice && <Alert tone="ok">{notice}</Alert>}

      {importResult && (
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-slate-400">
          <span>
            Imported {importResult.count} papers (format: {importResult.format})
          </span>
          <Link to="/" className={LINK_CLASS}>
            Go to search
          </Link>
        </div>
      )}

      {replay && (
        <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="m-0 text-[13px] text-slate-300">
              Cached results for "{replay.query}" · {replay.papers.length} papers
            </p>
            <button
              type="button"
              onClick={() => setReplay(null)}
              className="touch-target text-[11px] text-slate-400 hover:text-slate-100"
            >
              Close
            </button>
          </div>
          <ul className="scroll-thin mt-2 max-h-56 space-y-1 overflow-auto pl-4 text-[11px] text-slate-400">
            {replay.papers.slice(0, 50).map((paper, index) => (
              <li key={`${paper.doi ?? paper.title}-${index}`}>
                {paper.title}
                {paper.year ? ` (${paper.year})` : ""}
              </li>
            ))}
          </ul>
          {replay.papers.length > 50 && (
            <p className="mt-1 text-[11px] text-slate-400">
              Showing the first 50 of {replay.papers.length}.
            </p>
          )}
        </div>
      )}

      {loading && <LoadingLine>Loading history…</LoadingLine>}

      {error && <Alert>{error}</Alert>}

      {!error && !loading && !persistent && (
        <Alert tone="warn">
          History unavailable: persistent storage (Turso) is not configured.
        </Alert>
      )}

      {!error && !loading && persistent && rows.length === 0 && (
        <p className="m-0 text-[13px] text-slate-400">No searches recorded yet.</p>
      )}

      {rows.length > 0 && (
        <div className="space-y-2">
          {rows.map((row) => {
            const filters = filterEntries(row);
            return (
              <Card
                key={row.id}
                className={`history-row flex flex-col gap-1.5 p-2.5 ${
                  selectedIds.has(row.id) ? "border-sky-500/60 bg-sky-500/[0.07]" : ""
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-1.5">
                  <div className="flex min-w-0 items-start gap-1.5">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(row.id)}
                      onChange={() => toggleRow(row.id)}
                      aria-label={`Select search ${row.query || row.id}`}
                      className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-sky-500"
                    />
                    <div className="min-w-0">
                      <p className="m-0 break-words text-[13px] font-medium text-slate-100">
                        {row.query || "(empty query)"}
                      </p>
                      <p className="m-0 text-[11px] text-slate-400">
                        {formatTimestamp(row.created_at)}
                        {row.author ? ` · ${row.author}` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => exportArchive(row)}
                      disabled={busy !== null}
                    >
                      {busy === `export:${row.id}` ? (
                        <>
                          <Spinner size="xs" />
                          Exporting…
                        </>
                      ) : (
                        "Export"
                      )}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => reload(row)}>
                      Reload
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => splitRow(row)}
                      disabled={busy !== null}
                    >
                      {busy === `split:${row.id}` ? (
                        <>
                          <Spinner size="xs" />
                          Splitting…
                        </>
                      ) : (
                        "Split"
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => duplicateRow(row)}
                      disabled={busy !== null}
                    >
                      {busy === `duplicate:${row.id}` ? (
                        <>
                          <Spinner size="xs" />
                          Copying…
                        </>
                      ) : (
                        "Duplicate"
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => loadCached(row)}
                      disabled={busy !== null}
                    >
                      Load cached results
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => replayRow(row)}
                      disabled={busy !== null}
                    >
                      {busy === `replay:${row.id}` ? (
                        <>
                          <Spinner size="xs" />
                          Loading…
                        </>
                      ) : (
                        "Retry from cache"
                      )}
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => deleteRow(row)}
                      disabled={busy !== null}
                    >
                      {busy === `delete:${row.id}` ? (
                        <>
                          <Spinner size="xs" />
                          Deleting…
                        </>
                      ) : (
                        "Delete"
                      )}
                    </Button>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400">
                  <Chip className="tabular-nums text-slate-200">
                    {row.result_count} results
                  </Chip>
                  {typeof row.size_bytes === "number" && row.size_bytes > 0 && (
                    <Chip className="tabular-nums">
                      {(row.size_bytes / 1024).toFixed(1)} KB
                    </Chip>
                  )}
                  {typeof row.age_seconds === "number" && (
                    <Chip className="tabular-nums">{formatAge(row.age_seconds)}</Chip>
                  )}
                  {(row.sources ?? []).map((source) => (
                    <Chip key={source}>{source}</Chip>
                  ))}
                  {filters.map(([name, value]) => (
                    <Chip key={name}>
                      {name}: {String(value)}
                    </Chip>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
