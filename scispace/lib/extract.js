// lib/extract.js — deep paper extraction from public scholarly APIs.
// SciSpace paper detail pages are protected by an Amazon CAPTCHA, so instead
// of scraping them we enrich results from public metadata APIs (Crossref,
// OpenAlex, Semantic Scholar, Unpaywall) and resolve accessible URLs
// (open-access PDFs and the DOI resolver), which are always CAPTCHA-free.

const API_UA = "OpenClaudeScispace/1.0 (mailto:dy@users.noreply.github.com)";

// fetch wrapper with exponential backoff retry for rate limits (429) and
// transient server errors (5xx). Semantic Scholar throttles hard, so a small
// backoff here makes batch enrichment reliable instead of failing halfway.
async function getJsonWithRetry(url, { retries = 3, baseDelayMs = 800 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": API_UA } });
      if (r.ok) return await r.json();
      lastErr = new Error("HTTP " + r.status);
      if (r.status !== 429 && r.status < 500) throw lastErr; // 4xx (other than 429) won't recover
    } catch (e) {
      lastErr = e;
      if (!/HTTP (429|5\d\d)/.test(e.message)) throw e;
    }
    if (attempt < retries) {
      await new Promise((res) => setTimeout(res, baseDelayMs * 2 ** attempt));
    }
  }
  throw lastErr || new Error("fetch failed: " + url);
}

// Plain text fetch with the same retry behavior (for citations endpoints).
async function getTextWithRetry(url, { retries = 2, baseDelayMs = 500 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await fetch(url, { headers: { "User-Agent": API_UA } });
      if (r.ok) return await r.text();
      lastErr = new Error("HTTP " + r.status);
      if (r.status !== 429 && r.status < 500) throw lastErr;
    } catch (e) {
      lastErr = e;
      if (!/HTTP (429|5\d\d)/.test(e.message)) throw e;
    }
    if (attempt < retries) {
      await new Promise((res) => setTimeout(res, baseDelayMs * 2 ** attempt));
    }
  }
  throw lastErr || new Error("fetch failed: " + url);
}

