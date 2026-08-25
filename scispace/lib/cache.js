// lib/cache.js — In-memory LRU cache with TTL support
const MAX_ENTRIES = 100;
const DEFAULT_TTL_SEARCH = 5 * 60 * 1000; // 5 minutes for search results
const DEFAULT_TTL_EXTRACT = 60 * 60 * 1000; // 1 hour for deep extract

class CacheEntry {
  constructor(value, ttl) {
    this.value = value;
    this.expiresAt = Date.now() + ttl;
  }

  isExpired() {
    return Date.now() > this.expiresAt;
  }
}

class LRUCache {
  constructor(maxSize = MAX_ENTRIES) {
    this.maxSize = maxSize;
    this.cache = new Map();
  }

  get(key) {
    if (!this.cache.has(key)) {
      return null;
    }

    const entry = this.cache.get(key);
    if (entry.isExpired()) {
      this.cache.delete(key);
      return null;
    }

    // Move to end (most recently used)
    const value = this.cache.get(key);
    this.cache.delete(key);
    this.cache.set(key, value);

    return value.value;
  }

  set(key, value, ttl = DEFAULT_TTL_SEARCH) {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    } else if (this.cache.size >= this.maxSize) {
      // Remove oldest entry (first in Map)
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    this.cache.set(key, new CacheEntry(value, ttl));
  }

  has(key) {
    return this.get(key) !== null;
  }

  delete(key) {
    this.cache.delete(key);
  }

  clear() {
    this.cache.clear();
  }

  size() {
    let count = 0;
    for (const entry of this.cache.values()) {
      if (!entry.isExpired()) {
        count++;
      }
    }
    return count;
  }

  cleanup() {
    for (const [key, entry] of this.cache.entries()) {
      if (entry.isExpired()) {
        this.cache.delete(key);
      }
    }
  }
}

// Global cache instance
let cacheInstance = null;

function getCache() {
  if (!cacheInstance) {
    cacheInstance = new LRUCache(MAX_ENTRIES);
  }
  return cacheInstance;
}

function clearCache() {
  if (cacheInstance) {
    cacheInstance.clear();
  }
}

function generateCacheKey(params) {
  // Generate deterministic key from parameters
  const sortedKeys = Object.keys(params).sort();
  const parts = sortedKeys.map(k => `${k}:${params[k]}`);
  return Buffer.from(parts.join('|')).toString('base64');
}

module.exports = {
  getCache,
  clearCache,
  generateCacheKey,
  MAX_ENTRIES,
  DEFAULT_TTL_SEARCH,
  DEFAULT_TTL_EXTRACT,
};
