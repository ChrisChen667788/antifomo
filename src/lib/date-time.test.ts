import { describe, expect, it } from "vitest";
import { formatProductDate, formatProductDateTime } from "@/lib/date-time";

describe("product date formatting", () => {
  it("renders the same fixed product timezone at the UTC date boundary", () => {
    expect(formatProductDate("2026-07-14T16:30:05Z")).toBe("2026-07-15");
    expect(formatProductDateTime("2026-07-14T16:30:05Z")).toBe("2026-07-15 00:30:05");
  });

  it("treats server timestamps without an offset as UTC", () => {
    expect(formatProductDateTime("2026-07-14T15:38:53")).toBe("2026-07-14 23:38:53");
  });

  it("keeps invalid source strings visible instead of producing environment-specific output", () => {
    expect(formatProductDate("pending-date")).toBe("pending-date");
    expect(formatProductDateTime("pending-date")).toBe("pending-date");
  });
});
