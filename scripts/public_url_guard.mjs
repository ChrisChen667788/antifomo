import dns from "node:dns/promises";
import net from "node:net";

const blocked = new net.BlockList();
const allocatedGlobalIpv6 = new net.BlockList();
allocatedGlobalIpv6.addSubnet("2000::", 3, "ipv6");
for (const [network, prefix] of [
  ["0.0.0.0", 8],
  ["10.0.0.0", 8],
  ["100.64.0.0", 10],
  ["127.0.0.0", 8],
  ["169.254.0.0", 16],
  ["172.16.0.0", 12],
  ["192.0.0.0", 24],
  ["192.0.2.0", 24],
  ["192.88.99.0", 24],
  ["192.168.0.0", 16],
  ["198.18.0.0", 15],
  ["198.51.100.0", 24],
  ["203.0.113.0", 24],
  ["224.0.0.0", 4],
  ["240.0.0.0", 4],
]) {
  blocked.addSubnet(network, prefix, "ipv4");
}
for (const [network, prefix] of [
  ["::", 96],
  ["::", 128],
  ["::1", 128],
  ["64:ff9b::", 96],
  ["64:ff9b:1::", 48],
  ["100::", 64],
  ["2001::", 23],
  ["2001:db8::", 32],
  ["2002::", 16],
  ["3fff::", 20],
  ["fc00::", 7],
  ["fe80::", 10],
  ["fec0::", 10],
  ["ff00::", 8],
]) {
  blocked.addSubnet(network, prefix, "ipv6");
}

function normalizeHostname(value) {
  const raw = String(value || "").replace(/\.$/, "").toLowerCase();
  if (raw.startsWith("[") && raw.endsWith("]")) return raw.slice(1, -1);
  return raw;
}

export function isBlockedAddress(address) {
  const clean = normalizeHostname(String(address || "").split("%", 1)[0]);
  const family = net.isIP(clean);
  if (family === 4) return blocked.check(clean, "ipv4");
  if (family === 6) {
    const mapped = clean.match(/^::ffff:(.+)$/);
    if (mapped) {
      if (/^\d+\.\d+\.\d+\.\d+$/.test(mapped[1])) {
        return blocked.check(mapped[1], "ipv4");
      }
      const groups = mapped[1].split(":");
      if (groups.length === 2 && groups.every((group) => /^[0-9a-f]{1,4}$/.test(group))) {
        const high = Number.parseInt(groups[0], 16);
        const low = Number.parseInt(groups[1], 16);
        const ipv4 = [high >> 8, high & 255, low >> 8, low & 255].join(".");
        return blocked.check(ipv4, "ipv4");
      }
      return true;
    }
    if (!allocatedGlobalIpv6.check(clean, "ipv6")) return true;
    return blocked.check(clean, "ipv6");
  }
  return true;
}

function parsePublicHttpUrl(value) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    throw new Error("Only absolute HTTP(S) URLs are allowed");
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only absolute HTTP(S) URLs are allowed");
  }
  if (parsed.username || parsed.password) throw new Error("Credentials in URLs are not allowed");
  const hostname = normalizeHostname(parsed.hostname);
  if (
    !hostname ||
    hostname === "localhost" ||
    hostname.endsWith(".localhost") ||
    hostname.endsWith(".local") ||
    hostname.endsWith(".internal")
  ) {
    throw new Error("Local network destinations are not allowed");
  }
  return { parsed, hostname };
}

async function resolvePublicHttpUrl(value, lookupFn = dns.lookup) {
  const { parsed, hostname } = parsePublicHttpUrl(value);
  const literalFamily = net.isIP(hostname);
  let addresses;
  try {
    addresses = literalFamily
      ? [{ address: hostname, family: literalFamily }]
      : await lookupFn(hostname, { all: true, verbatim: true });
  } catch {
    throw new Error("URL host could not be resolved safely");
  }
  if (!Array.isArray(addresses) || addresses.length === 0) {
    throw new Error("URL host could not be resolved safely");
  }
  const normalizedAddresses = addresses.map((row) => ({
    address: normalizeHostname(row?.address),
    family: net.isIP(normalizeHostname(row?.address)),
  }));
  if (
    normalizedAddresses.some(
      (row) => ![4, 6].includes(row.family) || isBlockedAddress(row.address),
    )
  ) {
    throw new Error("Private, reserved, or non-global destinations are not allowed");
  }
  return { parsed, hostname, addresses: normalizedAddresses };
}

export async function assertPublicHttpUrl(value) {
  const resolved = await resolvePublicHttpUrl(value);
  return resolved.parsed.toString();
}

function formatResolverAddress(address, family) {
  return family === 6 ? `[${address}]` : address;
}

function buildHostResolverRules(hostMappings) {
  const rules = [];
  for (const [hostname, row] of hostMappings) {
    rules.push(`MAP ${hostname} ${formatResolverAddress(row.address, row.family)}`);
  }
  rules.push("MAP * ^NOTFOUND");
  return rules.join(", ");
}

export async function createPinnedBrowserNetworkPolicy(values, { lookupFn = dns.lookup } = {}) {
  const hostMappings = new Map();
  for (const value of values) {
    const resolved = await resolvePublicHttpUrl(value, lookupFn);
    if (!hostMappings.has(resolved.hostname)) {
      const preferred =
        resolved.addresses.find((row) => row.family === 4) || resolved.addresses[0];
      hostMappings.set(resolved.hostname, preferred);
    }
  }
  if (hostMappings.size === 0) {
    throw new Error("At least one public browser destination is required");
  }
  const resolverRules = buildHostResolverRules(hostMappings);
  return {
    allowedHosts: new Set(hostMappings.keys()),
    resolverRules,
    launchArgs: [
      "--no-proxy-server",
      "--disable-background-networking",
      "--disable-extensions",
      "--disable-features=NetworkPrediction",
      `--host-resolver-rules=${resolverRules}`,
    ],
  };
}

export async function installPuppeteerPublicNetworkGuard(
  page,
  { allowedHosts = new Set() } = {},
) {
  const normalizedAllowedHosts = new Set(
    Array.from(allowedHosts, (hostname) => normalizeHostname(hostname)),
  );
  // Extraction only needs the server-rendered DOM and our own CDP evaluation.
  // Disabling target-page JavaScript closes browser networking APIs such as
  // WebRTC/STUN that do not pass through HTTP request interception or DNS.
  await page.setJavaScriptEnabled(false);
  await page.evaluateOnNewDocument(() => {
    for (const key of ["RTCPeerConnection", "webkitRTCPeerConnection"]) {
      Object.defineProperty(globalThis, key, {
        value: undefined,
        writable: false,
        configurable: false,
      });
    }
    Object.defineProperty(globalThis, "open", {
      value: () => null,
      writable: false,
      configurable: false,
    });
  });
  await page.setRequestInterception(true);
  page.on("request", (intercepted) => {
    void (async () => {
      let parsed;
      try {
        parsed = new URL(intercepted.url());
      } catch {
        await intercepted.abort("blockedbyclient");
        return;
      }

      if (["about:", "blob:", "data:"].includes(parsed.protocol)) {
        await intercepted.continue();
        return;
      }
      if (!["http:", "https:"].includes(parsed.protocol)) {
        await intercepted.abort("blockedbyclient");
        return;
      }
      const hostname = normalizeHostname(parsed.hostname);
      if (!normalizedAllowedHosts.has(hostname)) {
        await intercepted.abort("blockedbyclient");
        return;
      }
      await intercepted.continue();
    })().catch(() => {
      void intercepted.abort("blockedbyclient").catch(() => {});
    });
  });
}
