// lib/review.js — literature-review column schema & deep review synthesis.
// Uses the same-origin API helper so every request carries session cookies + CSRF.
const { apiFetch, withPage, sessionExpired } = require("./api.js");

// Return the short 12-char unique ID from the end of a SciSpace entity slug.
// e.g. "climate-change-impacts-28ivps89p7i0" → "28ivps89p7i0"
function uniqueIdFromSlug(slug) {
  const parts = String(slug || "").split("-");
  return parts[parts.length - 1] || slug;
}

// Available comparison columns (what SciSpace can extract per paper).
async function getReviewColumns() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/paper-info/columns");
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    const generic = (r.body && r.body.generic && r.body.generic.data) || [];
    return {
      status: r.status,
      columns: generic.map((c) => ({
        key: c.key,
        displayName: c.display_name,
        isSelected: c.is_selected,
        isFixed: c.is_fixed,
      })),
    };
  });
}

// Deep review synthesis: extract comparison columns for a list of paper slugs.
// Uses the confirmed POST /api/paper-info/columns/bulk-data endpoint with the
// exact request shape captured from the live UI (unique_ids = 12-char suffixes).
//   slugs: array of full entity slugs like "climate-change-...-28ivps89p7i0"
//   columns: array of column keys from getReviewColumns (default: ["tldr"])
//   searchTerm: the original search query (used for context; optional)
//   modelVariant: "V1" (standard) | "V2" (premium) | "V3" (advanced)
async function deepReviewSynthesis(slugs, { columns, searchTerm, modelVariant, language } = {}) {
  const colList = Array.isArray(columns) && columns.length ? columns : ["tldr"];
  const uids = (Array.isArray(slugs) ? slugs : [slugs]).map(uniqueIdFromSlug);

  return withPage(async (page) => {
    const results = {};
    for (const key of colList) {
      const r = await apiFetch(page, "/api/paper-info/columns/bulk-data", {
        method: "POST",
        body: {
          key,
          search_term: searchTerm || "",
          language: language || "en",
          column_type: "GENERIC_COLUMN",
          entity_type: "PAPER",
          model_variant: modelVariant || "V1",
          unique_ids: uids,
        },
      });
      if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
      results[key] = { status: r.status, data: r.body };
    }
    return { status: 200, columnCount: colList.length, slugCount: slugs.length, results };
  });
}

module.exports = { getReviewColumns, deepReviewSynthesis };