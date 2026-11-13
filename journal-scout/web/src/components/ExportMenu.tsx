import { useState } from "react";
import { EXPORT_FORMATS, exportPapers } from "../lib/api";
import type { ExportFormat } from "../lib/api";
import type { Paper } from "../lib/types";
import { Button, Select } from "./ui";

const EXTENSIONS: Record<ExportFormat, string> = {
  bibtex: "bib",
  ris: "ris",
  csv: "csv",
  json: "json",
  endnote: "txt",
  isi: "txt",
  csv_header: "csv",
  apa: "txt",
  chicago: "txt",
  harvard: "txt",
  vancouver: "txt",
  mla: "txt",
  csiro: "txt",
  csv_bom: "csv",
  xls: "xls",
  csv_plain: "csv",
  xls_plain: "xls",
};

function saveText(text: string, filename: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
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

export function ExportMenu({
  papers,
  selectedCount = 0,
  totalCount = 0,
}: {
  papers: Paper[];
  selectedCount?: number;
  totalCount?: number;
}) {
  const [format, setFormat] = useState<ExportFormat>("bibtex");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const disabled = busy || papers.length === 0;
  const scope =
    selectedCount > 0
      ? `${selectedCount} selected`
      : totalCount > 0
        ? `all ${totalCount}`
        : `${papers.length}`;

  async function handleDownload() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const text = await exportPapers(papers, format);
      saveText(text, `papers.${EXTENSIONS[format]}`);
      setMessage(`Downloaded ${format} (${scope})`);
    } catch (exc) {
      setFailed(true);
      setMessage(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  async function handleCopy() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const text = await exportPapers(papers, format);
      await navigator.clipboard.writeText(text);
      setMessage(`Copied ${format}`);
    } catch {
      setFailed(true);
      setMessage("Copy failed. Use Download instead");
    } finally {
      setBusy(false);
    }
  }

  async function handleDetails() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const text = await exportPapers(papers, format);
      setPreview(text);
      setMessage(`Preview of ${format} (${scope})`);
    } catch (exc) {
      setFailed(true);
      setMessage(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <Select
          value={format}
          onChange={(event) => {
            setFormat(event.target.value as ExportFormat);
            setPreview(null);
          }}
          disabled={disabled}
          aria-label="Export format"
        >
          {EXPORT_FORMATS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
        <Button onClick={handleDownload} disabled={disabled}>
          {busy ? "Working…" : "Download"}
        </Button>
        <Button variant="ghost" onClick={handleCopy} disabled={disabled}>
          Copy
        </Button>
        <Button variant="ghost" onClick={handleDetails} disabled={disabled}>
          Details
        </Button>
        {message && (
          <span className={failed ? "text-[11px] text-red-300" : "text-[11px] text-slate-400"}>
            {message}
          </span>
        )}
      </div>
      {preview !== null && (
        <div className="rounded-md border border-slate-700 bg-slate-950/60">
          <div className="flex items-center justify-between border-b border-slate-700 px-2 py-1">
            <span className="text-[11px] text-slate-400">
              {format} preview · {preview.length} chars
            </span>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="touch-target text-[11px] text-slate-400 hover:text-slate-100"
            >
              Close
            </button>
          </div>
          <pre className="scroll-thin max-h-56 overflow-auto whitespace-pre-wrap px-2 py-1.5 text-[11px] text-slate-300">
            {preview || "(empty output)"}
          </pre>
        </div>
      )}
    </div>
  );
}
