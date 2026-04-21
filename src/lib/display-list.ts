function normalizeDisplayText(value: unknown): string {
  return String(value || "").trim();
}

export function dedupeTextList(
  values: Iterable<unknown> | null | undefined,
  options: {
    limit?: number;
    normalizer?: (value: unknown) => string;
  } = {},
): string[] {
  const normalizer = options.normalizer || normalizeDisplayText;
  const limit = typeof options.limit === "number" ? options.limit : Number.POSITIVE_INFINITY;
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values || []) {
    const normalized = normalizer(value);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    next.push(normalized);
    if (next.length >= limit) {
      break;
    }
  }
  return next;
}

export function dedupeByKey<T>(
  values: Iterable<T> | null | undefined,
  getKey: (value: T) => string,
  limit = Number.POSITIVE_INFINITY,
): T[] {
  const seen = new Set<string>();
  const next: T[] = [];
  for (const value of values || []) {
    const key = String(getKey(value) || "").trim();
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    next.push(value);
    if (next.length >= limit) {
      break;
    }
  }
  return next;
}
