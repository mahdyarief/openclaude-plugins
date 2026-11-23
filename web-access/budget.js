/**
 * Daily spend tracking and optional budgets.
 *
 *   "tavily": { "dailyCreditBudget": 100 }   // Tavily credits per UTC day
 *   "exa":    { "dailyBudgetUsd": 1.5 }      // Exa dollars per UTC day
 *
 * Spend is taken from what the APIs report (Tavily usage.credits, Exa
 * costDollars) and stored in the state file next to the config, so it is
 * shared between sessions and survives restarts. With the state file off it
 * is kept in memory. When a budget is reached, requests to that provider are
 * refused (search falls back to the other provider) until 00:00 UTC.
 */

const { loadConfig } = require("./config");
const { readStateFile, updateStateFile, stateFile } = require("./key-health");

class BudgetError extends Error {}

let _memory = null; // used when the state file is disabled

function today() {
  return new Date().toISOString().slice(0, 10);
}

function fresh() {
  return { date: today(), tavily: 0, exa: 0, tavilyRequests: 0, exaRequests: 0 };
}

function current() {
  const src = stateFile() ? readStateFile()?.spend : _memory;
  return src && src.date === today() ? { ...fresh(), ...src } : fresh();
}

/** Add spend for today. amount: Tavily credits or Exa dollars. */
function record(provider, amount) {
  const n = Number(amount);
  if (!Number.isFinite(n) || n < 0) return;
  const apply = (spend) => {
    const s = spend && spend.date === today() ? { ...fresh(), ...spend } : fresh();
    s[provider] = Math.round((s[provider] + n) * 1e6) / 1e6;
    s[`${provider}Requests`] += 1;
    return s;
  };
  if (stateFile()) updateStateFile((data) => (data.spend = apply(data.spend)));
  else _memory = apply(_memory);
}

function budgetFor(provider) {
  const cfg = loadConfig() || {};
  const v = provider === "tavily" ? cfg.tavily?.dailyCreditBudget : cfg.exa?.dailyBudgetUsd;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** Throws BudgetError when today's spend has reached the configured budget. */
function assertBudget(provider) {
  const budget = budgetFor(provider);
  if (budget === null) return;
  const spent = current()[provider];
  if (spent >= budget) {
    const unit = provider === "tavily" ? "credits" : "USD";
    const setting = provider === "tavily" ? "tavily.dailyCreditBudget" : "exa.dailyBudgetUsd";
    throw new BudgetError(
      `Daily ${provider === "tavily" ? "Tavily" : "Exa"} budget reached (${spent} / ${budget} ${unit} today). ` +
        `It resets at 00:00 UTC; raise ${setting} in web-access.json to continue.`
    );
  }
}

/** Summary for web_access_status. */
function describe(provider) {
  const s = current();
  const budget = budgetFor(provider);
  const unit = provider === "tavily" ? " credits" : "";
  const amount = provider === "exa" ? `$${s.exa.toFixed(4)}` : `${s.tavily}${unit}`;
  const of = budget === null ? "no daily budget" : `budget ${provider === "exa" ? `$${budget}` : `${budget}${unit}`}`;
  return `today (UTC): ${amount} over ${s[`${provider}Requests`]} request(s) · ${of}`;
}

module.exports = { record, assertBudget, describe, current, BudgetError };
