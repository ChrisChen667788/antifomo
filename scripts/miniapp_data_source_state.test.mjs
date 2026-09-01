import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const {
  getDataSourceStateCopy,
  getDataSourceStateTone,
  resolveDataSourceState,
} = require("../miniapp/utils/data-source-state.js");

test("miniapp source-state precedence never presents demo or unavailable content as live", () => {
  assert.equal(resolveDataSourceState({ fromMock: true, itemCount: 4 }), "demo");
  assert.equal(resolveDataSourceState({ unavailable: true, itemCount: 0 }), "unavailable");
  assert.equal(resolveDataSourceState({ items: [{ fallback_used: true }] }), "degraded");
  assert.equal(resolveDataSourceState({ items: [] }), "empty");
  assert.equal(resolveDataSourceState({ itemCount: 1 }), "live");
});

test("miniapp source states have explicit localized copy and tones", () => {
  assert.match(getDataSourceStateCopy("zh-CN", "demo"), /本地演示/);
  assert.match(getDataSourceStateCopy("en", "empty"), /no data/);
  assert.equal(getDataSourceStateTone("degraded"), "warning");
  assert.equal(getDataSourceStateTone("live"), "info");
});

test("miniapp primary read surfaces fail closed to unavailable state", async () => {
  const surfaces = [
    "../miniapp/pages/feed/index.js",
    "../miniapp/pages/item/index.js",
    "../miniapp/pages/saved/index.js",
  ];

  for (const surface of surfaces) {
    const source = await readFile(new URL(surface, import.meta.url), "utf8");
    assert.match(
      source,
      /resolveDataSourceState\(\{ unavailable: true \}\)/,
      `${surface} must expose API failure as unavailable`,
    );
  }
});

test("miniapp item detail keeps source state visible outside its content branch", async () => {
  const template = await readFile(
    new URL("../miniapp/pages/item/index.wxml", import.meta.url),
    "utf8",
  );
  const bannerIndex = template.indexOf("af-status-banner-{{sourceStateTone}}");
  const conditionalContentIndex = template.indexOf('wx:if="{{loading}}"');

  assert.ok(bannerIndex >= 0, "item detail must render a source-state banner");
  assert.ok(
    bannerIndex < conditionalContentIndex,
    "item detail source-state banner must remain visible during loading and error branches",
  );
});
