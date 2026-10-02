const PRODUCT_TIME_ZONE = "Asia/Shanghai";

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: PRODUCT_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const DATE_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: PRODUCT_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

type DateInput = Date | string | number;

function parseDate(value: DateInput): Date | null {
  const normalized =
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value.trim())
      ? `${value.trim()}Z`
      : value;
  const parsed = normalized instanceof Date ? new Date(normalized.getTime()) : new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getParts(formatter: Intl.DateTimeFormat, value: DateInput): Record<string, string> | null {
  const parsed = parseDate(value);
  if (!parsed) return null;
  return Object.fromEntries(
    formatter
      .formatToParts(parsed)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
}

export function formatProductDate(value: DateInput): string {
  const parts = getParts(DATE_FORMATTER, value);
  if (!parts) return typeof value === "string" ? value : "—";
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function formatProductDateTime(value: DateInput): string {
  const parts = getParts(DATE_TIME_FORMATTER, value);
  if (!parts) return typeof value === "string" ? value : "—";
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}
