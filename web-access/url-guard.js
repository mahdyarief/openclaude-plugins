/**
 * SSRF guard for direct fetches.
 *
 * Fetched pages are untrusted and can contain instructions that steer the model
 * into requesting internal addresses (cloud metadata at 169.254.169.254, router
 * admin pages, localhost services). By default such targets are refused.
 * Set "fetch": { "allowPrivateNetwork": true } in web-access.json to allow them
 * (e.g. to read docs served from localhost during development).
 *
 * Two layers: assertPublicUrl() checks the URL (and its DNS answers) before
 * every hop, and pinnedLookup() re-checks the address the socket actually
 * connects to, so a DNS-rebinding answer cannot slip through in between.
 */

const dns = require("dns").promises;
const net = require("net");

class BlockedUrlError extends Error {}

const BLOCKED_HOST_SUFFIXES = [".localhost", ".local", ".internal", ".home.arpa"];

function ipv4ToInt(ip) {
  return ip.split(".").reduce((acc, o) => (acc << 8) + Number(o), 0) >>> 0;
}

function inV4(ip, cidr) {
  const [base, bits] = cidr.split("/");
  const mask = bits === "0" ? 0 : (~0 << (32 - Number(bits))) >>> 0;
  return (ipv4ToInt(ip) & mask) === (ipv4ToInt(base) & mask);
}

const PRIVATE_V4 = [
  "0.0.0.0/8", // "this" network
  "10.0.0.0/8", // private
  "100.64.0.0/10", // carrier-grade NAT
  "127.0.0.0/8", // loopback
  "169.254.0.0/16", // link-local, cloud metadata
  "172.16.0.0/12", // private
  "192.0.0.0/24", // IETF protocol assignments
  "192.168.0.0/16", // private
  "198.18.0.0/15", // benchmarking
  "224.0.0.0/4", // multicast
  "240.0.0.0/4", // reserved + broadcast
];

function isPrivateIp(ip) {
  if (net.isIPv4(ip)) return PRIVATE_V4.some((c) => inV4(ip, c));
  if (net.isIPv6(ip)) {
    const v = ip.toLowerCase().replace(/^\[|\]$/g, "");
    if (v === "::" || v === "::1") return true;
    const mapped = v.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    if (mapped) return isPrivateIp(mapped[1]);
    const first = parseInt(v.split(":")[0] || "0", 16);
    if ((first & 0xfe00) === 0xfc00) return true; // fc00::/7 unique local
    if ((first & 0xffc0) === 0xfe80) return true; // fe80::/10 link-local
    if ((first & 0xff00) === 0xff00) return true; // ff00::/8 multicast
    return false;
  }
  return false;
}

/**
 * Throws BlockedUrlError if the URL is not http(s) or points at a private /
 * loopback / link-local address (directly or via DNS).
 */
async function assertPublicUrl(rawUrl, { allowPrivate = false } = {}) {
  let u;
  try {
    u = new URL(rawUrl);
  } catch {
    throw new BlockedUrlError(`Invalid URL: ${rawUrl}`);
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    throw new BlockedUrlError(`Only http(s) URLs are allowed (got ${u.protocol})`);
  }
  if (allowPrivate) return u;

  const host = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  const why = `refusing to fetch internal address ${host} (set fetch.allowPrivateNetwork to allow)`;

  if (host === "localhost" || BLOCKED_HOST_SUFFIXES.some((s) => host.endsWith(s))) {
    throw new BlockedUrlError(why);
  }
  if (net.isIP(host)) {
    if (isPrivateIp(host)) throw new BlockedUrlError(why);
    return u;
  }

  let addrs;
  try {
    addrs = await dns.lookup(host, { all: true, verbatim: true });
  } catch (err) {
    throw new Error(`DNS lookup failed for ${host}: ${err.code || err.message}`);
  }
  if (addrs.some((a) => isPrivateIp(a.address))) {
    throw new BlockedUrlError(`${why} — it resolves to a private IP`);
  }
  return u;
}

/**
 * A socket `lookup` function that refuses private addresses at connect time.
 * Used by the pinned transport: the IP that passes this check is exactly the
 * IP the socket connects to, which closes the DNS-rebinding window between
 * assertPublicUrl() and the actual connection.
 */
function pinnedLookup(allowPrivate) {
  const dnsCb = require("dns");
  return (hostname, options, callback) => {
    if (typeof options === "function") {
      callback = options;
      options = {};
    }
    const opts = typeof options === "number" ? { family: options } : options || {};
    dnsCb.lookup(hostname, { ...opts, all: true }, (err, addrs) => {
      if (err) return callback(err);
      if (!allowPrivate) {
        const bad = addrs.find((a) => isPrivateIp(a.address));
        if (bad) {
          return callback(
            new BlockedUrlError(
              `refusing to fetch internal address ${hostname} — it resolves to private IP ${bad.address} (set fetch.allowPrivateNetwork to allow)`
            )
          );
        }
      }
      if (opts.all) callback(null, addrs);
      else callback(null, addrs[0].address, addrs[0].family);
    });
  };
}

module.exports = { assertPublicUrl, isPrivateIp, pinnedLookup, BlockedUrlError };
