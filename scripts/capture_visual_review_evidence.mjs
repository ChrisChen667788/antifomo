#!/usr/bin/env node
/** Capture the actual local 2.10.5/2.10.6 panels. Does not initialize or mutate data. */
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const args = process.argv.slice(2);
function option(name, fallback) {
  const index = args.indexOf(name);
  return index < 0 ? fallback : args[index + 1];
}
const frontend = option("--frontend", "http://127.0.0.1:3010");
const api = option("--api", "http://127.0.0.1:8000");
const output = path.resolve(option("--output", "output/playwright/visual-2.10.6"));
for (const value of [frontend, api]) {
  assert(["127.0.0.1", "localhost", "[::1]"].includes(new URL(value).hostname), "Capture requires loopback services");
}
fs.mkdirSync(output, { recursive: true });
const executablePath = option("--chrome", process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
const browser = await puppeteer.launch({ executablePath, headless: true });
const manifest = {
  version: "2.10.6", captured_at: new Date().toISOString(),
  source_commit: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
  working_tree_changes: execFileSync("git", ["status", "--porcelain"], { encoding: "utf8" }).split("\n").filter(line => line && !line.endsWith(" memory.md")).length,
  browser: await browser.version(), evidence_kind: "local_browser_runtime",
  physical_device_test: false, human_acceptance: false,
  data_mode: option("--data-mode", "actual_local_api"),
  captures: [],
};
try {
  for (const [kind, viewport] of [
    ["desktop_browser", { width: 1440, height: 1100, deviceScaleFactor: 1 }],
    ["mobile_viewport", { width: 390, height: 844, deviceScaleFactor: 1, isMobile: true, hasTouch: true }],
  ]) {
    const page = await browser.newPage();
    const failures = [];
    page.on("pageerror", error => failures.push(error.message));
    await page.setViewport(viewport);
    await page.setRequestInterception(true);
    page.on("request", request => {
      const url = new URL(request.url());
      if (!new Set([new URL(frontend).origin, new URL(api).origin]).has(url.origin) || !["GET", "HEAD", "OPTIONS"].includes(request.method())) {
        void request.abort();
      } else void request.continue();
    });
    await page.evaluateOnNewDocument(apiBase => localStorage.setItem("anti_fomo_api_base_override", apiBase), api);
    const start = performance.now();
    const response = await page.goto(`${frontend}/competitive`, { waitUntil: "networkidle0" });
    assert.equal(response.status(), 200);
    await page.waitForSelector("[data-testid='competitive-visual-evidence']");
    await page.waitForFunction(() => !document.body.innerText.includes("正在读取视觉"));
    const navigation_ms = Math.round(performance.now() - start);
    for (const [panel, selector] of [
      ["office-receipts", "[data-testid='competitive-office-evidence-receipts']"],
      ["visual-revisions", "[data-testid='competitive-visual-evidence']"],
    ]) {
      const element = await page.$(selector);
      assert(element, `Missing ${panel}`);
      await element.evaluate(node => node.scrollIntoView({ block: "start" }));
      const dimensions = await element.evaluate(node => ({ width: node.clientWidth, scroll_width: node.scrollWidth }));
      assert(dimensions.scroll_width <= dimensions.width + 2, `${panel} overflows horizontally`);
      const filename = `${panel}-${kind}.png`;
      // A viewport capture has truthful dimensions for the visual-evidence API;
      // an element crop must not be labeled as a full device viewport.
      await page.screenshot({ path: path.join(output, filename), fullPage: false });
      const bytes = fs.readFileSync(path.join(output, filename));
      manifest.captures.push({
        filename, panel, capture_kind: kind, viewport, navigation_ms,
        size_bytes: bytes.length, sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
        image_width: bytes.readUInt32BE(16), image_height: bytes.readUInt32BE(20),
        horizontal_overflow: false, framing: "viewport_at_panel_start", human_review_status: "missing",
      });
    }
    assert.deepEqual(failures, [], `Browser runtime errors: ${failures.join(", ")}`);
    await page.close();
  }
  fs.writeFileSync(path.join(output, "capture-manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
  console.log(JSON.stringify({ output, captures: manifest.captures.length, browser: manifest.browser, physical_device_test: false }));
} finally {
  await browser.close();
}
