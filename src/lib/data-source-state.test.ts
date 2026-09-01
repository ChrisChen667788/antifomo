import { describe, expect, it } from "vitest";
import {
  getDataSourceStateCopy,
  hasFallbackContent,
  resolveDataSourceState,
} from "@/lib/data-source-state";

const translate = (_key: string, fallback = "") => fallback;

describe("data-source state", () => {
  it("never hides a local demo or unavailable API behind a live/empty label", () => {
    expect(resolveDataSourceState({ isDemo: true, itemCount: 3 })).toBe("demo");
    expect(resolveDataSourceState({ isUnavailable: true, itemCount: 0 })).toBe("unavailable");
  });

  it("surfaces explicit collector fallback content as degraded", () => {
    const items = [{ fallback_used: false }, { fallbackUsed: true }];

    expect(hasFallbackContent(items)).toBe(true);
    expect(resolveDataSourceState({ items })).toBe("degraded");
  });

  it("keeps a successful empty API response distinct from an unavailable API", () => {
    expect(resolveDataSourceState({ items: [] })).toBe("empty");
    expect(resolveDataSourceState({ itemCount: 1 })).toBe("live");
  });

  it("uses explicit, user-facing copy for every source state", () => {
    expect(getDataSourceStateCopy("live", translate).label).toBe("实时 API 数据");
    expect(getDataSourceStateCopy("degraded", translate).detail).toContain("降级采集路径");
    expect(getDataSourceStateCopy("demo", translate).detail).toContain("本地演示数据");
  });
});
