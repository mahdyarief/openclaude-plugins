// lib/utils.js — account credits & translation utilities via SciSpace internal API.
const { apiFetch, withPage, sessionExpired } = require("./api.js");

// Current credit balance / usage window from /api/meters/credits.
async function checkCredits() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/meters/credits");
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, credits: r.body };
  });
}

// Languages supported for SciSpace's in-app translation.
async function listTranslationLanguages() {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/translation/languages");
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, languages: r.body };
  });
}

// Check which model tiers the account can access for a given feature.
async function getModelAccess(kind = "literature-review") {
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/hooks/models/" + encodeURIComponent(kind));
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, models: r.body };
  });
}

module.exports = { checkCredits, listTranslationLanguages, getModelAccess };