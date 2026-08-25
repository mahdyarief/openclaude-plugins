// lib/extract.js — deep paper extraction from public scholarly APIs
// SciSpace paper detail pages are protected by an Amazon CAPTCHA, so instead
// of scraping them we enrich results from public metadata APIs (Crossref,
// OpenAlex, Semantic Scholar) and resolve accessible URLs (open-access PDFs
// and the DOI resolver), which are always reachable without a CAPTCHA.

const API_UA = "OpenClaudeScispace/1.0 (mailto:dy@users.noreply.github.com)";

async function getJson(url) {
  const r = await fetch(url, { headers: { "User-Agent": API_UA } });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

function cleanAbstract(html) {
  return (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

// Extract a DOI from free text (paper context, URL, or an explicit DOI string).
function extractDoi(input) {
  const m = String(input || "").match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
  return m ? m[0].replace(/[.,;]+$/, "") : null;
}

// Full deep extraction for one DOI: metadata + abstract + references from
// Crossref, citation/OA info from OpenAlex, TLDR/citations from Semantic
// Scholar, and a list of accessible URLs (PDF first, then DOI resolver).
async function deepExtractPaper(doi) {
  const out = { doi, doiUrl: "https://doi.org/" + doi, accessibleUrls: [] };

  // 1. Crossref — metadata, abstract, references
  try {
    const cr = (await getJson("https://api.crossref.org/works/" + encodeURIComponent(doi))).message;
    out.title = (cr.title || [""])[0];
    out.type = cr.type;
    out.journal = (cr["container-title"] || [""])[0];
    out.issn = cr.ISSN || [];
    out.publisher = cr.publisher;
    const pub = cr.published || cr["published-print"] || cr["published-online"] || {};
    out.published = pub["date-parts"] || null;
    out.volume = cr.volume;
    out.issue = cr.issue;
    out.page = cr.page;
    out.authors = (cr.author || []).map((a) => ((a.given || "") + " " + (a.family || "")).trim());
    out.abstract = cleanAbstract(cr.abstract);
    out.license = (cr.license || []).map((l) => l.URL).filter(Boolean);
    out.language = cr.language;
    out.refCount = (cr.reference || []).length;
    out.references = (cr.reference || []).slice(0, 10).map((r) => r["article-title"] || r.unstructured || r.DOI || "untitled");
  } catch (e) {
    out.crossrefError = e.message;
  }

  // 2. OpenAlex — citations, concepts, open-access status + PDF
  try {
    const oa = await getJson("https://api.openalex.org/works/doi:" + encodeURIComponent(doi));
    out.openAlex = {
      citedByCount: oa.cited_by_count,
      openAccess: oa.open_access
        ? { status: oa.open_access.oa_status, isOa: oa.open_access.is_oa, pdfUrl: oa.open_access.oa_url }
        : null,
      concepts: (oa.concepts || []).slice(0, 5).map((c) => c.display_name),
      keywords: (oa.keywords || []).slice(0, 6).map((k) => k.display_name),
      publicationYear: oa.publication_year,
    };
  } catch (e) {
    out.openAlexError = e.message;
  }

  // 3. Semantic Scholar — TLDR, citations, OA PDF
  try {
    const ss = await getJson(
      "https://api.semanticscholar.org/graph/v1/paper/DOI:" +
        encodeURIComponent(doi) +
        "?fields=title,citationCount,influentialCitationCount,fieldsOfStudy,tldr,openAccessPdf,venue,referenceCount"
    );
    out.semanticScholar = {
      citationCount: ss.citationCount,
      influentialCitationCount: ss.influentialCitationCount,
      fieldsOfStudy: ss.fieldsOfStudy || [],
      tldr: ss.tldr ? ss.tldr.text : null,
      openAccessPdf: ss.openAccessPdf ? ss.openAccessPdf.url : null,
      venue: ss.venue,
      referenceCount: ss.referenceCount,
    };
  } catch (e) {
    out.semanticScholarError = e.message;
  }

  // 4. Unpaywall — extra OA location (best_oa_location)
  try {
    const up = await getJson(
      "https://api.unpaywall.org/v2/" + encodeURIComponent(doi) + "?email=dy@users.noreply.github.com"
    );
    if (up.best_oa_location && up.best_oa_location.url) {
      out.unpaywall = { oaStatus: up.oa_status, pdfUrl: up.best_oa_location.url_for_pdf || up.best_oa_location.url };
    }
  } catch (e) {
    // Unpaywall is best-effort; ignore failures.
  }

  // Accessible URLs, PDF first, DOI resolver as the always-usable fallback.
  const seen = new Set();
  const pushUrl = (label, url) => {
    if (url && !seen.has(url)) {
      seen.add(url);
      out.accessibleUrls.push({ label, url });
    }
  };
  if (out.openAlex && out.openAlex.openAccess && out.openAlex.openAccess.pdfUrl) {
    pushUrl("PDF (OpenAlex)", out.openAlex.openAccess.pdfUrl);
  }
  if (out.semanticScholar && out.semanticScholar.openAccessPdf) {
    pushUrl("PDF (Semantic Scholar)", out.semanticScholar.openAccessPdf);
  }
  if (out.unpaywall && out.unpaywall.pdfUrl) {
    pushUrl("PDF (Unpaywall)", out.unpaywall.pdfUrl);
  }
  pushUrl("DOI resolver", out.doiUrl);
  if (out.accessibleUrls.length === 0) {
    pushUrl("DOI resolver", out.doiUrl);
  }

  return out;
}

// Batch enrichment: given search results (title + url + context), extract the
// DOI from each card and resolve an accessible URL (open-access PDF or DOI
// resolver) so every result has a URL that actually works without CAPTCHA.
async function enrichPapers(papers, { maxDepth = 3 } = {}) {
  const results = [];
  for (const p of papers) {
    const doi = extractDoi((p.context || "") + " " + (p.url || ""));
    const entry = {
      title: p.title,
      scispaceUrl: p.url || null,
      doi: doi || null,
      accessibleUrls: [],
    };
    if (doi) {
      entry.doiUrl = "https://doi.org/" + doi;
      entry.accessibleUrls.push({ label: "DOI resolver", url: entry.doiUrl });
    }
    // For the first few papers, also try to resolve a direct open-access PDF.
    if (doi && results.length < maxDepth) {
      try {
        const deep = await deepExtractPaper(doi);
        entry.journal = deep.journal;
        entry.authors = deep.authors;
        entry.published = deep.published;
        entry.abstract = deep.abstract ? deep.abstract.slice(0, 500) : null;
        entry.citedBy = deep.openAlex ? deep.openAlex.citedByCount : null;
        entry.accessType = deep.openAlex && deep.openAlex.openAccess ? deep.openAlex.openAccess.status : null;
        entry.tldr = deep.semanticScholar ? deep.semanticScholar.tldr : null;
        entry.accessibleUrls = deep.accessibleUrls.length ? deep.accessibleUrls : entry.accessibleUrls;
      } catch (e) {
        entry.enrichError = e.message;
      }
    }
    results.push(entry);
  }
  return results;
}

module.exports = { extractDoi, deepExtractPaper, enrichPapers };
