import { useEffect, useRef, useState } from "react";
import { useSearch } from "@tanstack/react-router";
import { downloadPdf, type PdfDownload } from "../lib/api";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Chip,
  Label,
  PageHeader,
  Spinner,
  ToggleGroup,
  ToggleGroupItem,
  cn,
} from "../components/ui";

const MAX_ITEMS = 25;
const CONCURRENCY = 2;

type ScinetMode = "default" | "on" | "off";

type Row = {
  identifier: string;
  state: "queued" | "loading" | "ready" | "error";
  result?: PdfDownload;
  objectUrl?: string;
  error?: string;
};

/** One identifier per line (or comma/space separated); doi.org links and `doi:` are accepted. */
export function parseIdentifiers(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split(/[\s,;]+/)) {
    const value = raw
      .trim()
      .replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")
      .replace(/^doi:/i, "")
      .replace(/[.)\]]+$/, "");
    if (!value) continue;
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(value);
  }
  return out;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function saveBlob(url: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

const SOURCE_LABEL: Record<string, string> = {
  open_access: "Open access",
  arxiv: "arXiv",
  crossref: "Crossref link",
  landing: "Publisher page",
  acm: "ACM DL",
  nejm_ai: "NEJM AI",
  peerj: "PeerJ",
  scinet: "Sci-Net",
};

export function PdfPage() {
  const { doi } = useSearch({ from: "/pdf" });
  const [text, setText] = useState(doi ?? "");
  const [scinet, setScinet] = useState<ScinetMode>("default");
  const [autoSave, setAutoSave] = useState(true);
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const urlsRef = useRef<string[]>([]);

  // Free the in-memory PDFs when the page goes away.
  useEffect(
    () => () => {
      abortRef.current?.abort();
      urlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );

  const identifiers = parseIdentifiers(text);

  function update(index: number, patch: Partial<Row>) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (running || identifiers.length === 0) return;
    const batch = identifiers.slice(0, MAX_ITEMS);
    setNotice(
      identifiers.length > MAX_ITEMS
        ? `Only the first ${MAX_ITEMS} identifiers are fetched per run.`
        : null,
    );
    urlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    urlsRef.current = [];
    setRows(batch.map((identifier) => ({ identifier, state: "queued" })));

    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    const scinetFlag = scinet === "default" ? undefined : scinet === "on";
    let next = 0;

    async function worker() {
      while (next < batch.length && !controller.signal.aborted) {
        const index = next++;
        update(index, { state: "loading" });
        try {
          const result = await downloadPdf(batch[index], {
            scinet: scinetFlag,
            signal: controller.signal,
          });
          const objectUrl = URL.createObjectURL(result.blob);
          urlsRef.current.push(objectUrl);
          update(index, { state: "ready", result, objectUrl });
          if (autoSave) saveBlob(objectUrl, result.filename);
        } catch (exc) {
          if (controller.signal.aborted) {
            update(index, { state: "error", error: "Cancelled." });
            continue;
          }
          update(index, {
            state: "error",
            error: exc instanceof Error ? exc.message : String(exc),
          });
        }
      }
    }

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    setRows((current) =>
      current.map((row) =>
        row.state === "queued" ? { ...row, state: "error", error: "Cancelled." } : row,
      ),
    );
    setRunning(false);
    abortRef.current = null;
  }

  const ready = rows.filter((row) => row.state === "ready").length;
  const failed = rows.filter((row) => row.state === "error").length;

  return (
    <div className="w-full space-y-5">
      <PageHeader
        title="PDF download"
        description="Paste DOIs or arXiv ids, one per line. Each is resolved through open-access links, Crossref, the publisher's landing page, known publisher patterns and, when enabled, Sci-Net; the first real PDF is downloaded to your computer."
      />

      <Card className="space-y-2 p-2.5">
        <form onSubmit={submit} className="space-y-2">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            spellCheck={false}
            placeholder={"10.1016/j.cosrev.2026.101054\nhttps://doi.org/10.1145/3637870\n2401.12345"}
            aria-label="DOIs or arXiv ids, one per line"
            className="scroll-thin w-full resize-y rounded-md border border-slate-500 bg-slate-950/60 px-3 py-2 font-mono text-[13px] text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus-visible:border-sky-400 focus-visible:ring-2 focus-visible:ring-sky-400/25"
          />

          <div className="flex flex-col gap-2 border-t border-slate-800 pt-2 sm:flex-row sm:flex-wrap sm:items-center">
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
              <span className="font-medium uppercase tracking-wide">Sci-Net</span>
              <ToggleGroup
                type="single"
                value={scinet}
                onValueChange={(value) => {
                  if (value) setScinet(value as ScinetMode);
                }}
                className="text-[11px]"
              >
                <ToggleGroupItem value="default">Server default</ToggleGroupItem>
                <ToggleGroupItem value="on">On</ToggleGroupItem>
                <ToggleGroupItem value="off">Off</ToggleGroupItem>
              </ToggleGroup>
            </div>

            <div className="flex items-center gap-1.5">
              <Checkbox
                id="pdf-autosave"
                checked={autoSave}
                onCheckedChange={(value) => setAutoSave(value === true)}
              />
              <Label htmlFor="pdf-autosave" className="text-[12px] text-slate-300">
                Save each PDF as soon as it is ready
              </Label>
            </div>

            <div className="flex items-center gap-2 sm:ml-auto">
              <span className="text-[11px] tabular-nums text-slate-400">
                {identifiers.length} identifier{identifiers.length === 1 ? "" : "s"}
              </span>
              {running && (
                <Button variant="ghost" onClick={() => abortRef.current?.abort()}>
                  Cancel
                </Button>
              )}
              <Button type="submit" disabled={running || identifiers.length === 0}>
                {running ? (
                  <>
                    <Spinner size="xs" />
                    Fetching…
                  </>
                ) : (
                  "Get PDF"
                )}
              </Button>
            </div>
          </div>
        </form>
      </Card>

      {notice && <Alert tone="warn">{notice}</Alert>}

      {rows.length > 0 && (
        <section className="space-y-2">
          <h2 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Results{" "}
            <span className="font-normal normal-case tracking-normal tabular-nums">
              · {ready} ready{failed ? ` · ${failed} failed` : ""}
            </span>
          </h2>
          <Card className="divide-y divide-slate-800/70">
            {rows.map((row) => (
              <div
                key={row.identifier}
                className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="m-0 truncate font-mono text-[12.5px] text-slate-200">
                    {row.identifier}
                  </p>
                  {row.result?.title && (
                    <p className="m-0 line-clamp-2 text-[13px] leading-snug text-slate-300">
                      {row.result.title}
                    </p>
                  )}
                  {row.state === "error" && (
                    <p className="m-0 text-[12px] leading-snug text-red-300">{row.error}</p>
                  )}
                  {row.result && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      {row.result.source && (
                        <Chip
                          className={cn(
                            row.result.source === "scinet" &&
                              "border-amber-500/40 bg-amber-500/10 text-amber-200",
                          )}
                          title={row.result.pdfUrl ?? undefined}
                        >
                          {SOURCE_LABEL[row.result.source] ?? row.result.source}
                        </Chip>
                      )}
                      {row.result.via && <Chip variant="outline">via {row.result.via}</Chip>}
                      <span className="text-[11px] tabular-nums text-slate-400">
                        {formatSize(row.result.blob.size)} · {row.result.filename}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {(row.state === "queued" || row.state === "loading") && (
                    <span className="flex items-center gap-1.5 text-[12px] text-slate-400">
                      {row.state === "loading" ? <Spinner size="xs" /> : null}
                      {row.state === "loading" ? "Fetching…" : "Queued"}
                    </span>
                  )}
                  {row.state === "ready" && row.objectUrl && row.result && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(row.objectUrl, "_blank", "noopener")}
                      >
                        Open
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => saveBlob(row.objectUrl!, row.result!.filename)}
                      >
                        Save PDF
                      </Button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </Card>
          {rows.some((row) => row.result?.source === "scinet") && (
            <p className="m-0 text-[11px] leading-relaxed text-slate-400">
              Sci-Net copies are hosted outside the publisher's licence.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
