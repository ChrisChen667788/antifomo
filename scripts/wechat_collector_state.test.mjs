import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalizePersistedUrl,
  normalizeFetchUrl,
  sanitizeCollectorState,
  selectFavoriteLinksForRefresh,
  sourceToken,
  wasSeenRecently,
} from "./wechat_collector_state.mjs";

const privateUrl =
  "https://mp.weixin.qq.com/s?pass_ticket=secret&idx=1&mid=22&__biz=MzDemo&sn=abc&scene=21&uin=private#wechat_redirect";
const canonicalUrl = "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=22&idx=1&sn=abc";

test("keeps a temporary fetch URL but persists only stable WeChat identity", () => {
  assert.match(normalizeFetchUrl(privateUrl), /pass_ticket=secret/);
  assert.equal(canonicalizePersistedUrl(privateUrl), canonicalUrl);
  assert.doesNotMatch(sourceToken(privateUrl), /secret|pass_ticket|uin/);
});

test("removes URL credentials from temporary and persisted representations", () => {
  const credentialUrl =
    "https://reader:password@mp.weixin.qq.com/s?__biz=MzDemo&mid=22&idx=1&pass_ticket=secret";
  assert.equal(
    normalizeFetchUrl(credentialUrl),
    "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=22&idx=1&pass_ticket=secret",
  );
  assert.equal(canonicalizePersistedUrl(credentialUrl), canonicalUrl.replace("&sn=abc", ""));
});

test("migrates legacy state keys and redacts URLs embedded in diagnostics", () => {
  const state = sanitizeCollectorState({
    seen_links: {
      [privateUrl]: { seen_at: "2026-10-03T00:00:00.000Z", note: `failed ${privateUrl}` },
    },
    seen_favorite_links: {
      [privateUrl]: {
        seen_at: "2026-10-03T01:00:00.000Z",
        source_url: privateUrl,
      },
    },
    last_rows: [{ note: `failed ${privateUrl}` }],
  });
  const serialized = JSON.stringify(state);
  assert.deepEqual(Object.keys(state.seen_links), [canonicalUrl]);
  assert.deepEqual(Object.keys(state.seen_favorite_links), [canonicalUrl]);
  assert.equal(state.seen_favorite_links[canonicalUrl].source_url, canonicalUrl);
  assert.doesNotMatch(serialized, /secret|pass_ticket|uin=|scene=21/);
});

test("seen checkpoints expire so unchanged URLs are periodically refreshed", () => {
  const entry = { seen_at: "2026-10-03T00:00:00.000Z" };
  assert.equal(wasSeenRecently(entry, 24, Date.parse("2026-10-03T23:00:00.000Z")), true);
  assert.equal(wasSeenRecently(entry, 24, Date.parse("2026-10-04T01:00:00.000Z")), false);
});

test("favorites checkpoints use canonical identity and expire with refresh hours", () => {
  const seenFavoriteLinks = {
    [canonicalUrl]: { seen_at: "2026-10-03T00:00:00.000Z" },
  };
  const duplicatePrivateUrl =
    "https://mp.weixin.qq.com/s?__biz=MzDemo&mid=22&idx=1&sn=abc&pass_ticket=rotated";

  assert.deepEqual(
    selectFavoriteLinksForRefresh(
      [privateUrl, duplicatePrivateUrl],
      seenFavoriteLinks,
      24,
      Date.parse("2026-10-03T23:00:00.000Z"),
    ),
    [],
  );
  assert.deepEqual(
    selectFavoriteLinksForRefresh(
      [privateUrl, duplicatePrivateUrl],
      seenFavoriteLinks,
      24,
      Date.parse("2026-10-04T01:00:00.000Z"),
    ),
    [{ persistedUrl: canonicalUrl, fetchUrl: normalizeFetchUrl(privateUrl) }],
  );
});
