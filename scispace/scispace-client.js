// scispace-client.js — aggregator: re-export all capabilities from lib/ modules.
// Kept as the single entry point so tools.js and external scripts keep working.
const { searchPapers } = require("./lib/search.js");
const { login, status } = require("./lib/auth.js");
const { extractDoi, deepExtractPaper, enrichPapers } = require("./lib/extract.js");
const { listLibrary, listCollections, getCollection, createCollection, bookmarkPaper } = require("./lib/library.js");
const { exportCitation, exportLibraryCsv } = require("./lib/citations.js");
const { checkCredits, listTranslationLanguages, getModelAccess } = require("./lib/utils.js");
const { getReviewColumns } = require("./lib/review.js");

module.exports = {
  searchPapers, login, status,
  extractDoi, deepExtractPaper, enrichPapers,
  listLibrary, listCollections, getCollection, createCollection, bookmarkPaper,
  exportCitation, exportLibraryCsv,
  checkCredits, listTranslationLanguages, getModelAccess,
  getReviewColumns,
};
