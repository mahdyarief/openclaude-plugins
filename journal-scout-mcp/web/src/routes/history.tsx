import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { fetchSearches } from "../lib/api";
import type { SearchHistoryRow } from "../lib/types";
import {
  ALERT_ERROR,
  ALERT_WARN,
  CARD,
  CHIP,
  EYEBROW,
  GHOST_BTN,
  H1,
  LEDE,
  PAGE,
} from "../lib/ui";

const SEARCH_LIMIT = 20;

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString();
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
  }, []);

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

  return (
    <div className={PAGE}>
      <section className="space-y-3">
        <p className={EYEBROW}>Past queries</p>
        <h1 className={H1}>Search history</h1>
        <p className={LEDE}>
          Recent searches recorded by the server, newest first. Reload one to re-run it with the
          same query, sources and filters.
        </p>
      </section>

      {loading && <p className="text-sm text-slate-400">Loading history…</p>}

      {error && <div className={ALERT_ERROR}>{error}</div>}

      {!error && !loading && !persistent && (
        <div className={ALERT_WARN}>Riwayat tidak tersedia: penyimpanan Turso tidak aktif</div>
      )}

      {!error && !loading && persistent && rows.length === 0 && (
        <p className="text-sm text-slate-500">Belum ada pencarian</p>
      )}

      {rows.length > 0 && (
        <div className="space-y-3">
          {rows.map((row) => {
            const filters = filterEntries(row);
            return (
              <div
                key={row.id}
                className={`${CARD} history-row flex flex-col gap-3 p-4 sm:p-5`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <p className="m-0 break-words text-sm font-medium text-slate-100">
                      {row.query || "(empty query)"}
                    </p>
                    <p className="m-0 text-xs text-slate-500">
                      {formatTimestamp(row.created_at)}
                      {row.author ? ` · ${row.author}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => reload(row)}
                    className={`${GHOST_BTN} h-9 px-3 text-xs`}
                  >
                    Reload
                  </button>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span className={`${CHIP} text-slate-300`}>
                    {row.result_count} results
                  </span>
                  {(row.sources ?? []).map((source) => (
                    <span key={source} className={CHIP}>
                      {source}
                    </span>
                  ))}
                  {filters.map(([name, value]) => (
                    <span key={name} className={CHIP}>
                      {name}: {String(value)}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
