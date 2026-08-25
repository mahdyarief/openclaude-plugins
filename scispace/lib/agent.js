// lib/agent.js — SciSpace AI agent (threads & genius conversation) helpers.
// Thread listing uses GET /api/scispace-agent/threads (confirmed 200).
// Asking a question uses POST /api/genius/conversation (confirmed 200),
// which is the same backend the search page's "ask" UI hits.
const { apiFetch, withPage, sessionExpired } = require("./api.js");

// List existing AI-agent threads (pinned and regular) from the account.
async function listAgentThreads({ page = 0, pageSize = 20 } = {}) {
  return withPage(async (pageRef) => {
    const r = await apiFetch(
      pageRef,
      "/api/scispace-agent/threads?page_size=" + pageSize + "&page=" + page + "&is_pinned=false"
    );
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, total: r.body.total ?? null, threads: r.body.data ?? [] };
  });
}

// Ask a question to the SciSpace AI. entitySlugs are optional paper references;
// without them the question is asked in the general (search-table) context.
// searchTerm and globalInsightsSlug mirror the fields the search-page UI sends
// (captured from the related-questions request shape).
async function askPaper(question, { entitySlugs, entityType = "PAPER", searchTerm, globalInsightsSlug } = {}) {
  const body = { entity_type: entityType, question };
  if (Array.isArray(entitySlugs) && entitySlugs.length) {
    body.entity_slugs = entitySlugs.map((s) => (String(s).startsWith("paper__") ? s : "paper__" + s));
  }
  if (searchTerm) body.search_term = searchTerm;
  if (globalInsightsSlug) body.global_insights_slug = globalInsightsSlug;
  return withPage(async (page) => {
    const r = await apiFetch(page, "/api/genius/conversation", {
      method: "POST",
      body,
    });
    if (sessionExpired(r)) return { status: r.status, error: "Session expired — run scispace_login." };
    return { status: r.status, question, result: r.body };
  });
}

module.exports = { listAgentThreads, askPaper };