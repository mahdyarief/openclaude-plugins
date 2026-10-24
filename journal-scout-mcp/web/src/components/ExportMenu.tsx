import { useState } from "react";
import { EXPORT_FORMATS, exportPapers } from "../lib/api";
import type { ExportFormat } from "../lib/api";
import type { Paper } from "../lib/types";
import { FIELD_SM, GHOST_BTN, PRIMARY_BTN } from "../lib/ui";

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

export function ExportMenu({ papers }: { papers: Paper[] }) {
  const [format, setFormat] = useState<ExportFormat>("bibtex");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const disabled = busy || papers.length === 0;

  async function handleDownload() {
    setBusy(true);
    setMessage(null);
    setFailed(false);
    try {
      const text = await exportPapers(papers, format);
      saveText(text, `papers.${EXTENSIONS[format]}`);
      setMessage(`Downloaded ${format}`);
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
      setMessage("Copy failed — use Download instead");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={format}
        onChange={(event) => setFormat(event.target.value as ExportFormat)}
        disabled={disabled}
        aria-label="Export format"
        className={`${FIELD_SM} h-9`}
      >
        {EXPORT_FORMATS.map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={handleDownload}
        disabled={disabled}
        className={PRIMARY_BTN}
      >
        {busy ? "Working…" : "Download"}
      </button>
      <button
        type="button"
        onClick={handleCopy}
        disabled={disabled}
        className={`${GHOST_BTN} disabled:cursor-not-allowed disabled:opacity-50`}
      >
        Copy
      </button>
      {message && (
        <span className={failed ? "text-xs text-red-400" : "text-xs text-slate-400"}>
          {message}
        </span>
      )}
    </div>
  );
}
