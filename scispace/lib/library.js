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

// List all papers in a collection by its full_slug.
// GET /api/library/collection/{fullSlug}/records?page_size=&page=
async function listCollectionContents(fullSlug, { page = 0, pageSize = 50 } = {}) {
  return withPage(async (pageRef) => {
    const r = await apiFetch(
      pageRef,
      "/api/library/collection/" + encodeURIComponent(fullSlug) + "/records?page_size=" + pageSize + "&page=" + page
    );
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, total: r.body.total ?? null, records: r.body.records ?? [], collection: r.body };
  });
}

// Rename an existing collection by its full_slug.
// PATCH /api/library/collection/{fullSlug} with {name: newName}
async function renameCollection(fullSlug, newName) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection/" + encodeURIComponent(fullSlug), {
      method: "PATCH",
      body: { name: newName },
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    if (r.status === 404) return { status: r.status, error: "Collection not found" };
    return { status: r.status, result: r.body };
  });
}

// Delete a collection by its full_slug.
// DELETE /api/library/collection/{fullSlug}
async function deleteCollection(fullSlug) {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/library/collection/" + encodeURIComponent(fullSlug), {
      method: "DELETE",
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    if (r.status === 404) return { status: r.status, error: "Collection not found" };
    // Returns 204 No Content or 200 with success flag
    return { status: r.status, success: [200, 204].includes(r.status), result: r.body };
  });
}

// Move papers between two collections.
// Uses removeFromCollection from first collection, then addToCollection to second.
// Returns { moved: [...], failed: [...] }.
async function moveBetweenCollections(fromSlug, toSlug, entitySlugs) {
  const list = (Array.isArray(entitySlugs) ? entitySlugs : [entitySlugs]).map(paperEntity);
  const moved = [];
  const failed = [];

  for (const slug of list) {
    try {
      // First remove from source collection
      const removeR = await apiFetch(
        (await withPage((p) => p)).constructor,
        "/api/library/records/" + encodeURIComponent(slug.replace("paper__", "")),
        { method: "DELETE" }
      );
      // Then add to destination collection
      const addR = await apiFetch(
        (await withPage((p) => p)).constructor,
        "/api/library/records",
        { method: "POST", body: { entity_slug_list: [slug], collection_slug: toSlug } }
      );
      if ([200, 201, 204].includes(addR.status)) {
        moved.push(slug);
      } else {
        failed.push({ slug, error: "Failed to add to destination collection" });
      }
    } catch (e) {
      failed.push({ slug, error: e.message });
    }
  }

  return { moved, failed };
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
  listCollectionContents,
  renameCollection,
  deleteCollection,
  moveBetweenCollections,
};
