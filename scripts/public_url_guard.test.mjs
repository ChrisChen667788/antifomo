import assert from "node:assert/strict";
import test from "node:test";

import {
  createPinnedBrowserNetworkPolicy,
  installPuppeteerPublicNetworkGuard,
  isBlockedAddress,
} from "./public_url_guard.mjs";

function publicLookup(hostname) {
  const addresses = {
    "example.test": [{ address: "93.184.216.34", family: 4 }],
    "mp.weixin.qq.com": [{ address: "1.1.1.1", family: 4 }],
  };
  return Promise.resolve(addresses[hostname] || []);
}

test("address classification rejects local, metadata, mapped, and documentation ranges", () => {
  for (const address of [
    "127.0.0.1",
    "10.1.2.3",
    "169.254.169.254",
    "192.0.2.10",
    "::1",
    "::ffff:127.0.0.1",
    "::ffff:7f00:1",
    "::7f00:1",
    "64:ff9b::7f00:1",
    "2002:7f00:1::",
    "3fff::1",
    "5f00::1",
    "4000::1",
    "6000::1",
    "fe00::1",
    "100:0:0:1::1",
    "fc00::1",
    "fec0::1",
    "2001:db8::1",
  ]) {
    assert.equal(isBlockedAddress(address), true, address);
  }
  assert.equal(isBlockedAddress("93.184.216.34"), false);
  assert.equal(isBlockedAddress("2606:4700:4700::1111"), false);
});

test("browser policy pins validated hosts and denies every other DNS name", async () => {
  const policy = await createPinnedBrowserNetworkPolicy(
    ["https://example.test/a", "https://mp.weixin.qq.com/s/id"],
    { lookupFn: publicLookup },
  );

  assert.deepEqual([...policy.allowedHosts], ["example.test", "mp.weixin.qq.com"]);
  assert.match(policy.resolverRules, /MAP example\.test 93\.184\.216\.34/);
  assert.match(policy.resolverRules, /MAP mp\.weixin\.qq\.com 1\.1\.1\.1/);
  assert.match(policy.resolverRules, /MAP \* \^NOTFOUND$/);
  assert.ok(policy.launchArgs.includes("--no-proxy-server"));
  assert.ok(policy.launchArgs.includes("--disable-background-networking"));
  assert.ok(policy.launchArgs.includes("--disable-extensions"));
  assert.ok(policy.launchArgs.includes("--disable-features=NetworkPrediction"));
  assert.ok(policy.launchArgs.some((value) => value.startsWith("--host-resolver-rules=")));
});

test("browser policy formats an IPv6 replacement without bracketing the host pattern", async () => {
  const policy = await createPinnedBrowserNetworkPolicy(["https://ipv6.example.test/a"], {
    lookupFn: async () => [{ address: "2606:4700:4700::1111", family: 6 }],
  });
  assert.equal(
    policy.resolverRules,
    "MAP ipv6.example.test [2606:4700:4700::1111], MAP * ^NOTFOUND",
  );
});

test("browser policy rejects a hostname if any current answer is private", async () => {
  await assert.rejects(
    createPinnedBrowserNetworkPolicy(["https://example.test/a"], {
      lookupFn: async () => [
        { address: "93.184.216.34", family: 4 },
        { address: "127.0.0.1", family: 4 },
      ],
    }),
    /Private, reserved, or non-global/,
  );
});

function fakeInterceptedRequest(url) {
  return {
    action: "",
    url: () => url,
    continue: async function continueRequest() {
      this.action = "continue";
    },
    abort: async function abortRequest() {
      this.action = "abort";
    },
  };
}

test("request interception allows only pinned HTTP hosts and local document schemes", async () => {
  let requestHandler;
  let documentInitializer;
  const page = {
    setJavaScriptEnabled: async (enabled) => assert.equal(enabled, false),
    evaluateOnNewDocument: async (initializer) => {
      documentInitializer = initializer;
    },
    setRequestInterception: async (enabled) => assert.equal(enabled, true),
    on: (event, handler) => {
      assert.equal(event, "request");
      requestHandler = handler;
    },
  };
  await installPuppeteerPublicNetworkGuard(page, {
    allowedHosts: new Set(["example.test"]),
  });
  assert.equal(typeof documentInitializer, "function");
  assert.match(documentInitializer.toString(), /RTCPeerConnection/);
  assert.match(documentInitializer.toString(), /webkitRTCPeerConnection/);
  assert.match(documentInitializer.toString(), /globalThis, "open"/);

  const allowed = fakeInterceptedRequest("https://example.test/article");
  requestHandler(allowed);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(allowed.action, "continue");

  const unknown = fakeInterceptedRequest("https://cdn.example.test/script.js");
  requestHandler(unknown);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(unknown.action, "abort");

  const websocket = fakeInterceptedRequest("wss://example.test/socket");
  requestHandler(websocket);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(websocket.action, "abort");

  const localFile = fakeInterceptedRequest("file:///etc/passwd");
  requestHandler(localFile);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(localFile.action, "abort");

  const localData = fakeInterceptedRequest("data:text/plain,ok");
  requestHandler(localData);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(localData.action, "continue");
});
