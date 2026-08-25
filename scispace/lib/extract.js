// lib/extract.js — Paper extraction & enrichment via public scholarly APIs
// Crossref, OpenAlex, Semantic Scholar, Unpaywall
const { fetchWithRetry } = require("./api.js");
const { getCache, generateCacheKey, DEFAULT_TTL_EXTRACT } = require("./cache.js");

// Retry helper for external API calls with exponential backoff and jitter
async function getJsonWithRetry(url, options = {}, { baseDelayMs = 2000, maxRetries = 5, jitter = true } = {}) {
  let lastErr = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        if (response.status >= 500 && attempt < maxRetries) {
          // Transient server errors (5xx), retry
          await sleep(delayWithJitter(baseDelayMs, attempt, jitter));
          continue;
        }
        throw new Error("HTTP " + response.status);
      }
      return await response.json();
    } catch (e) {
      lastErr = e;
      if (attempt < maxRetries) {
        const delay = delayWithJitter(baseDelayMs, attempt, jitter);
        console.log(`[extract] Retry ${attempt + 1}/${maxRetries} after ${delay}ms: ${url}`);
        await sleep(delay);
      }
    }
  }

  throw lastErr || new Error("fetch failed: " + url);
}

function delayWithJitter(baseDelayMs, attempt, jitter = true) {
  const exponentialDelay = baseDelayMs * Math.pow(2, attempt);
  if (jitter) {
    // Add random jitter: 0.5x to 1.5x to avoid thundering herd
    return exponentialDelay * (0.5 + Math.random());
  }
  return exponentialDelay;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Extract DOIs from URLs or titles that contain them
function extractDoi(text) {
  const doiPattern = /10\.\d{4,9}\/[-._;()/:A-Z0-9]+/gi;
  const match = text.match(doiPattern);
  return match ? match[0] : null;
}

// Deep-extract a single paper by DOI from all available public sources
async function deepExtractPaper(doi) {
  const cleanDoi = doi.replace(/^doi:/i, "");
  const cacheKey = generateCacheKey({ type: "deep_extract", doi: cleanDoi });
  const cache = getCache();

  // Check cache first
  const cachedResult = cache.get(cacheKey);
  if (cachedResult) {
    return cachedResult;
  }

  // Perform deep extraction
  const result = await _performDeepExtract(cleanDoi);

  // Store in cache with long TTL
  cache.set(cacheKey, result, DEFAULT_TTL_EXTRACT);

  return result;
}

async function _performDeepExtract(doi) {
  const out = { doi, doiUrl: "https://doi.org/" + doi };

  try {
    // Crossref metadata
    const crossrefUrl = "https://api.crossref.org/works/" + encodeURIComponent(doi);
    const crossrefData = await getJsonWithRetry(crossrefUrl, {
      headers: { "Accept": "application/json" },
    }, { baseDelayMs: 2000, maxRetries: 5, jitter: true });

    out.title = crossrefData.message.title?.[0] || crossrefData.message.title;
    out.authors = crossrefData.message.author?.map(a => a.given + " " + a.family).join(", ") || "";
    out.year = crossrefData.message.published["print-parts"]?.[0]?.[0] || crossrefData.message.publisher;
    out.journal = crossrefData.message.container-title?.[0] || crossrefData.message["abstract-en"];
    out.crossrefUrl = crossrefUrl;

    // Resolve open-access PDF from Crossref
    if (crossrefData.message.link && Array.isArray(crossrefData.message.link)) {
      const pdfLink = crossrefData.message.link.find(l => l["content-type"] === "application/pdf");
      if (pdfLink && pdfLink["content-url"]) {
        out.accessibleUrls = [pdfLink["content-url"]];
      }
    }

    // OpenAlex API
    const openAlexUrl = "https://api.openalex.org/works/" + "https://openalex.org/W" + doi.replace(/\./g, "");
    const openAlexData = await getJsonWithRetry(openAlexUrl, {
      headers: { "Accept": "application/json" },
    }, { baseDelayMs: 2000, maxRetries: 5, jitter: true }).catch(e => {
      out.openAlexError = e.message;
      return null;
    });

    if (openAlexData) {
      out.openAlexId = openAlexData.id;
      out.citationCount = openAlexData.citation_count;
      out.doajOpenAccess = openAlexData.doi_url || openAlexData.open_access?.oapdf_url;
    }

    // Semantic Scholar API (TLEDR summary + citations)
    const semanticUrl = "https://api.semanticscholar.org/graph/v1/paper/DOI:" + doi;
    const semanticData = await getJsonWithRetry(semanticUrl, {
      headers: { "Accept": "application/json" },
    }, { baseDelayMs: 2000, maxRetries: 5, jitter: true }).catch(e => {
      out.semanticScholarError = e.message;
      return null;
    });

    if (semanticData) {
      out.tldr = semanticData.tldr;
      out.semanticCitationCount = semanticData.citationCount;
      if (semanticData.pdfUrls && semanticData.pdfUrls.length > 0) {
        out.semanticPdfUrl = semanticData.pdfUrls[0];
      }
    }

    // Unpaywall (best OA location)
    const unpaywallUrl = "https://api.unpaywall.org/v2/" + doi + "?key=public";
    const unpaywallData = await getJsonWithRetry(unpaywallUrl, {
      headers: { "Accept": "application/json" },
    }, { baseDelayMs: 2000, maxRetries: 5, jitter: true }).catch(e => {
      out.unpaywallError = e.message;
      return null;
    });

    if (unpaywallData) {
      out.bestOaLocation = unpaywallData.best_oa_location;
      if (unpaywallData.best_oa_location?.pdf_url) {
        out.accessibleUrls = out.accessibleUrls || [];
        out.accessibleUrls.unshift(unpaywallData.best_oa_location.pdf_url);
      }
    }

  } catch (e) {
    // If deep extraction had partial failures, surface them as warnings
    out.enrichWarning = e.message;
  }

  // Always add DOI resolver fallback URL that works without CAPTCHA
  if (!out.accessibleUrls) {
    out.accessibleUrls = [];
  }
  out.accessibleUrls.push("https://doi.org/" + doi);

  return out;
}

// Enrich papers from search results by extracting DOI and resolving accessible URLs
async function enrichPapers(papers, { maxDepth = 3 } = {}) {
  const enriched = [];

  for (let i = 0; i < papers.length; i++) {
    const entry = papers[i];
    const enrichedEntry = { ...entry };

    // Try to extract DOI from title/url
    const doiText = (entry.title + " " + entry.url).toLowerCase();
    const doi = extractDoi(doiText);

    if (doi) {
      enrichedEntry.doi = doi;

      // For first N papers, do full deep extraction
      if (i < maxDepth) {
        try {
          enrichedEntry.deepData = await deepExtractPaper(doi);
        } catch (e) {
          enrichedEntry.enrichWarning = e.message;
        }
      } else {
        // Quick DOI lookup only
        try {
          const quickUrl = "https://api.crossref.org/works/" + encodeURIComponent(doi);
          const data = await getJsonWithRetry(quickUrl, {
            headers: { "Accept": "application/json" },
          }, { baseDelayMs: 1000, maxRetries: 3, jitter: true });

          enrichedEntry.deepData = {
            title: data.message.title?.[0],
            authors: data.message.author?.map(a => a.given + " " + a.family).join(", "),
            year: data.message.published?.["print-parts"]?.[0]?.[0],
            journal: data.message.container-title?.[0],
          };
        } catch (e) {
          // Skip warning for quick lookup failures
        }
      }

      // Add DOI resolver URL
      enrichedEntry.accessibleUrls = enrichedEntry.accessibleUrls || [];
      enrichedEntry.accessibleUrls.push("https://doi.org/" + doi);
    }

    enriched.push(enrichedEntry);
  }

  return { papers: enriched, total: enriched.length };
}

module.exports = { extractDoi, deepExtractPaper, enrichPapers, getJsonWithRetry };
