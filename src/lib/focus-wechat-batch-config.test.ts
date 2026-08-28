import { describe, expect, it } from "vitest";
import {
  DEFAULT_FOCUS_WECHAT_BATCH_CONFIG,
  parseFocusWechatBatchConfig,
} from "@/lib/focus-wechat-batch-config";

describe("focus wechat batch config", () => {
  it("uses production defaults without an override", () => {
    expect(parseFocusWechatBatchConfig()).toEqual(DEFAULT_FOCUS_WECHAT_BATCH_CONFIG);
  });

  it("allows a bounded small batch through focus URL parameters", () => {
    expect(
      parseFocusWechatBatchConfig({
        search:
          "?focusWechatTotalItems=1&focusWechatSegmentItems=1&focusWechatStartBatchIndex=0&focusWechatRunOnceMaxItems=1&focusCollectorMaxPerCycle=2",
      }),
    ).toMatchObject({
      totalItems: 1,
      segmentItems: 1,
      startBatchIndex: 0,
      runOnceMaxItems: 1,
      maxCollectPerCycle: 2,
      overrideActive: true,
      source: "query",
    });
  });

  it("accepts localStorage JSON for reusable test runs", () => {
    expect(
      parseFocusWechatBatchConfig({
        storageValue: JSON.stringify({
          totalItems: 3,
          segmentItems: 2,
          startBatchIndex: 4,
          runOnceMaxItems: 2,
        }),
      }),
    ).toMatchObject({
      totalItems: 3,
      segmentItems: 2,
      startBatchIndex: 4,
      runOnceMaxItems: 2,
      overrideActive: true,
      source: "storage",
    });
  });

  it("clamps invalid values to safe ranges", () => {
    expect(
      parseFocusWechatBatchConfig({
        search: "?wechatItems=0&wechatSegmentItems=99&wechatStartBatchIndex=-3&wechatRunOnceMaxItems=200",
      }),
    ).toMatchObject({
      totalItems: 1,
      segmentItems: 1,
      startBatchIndex: 0,
      runOnceMaxItems: 60,
    });
  });
});
