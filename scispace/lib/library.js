// lib/library.js — My Library management via SciSpace internal API.
// All calls run inside a logged-in browser page so session cookies apply,
// and every request carries the X-CSRFToken header (see lib/api.js).
const { apiFetch, withPage, sessionExpired } = require("./api.js");

// Normalize a paper reference to the "paper__<slug>" entity form the API expects
// (confirmed from the live network capture: /api/bookmark/list sends
// entity_slug_list like ["paper__climate-change-...-28ivps89p7i0"]).
function paperEntity(slug) {
  const s = String(slug || "");
  return s.startsWith("paper__") ? s : "paper__" + s;
}

// List saved paper records in My Library.
async function listLibrary() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/records");
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, total: r.body.total ?? null, records: r.body.data ?? [] };
  });
}

// List all collections (folders) in My Library.
async function listCollections() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection");
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, total: r.body.total ?? null, collections: r.body.data ?? [] };
  });
}

// Get the contents of a specific collection by its full_slug.
async function getCollection(fullSlug) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection/" + encodeURIComponent(fullSlug));
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, collection: r.body };
  });
}

// Create a new collection folder. Returns the created collection.
async function createCollection(name) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection", {
      method: "POST",
      body: { name },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, result: r.body };
  });
}

// Check bookmark status for one or more paper slugs (entity slug or full URL).
// POST /api/bookmark/list is what the SciSpace UI itself calls (confirmed 200).
async function listBookmarkStatus(entitySlugs) {
  const list = (Array.isArray(entitySlugs) ? entitySlugs : [entitySlugs]).map(paperEntity);
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/bookmark/list", {
      method: "POST",
      body: { entity_slug_list: list },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, result: r.body };
  });
}

// Add papers to a collection folder (by the collection's full_slug).
// Uses POST /api/library/records with entity_slug_list + collection_slug,
// matching the same pattern as the confirmed bookmark/list endpoint.
async function addToCollection(collectionSlug, entitySlugs) {
  const list = (Array.isArray(entitySlugs) ? entitySlugs : [entitySlugs]).map(paperEntity);
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/records", {
      method: "POST",
      body: { entity_slug_list: list, collection_slug: collectionSlug },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, result: r.body };
  });
}

// Remove papers from a collection folder.
// Uses DELETE /api/library/records/{entity_slug} (the detail route confirmed
// to exist from probes — 405 on POST means GET/DELETE are the allowed methods).
async function removeFromCollection(collectionSlug, entitySlugs) {
  const list = (Array.isArray(entitySlugs) ? entitySlugs : [entitySlugs]).map(paperEntity);
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/records/" + encodeURIComponent(list[0].replace("paper__", "")), {
      method: "DELETE",
      body: { collection_slug: collectionSlug },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, result: r.body };
  });
}

// Toggle a bookmark for a paper entity (by its /papers/ slug).
// Note: /api/bookmark/update returned 404 in live probes (both with and without
// the paper__ prefix), so this is best-effort — the confirmed read endpoint is
// listBookmarkStatus above.
async function bookmarkPaper(entitySlug, { bookmarked = true } = {}) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/bookmark/update", {
      method: "POST",
      body: { entity_slug: paperEntity(entitySlug), entity_type: "PAPER", is_bookmarked: bookmarked },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, result: r.body };
  });
}

module.exports = {
  listLibrary,
  listCollections,
  getCollection,
  createCollection,
  bookmarkPaper,
  listBookmarkStatus,
  addToCollection,
  removeFromCollection,
};
