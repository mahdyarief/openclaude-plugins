// lib/citations.js — citation generation & export via public Crossref APIs.
// No browser needed: these endpoints are open and CAPTCHA-free.
const { getTextWithRetry } = require("./extract.js");

// Generate a single citation for a DOI in the requested style.
//   style: "bibtex" (Crossref transform) | "apa" | "mla" | "chicago" | "harvard" (DataCite formatter)
async function exportCitation(doi, { style = "apa" } = {}) {
  if (style === "bibtex") {
    const citation = (
      await getTextWithRetry(
        "https://api.crossref.org/works/" + encodeURIComponent(doi) + "/transform/application/x-bibtex"
      )
    ).trim();
    return { format: "bibtex", doi, citation };
  }
  const styleMap = {
    apa: "apa",
    mla: "modern-language-association",
    chicago: "chicago-author-date",
    harvard: "harvard-cite-them-right",
  };
  const mapped = styleMap[style] || style;
  const url =
    "https://citation.crosscite.org/format?doi=" +
    encodeURIComponent(doi) +
    "&style=" +
    mapped +
    "&lang=en-US";
  const citation = (await getTextWithRetry(url)).trim();
  return { format: style, doi, citation };
}

// Bulk BibTeX export for a list of paper records (any records with a doi).
async function exportLibraryBibtex(records) {
  const list = Array.isArray(records) ? records : [];
  const entries = [];
  for (const r of list) {
    const doi = r.doi || (r.url && r.url.match(/doi\.org\/([^/?#]+)/i)?.[1]) || null;
    if (!doi) continue;
    try {
      const c = await exportCitation(doi, { style: "bibtex" });
      entries.push(c.citation);
    } catch (e) {
      entries.push("% " + (r.title || doi) + " — failed: " + e.message);
    }
  }
  return { format: "bibtex", entryCount: entries.length, bibtex: entries.join("\n\n") };
}

// Build a CSV export from a list of paper records.
async function exportLibraryCsv(records) {
  const escape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const header = ["title", "authors", "year", "journal", "doi", "url"].join(",");
  const rows = records.map((r) =>
    [
      escape(r.title),
      escape((r.authors || []).join("; ")),
      r.year ?? "",
      escape(r.journal),
      escape(r.doi),
      escape(r.url),
    ].join(",")
  );
  return { format: "csv", rowCount: records.length, csv: header + "\n" + rows.join("\n") };
}

module.exports = { exportCitation, exportLibraryCsv, exportLibraryBibtex };