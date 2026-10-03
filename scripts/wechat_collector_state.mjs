import crypto from "node:crypto";

const WECHAT_STABLE_QUERY_KEYS = ["__biz", "mid", "idx", "sn", "chksm"];

export function normalizeFetchUrl(url) {
  const text = String(url || "").trim();
  if (!text || !/^https?:\/\//i.test(text)) return "";
  try {
    const parsed = new URL(text);
    parsed.username = "";
    parsed.password = "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "";
  }
}

export function canonicalizePersistedUrl(url) {
  const normalized = normalizeFetchUrl(url);
  if (!normalized) return "";
  const parsed = new URL(normalized);
  if (parsed.hostname.toLowerCase() === "mp.weixin.qq.com") {
    const stable = new URLSearchParams();
    for (const key of WECHAT_STABLE_QUERY_KEYS) {
      const values = parsed.searchParams.getAll(key).sort();
      for (const value of values) stable.append(key, value);
    }
    parsed.search = stable.toString();
  }
  return parsed.toString();
}

export function redactSensitiveUrls(value) {
  return String(value || "").replace(/https?:\/\/[^\s<>"']+/gi, (candidate) => {
    const trailing = candidate.match(/[),.;，。；）】》]+$/)?.[0] || "";
    const core = trailing ? candidate.slice(0, -trailing.length) : candidate;
    return `${canonicalizePersistedUrl(core) || "[invalid-url]"}${trailing}`;
  });
}

export function sourceToken(url) {
  const canonical = canonicalizePersistedUrl(url);
  if (!canonical) return "-";
  const parsed = new URL(canonical);
  const pathToken = parsed.pathname.split("/").filter(Boolean).at(-1) || parsed.hostname;
  if (parsed.hostname === "mp.weixin.qq.com" && pathToken === "s") {
    return `wx-${crypto.createHash("sha256").update(canonical).digest("hex").slice(0, 12)}`;
  }
  return pathToken || parsed.hostname;
}

export function wasSeenRecently(entry, refreshHours, nowMs = Date.now()) {
  if (!entry || Number(refreshHours) <= 0) return false;
  const seenAt = Date.parse(String(entry.seen_at || ""));
  if (!Number.isFinite(seenAt)) return false;
  return nowMs - seenAt < Number(refreshHours) * 60 * 60 * 1000;
}

export function selectFavoriteLinksForRefresh(
  urls,
  seenFavoriteLinks,
  refreshHours,
  nowMs = Date.now(),
) {
  const byPersistedIdentity = new Map();
  for (const rawUrl of Array.isArray(urls) ? urls : []) {
    const fetchUrl = normalizeFetchUrl(rawUrl);
    const persistedUrl = canonicalizePersistedUrl(fetchUrl);
    if (fetchUrl && persistedUrl && !byPersistedIdentity.has(persistedUrl)) {
      byPersistedIdentity.set(persistedUrl, fetchUrl);
    }
  }

  const checkpoints = seenFavoriteLinks && typeof seenFavoriteLinks === "object"
    ? seenFavoriteLinks
    : {};
  return Array.from(byPersistedIdentity, ([persistedUrl, fetchUrl]) => ({
    persistedUrl,
    fetchUrl,
  })).filter(
    ({ persistedUrl }) => !wasSeenRecently(checkpoints[persistedUrl], refreshHours, nowMs),
  );
}

function sanitizeStoredValue(value) {
  if (typeof value === "string") return redactSensitiveUrls(value);
  if (Array.isArray(value)) return value.map((item) => sanitizeStoredValue(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeStoredValue(item)]),
    );
  }
  return value;
}

function sanitizeSeenUrlMap(value) {
  const output = {};
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  for (const [rawUrl, rawEntry] of Object.entries(source)) {
    const canonical = canonicalizePersistedUrl(rawUrl);
    if (!canonical) continue;
    const entry = sanitizeStoredValue(rawEntry);
    const previous = output[canonical];
    if (!previous || String(entry?.seen_at || "") >= String(previous?.seen_at || "")) {
      output[canonical] = entry;
    }
  }
  return output;
}

export function sanitizeCollectorState(input) {
  const source = input && typeof input === "object" ? input : {};
  const seenLinks = sanitizeSeenUrlMap(source.seen_links);
  const seenFavoriteLinks = sanitizeSeenUrlMap(source.seen_favorite_links);
  const sanitized = sanitizeStoredValue({
    ...source,
    seen_links: undefined,
    seen_favorite_links: undefined,
  });
  delete sanitized.seen_links;
  delete sanitized.seen_favorite_links;
  return {
    ...sanitized,
    seen_links: seenLinks,
    seen_favorite_links: seenFavoriteLinks,
  };
}
