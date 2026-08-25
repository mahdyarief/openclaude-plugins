// scispace-client.js — aggregator: re-export all capabilities from lib/ modules.
// Kept as the single entry point so tools.js and external scripts keep working.
const { searchPapers } = require("./lib/search.js");
const { login, status } = require("./lib/auth.js");
const { extractDoi, deepExtractPaper, enrichPapers } = require("./lib/extract.js");
const {
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
} = require("./lib/library.js");
const { exportCitation, exportLibraryCsv, exportLibraryBibtex } = require("./lib/citations.js");
const { checkCredits, listTranslationLanguages, getModelAccess } = require("./lib/utils.js");
const { getReviewColumns, deepReviewSynthesis } = require("./lib/review.js");
const { listAgentThreads, askPaper } = require("./lib/agent.js");
const { getCache, clearCache } = require("./lib/cache.js");

module.exports = {
  searchPapers,
  login,
  status,
  extractDoi,
  deepExtractPaper,
  enrichPapers,
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
  exportCitation,
  exportLibraryCsv,
  exportLibraryBibtex,
  checkCredits,
  listTranslationLanguages,
  getModelAccess,
  getReviewColumns,
  deepReviewSynthesis,
  listAgentThreads,
  askPaper,
  getCache,
  clearCache,
};