function cleanAbstract(html) {
  return (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

// Extract a DOI from free text (paper context, URL, or an explicit DOI string).
function extractDoi(input) {
  const m = String(input || "").match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
  return m ? m[0].replace(/[.,;]+$/, "") : null;
}

// Fallback DOI resolution by title via Crossref bibliographic search.
// Used when a paper record has no DOI embedded in its title/url/context.
async function resolveDoiByTitle(title) {
  if (!title) return null;
  try {
    const url =
      "https://api.crossref.org/works?query.bibliographic=" +
      encodeURIComponent(title) +
      "&rows=1";
    const data = await getJsonWithRetry(url);
    const items = data && data.message && data.message.items;
    if (items && items.length && items[0].DOI) return items[0].DOI;
  } catch (e) {
    // Return null silently — enrichment can proceed without a DOI, but callers
    // should surface an enrichError field when they know the enrichment failed.
  }
  return null;
}

// Full deep extraction for one DOI: metadata + abstract + references from
// Crossref, citation/OA info from OpenAlex, TLDR/citations from Semantic
// Scholar, and a list of accessible URLs (PDF first, then DOI resolver).
async function deepExtractPaper(doi) {
  const out = { doi, doiUrl: "https://doi.org/" + doi, accessibleUrls: [] };

  // 1. Crossref — metadata, abstract, references
  try {
    const cr = (await getJsonWithRetry("https://api.crossref.org/works/" + encodeURIComponent(doi))).message;
    out.title = (cr.title || [""])[0];
    out.type = cr.type;
    out.journal = (cr["container-title"] || [""])[0];
    out.issn = cr.ISSN || [];
    out.publisher = cr.publisher;
    const pub = cr.published || cr["published-print"] || cr["published-online"];
    const parts = pub && pub["date-parts"] && pub["date-parts"][0];
    if (parts) {
      out.year = parts[0];
      out.month = parts[1] || null;
      out.day = parts[2] || null;
    }
    out.authors = (cr.author || []).map((a) =>
      [a.given, a.family].filter(Boolean).join(" ")
    );
    out.abstract = cleanAbstract(cr.abstract);
    out.references = (cr.reference || []).slice(0, 20).map((r) => ({
      doi: r.DOI || null,
      title: r["article-title"] || null,
      year: r["year"] || null,
      authors: r.author || null,
    }));
  } catch (e) {
    out.crossrefError = e.message;
  }

  // 2. OpenAlex — citation count, concepts, open-access status + PDF
  try {
    const oa = await getJsonWithRetry(
      "https://api.openalex.org/works/https://doi.org/" + encodeURIComponent(doi)
    );
    out.citationCount = oa.cited_by_count;
    out.concepts = (oa.concepts || []).slice(0, 5).map((c) => c.display_name);
    out.openAccess = oa.open_access;
    const pdfUrl = oa.best_oa_location && oa.best_oa_location.pdf_url;
    if (pdfUrl) out.accessibleUrls.push(pdfUrl);
  } catch (e) {
    out.openAlexError = e.message;
  }

  // 3. Semantic Scholar — TLDR, citation count, OA PDF
  try {
    const s2 = await getJsonWithRetry(
      "https://api.semanticscholar.org/graph/v1/paper/DOI:" +
        encodeURIComponent(doi) +
        "?fields=title,tldr,citationCount,openAccessPdf"
    );
    out.tldr = (s2.tldr && s2.tldr.text) || null;
    out.s2CitationCount = s2.citationCount;
    if (s2.openAccessPdf && s2.openAccessPdf.url) {
      out.accessibleUrls.push(s2.openAccessPdf.url);
    }
  } catch (e) {
    out.semanticScholarError = e.message;
  }

  // 4. Unpaywall — best OA location (fallback PDF source)
  try {
    const up = await getJsonWithRetry(
      "https://api.unpaywall.org/v2/" + encodeURIComponent(doi) + "?email=openclaude@example.com"
    );
    const loc = up.best_oa_location;
    if (loc && loc.url_for_pdf) out.accessibleUrls.push(loc.url_for_pdf);
    else if (loc && loc.url) out.accessibleUrls.push(loc.url);
  } catch (e) {
    out.unpaywallError = e.message;
  }

  // Dedupe accessible URLs, keep PDFs first, always include the DOI resolver.
  const seen = new Set();
  out.accessibleUrls = out.accessibleUrls.filter((u) => {
    if (!u || seen.has(u)) return false;
    seen.add(u);
    return true;
  });
  if (!out.accessibleUrls.length || !out.accessibleUrls.some((u) => /\.pdf($|\?)/i.test(u))) {
    out.accessibleUrls.push("https://doi.org/" + doi);
  }
  return out;
}

// Run async work over an array with limited concurrency (small worker pool).
async function mapWithConcurrency(items, concurrency, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  const poolSize = Math.min(concurrency, items.length || 1);
  await Promise.all(Array.from({ length: poolSize }, worker));
  return results;
}

// Enrich a list of papers (from search) with DOI + accessible URLs. The first
// maxDepth papers get a full deep extract (abstract, analytics); the rest just
// get DOI resolution. Enrichment runs in parallel (concurrency 3) so a batch of
// 10 papers completes in ~1/3 of the sequential time, with per-paper error
// capture and non-silent failure reporting.
async function enrichPapers(papers, { maxDepth = 3, concurrency = 3 } = {}) {
  const list = Array.isArray(papers) ? papers : [];
  const out = list.map((p) => ({ ...p, doi: extractDoi(p.title + " " + (p.url || "") + " " + (p.context || "")) }));

  await mapWithConcurrency(out, concurrency, async (entry, i) => {
    if (!entry.doi) {
      const doi = await resolveDoiByTitle(entry.title);
      if (!doi) {
        entry.enrichError = "No DOI found and title lookup failed";
        return;
      }
      entry.doi = doi;
    }
    try {
      if (i < maxDepth) {
        const deep = await deepExtractPaper(entry.doi);
        Object.assign(entry, {
          title: deep.title || entry.title,
          accessibleUrls: deep.accessibleUrls,
          abstract: deep.abstract,
          year: deep.year,
          journal: deep.journal,
          authors: deep.authors,
          citationCount: deep.citationCount,
          tldr: deep.tldr,
        });
        // If deep extraction had partial failures, surface them as warnings
        if (deep.crossrefError || deep.semanticScholarError || deep.unpaywallError) {
          entry.enrichWarnings = [deep.crossrefError, deep.semanticScholarError, deep.unpaywallError].filter(Boolean);
        }
      } else {
        // Shallow: just resolve a working URL (PDF via OpenAlex, else DOI resolver).
        let pdfUrl;
        try {
          const oa = await getJsonWithRetry(
            "https://api.openalex.org/works/https://doi.org/" + encodeURIComponent(entry.doi)
          );
          pdfUrl = oa.best_oa_location && oa.best_oa_location.pdf_url;
        } catch (e) {
          entry.enrichWarning = "OpenAlex PDF lookup failed";
        }
        entry.accessibleUrls = pdfUrl ? [pdfUrl, "https://doi.org/" + entry.doi] : ["https://doi.org/" + entry.doi];
      }
    } catch (e) {
      entry.enrichError = e.message;
    }
  });

  return out;
}

module.exports = { extractDoi, deepExtractPaper, enrichPapers, getJsonWithRetry, getTextWithRetry };