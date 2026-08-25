// scispace-client.js — aggregator: re-export all capabilities from lib/ modules.
// Kept as the single entry point so tools.js and external scripts keep working.
const { searchPapers } = require("./lib/search.js");
const { login, status } = require("./lib/auth.js");
const { extractDoi, deepExtractPaper, enrichPapers } = require("./lib/extract.js");

module.exports = { searchPapers, login, status, extractDoi, deepExtractPaper, enrichPapers };
