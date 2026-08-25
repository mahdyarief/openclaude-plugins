// lib/citations.js — citation generation & export via public Crossref APIs.
// No browser needed: these endpoints are open and CAPTCHA-free.

const API_UA = "OpenClaudeScispace/1.0 (mailto:dy@users.noreply.github.com)";

async function getText(url) {
  const r = await fetch(url, { headers: { "User-Agent": API_UA } });
  if (!r.ok) throw new Error("HTTP " + r.status + " from " + url);
  return r.text();
}

// Generate a single citation for a DOI in the requested style.
//   style: "bibtex" (Crossref transform) | "apa" | "mla" | "chicago" | "harvard" (DataCite formatter)
async function exportCitation(doi, { style = "apa" } = {}) {
  if (style === "bibtex") {
    const citation = (
      await getText(
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
  const citation = (await getText(url)).trim();
  return { format: style, doi, citation };
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

module.exports = { exportCitation, exportLibraryCsv };
