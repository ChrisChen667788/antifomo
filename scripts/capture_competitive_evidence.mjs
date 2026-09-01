#!/usr/bin/env node
/**
 * Capture reproducible, read-only `/competitive` evidence for public docs.
 *
 * This script intentionally does not start or stop the frontend/backend and
 * replaces persisted product-strategy GET responses in the browser with their
 * deterministic read-only `preview` payloads, even if an operator has
 * initialized a local development DB.
 *
 * It is browser/viewport evidence, not a claim of physical-device testing,
 * production performance, external-source verification, or release approval.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_OUTPUT_DIR = "docs/assets/competitive-evidence";
const DEFAULT_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const API_BASE_OVERRIDE_KEY = "anti_fomo_api_base_override";
const CHROME_COMMAND_CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"];
const CHROME_PATH_CANDIDATES = [
  DEFAULT_MAC_CHROME_PATH,
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
];
const PREVIEW_PERSISTED_PATHS = new Set([
  "/api/product-strategy/competitive-landscape",
  "/api/product-strategy/decision-context-packets",
  "/api/product-strategy/artifact-acceptance",
  "/api/product-strategy/iteration-program",
]);
const PRODUCT_STRATEGY_PREFIX = "/api/product-strategy/";
const MIN_CAPTURE_BYTES = 30_000;
const CAPTURES = [
  {
    key: "competitive-preview-desktop-browser",
    filename: "competitive-preview-desktop-browser.png",
    formFactor: "desktop_browser",
    viewport: { width: 1600, height: 1100, deviceScaleFactor: 1 },
    description: "Read-only Competitive Capability Observatory overview in a desktop browser viewport.",
  },
  {
    key: "competitive-source-matrix-desktop-browser",
    filename: "competitive-source-matrix-desktop-browser.png",
    formFactor: "desktop_browser",
    viewport: { width: 1600, height: 1100, deviceScaleFactor: 1 },
    scrollText: "官方能力观察",
    description: "Official-source matrix in a desktop browser viewport; vendor claims remain unverified unless separately evidenced.",
  },
  {
    key: "competitive-artifact-gates-desktop-browser",
    filename: "competitive-artifact-gates-desktop-browser.png",
    formFactor: "desktop_browser",
    viewport: { width: 1600, height: 1100, deviceScaleFactor: 1 },
    scrollSelector: "[data-testid='competitive-artifact-acceptance']",
    description: "Office and visual evidence HOLD gates in a desktop browser viewport.",
  },
  {
    key: "competitive-preview-mobile-viewport",
    filename: "competitive-preview-mobile-viewport.png",
    formFactor: "mobile_viewport",
    viewport: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
    description: "Read-only Competitive Capability Observatory overview in a simulated mobile CSS viewport, not a physical-device capture.",
  },
  {
    key: "competitive-artifact-gates-mobile-viewport",
    filename: "competitive-artifact-gates-mobile-viewport.png",
    formFactor: "mobile_viewport",
    viewport: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
    scrollSelector: "[data-testid='competitive-artifact-acceptance']",
    description: "Office and visual evidence HOLD gates in a simulated mobile CSS viewport, not a physical-device capture.",
  },
  {
    key: "competitive-iteration-program-desktop-browser",
    filename: "competitive-iteration-program-desktop-browser.png",
    formFactor: "desktop_browser",
    viewport: { width: 1600, height: 1100, deviceScaleFactor: 1 },
    scrollSelector: "[data-testid='competitive-iteration-program']",
    description: "The governed 2.10.3-2.11.7 iteration train and Agent-source watch in a desktop browser viewport.",
  },
  {
    key: "competitive-iteration-program-mobile-viewport",
    filename: "competitive-iteration-program-mobile-viewport.png",
    formFactor: "mobile_viewport",
    viewport: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
    scrollSelector: "[data-testid='competitive-iteration-program']",
    description: "The governed 2.10.3-2.11.7 iteration train in a simulated mobile CSS viewport, not a physical-device capture.",
  },
];

function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    apiBase: DEFAULT_API_BASE,
    outputDir: DEFAULT_OUTPUT_DIR,
    chromePath: process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH || "",
    samples: 3,
    headless: true,
    mode: "preview",
    generateMotion: true,
  };

  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    const next = argv[index + 1];
    if (token === "--frontend-url" && next) {
      args.frontendUrl = next;
      index += 1;
    } else if (token === "--api-base" && next) {
      args.apiBase = next;
      index += 1;
    } else if (token === "--output-dir" && next) {
      args.outputDir = next;
      index += 1;
    } else if (token === "--chrome-path" && next) {
      args.chromePath = next;
      index += 1;
    } else if (token === "--samples" && next) {
      args.samples = Number(next);
      index += 1;
    } else if (token === "--headful") {
      args.headless = false;
    } else if (token === "--mode" && next) {
      args.mode = next;
      index += 1;
    } else if (token === "--no-motion") {
      args.generateMotion = false;
    } else if (token === "--help" || token === "-h") {
      printUsage();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${token}`);
    }
  }

  if (!Number.isInteger(args.samples) || args.samples < 1 || args.samples > 10) {
    throw new Error("--samples must be an integer between 1 and 10.");
  }
  if (args.mode !== "preview") {
    throw new Error("Only `--mode preview` is supported. It prevents persisted-state and mutation claims.");
  }
  return args;
}

function printUsage() {
  console.log(`Usage: node scripts/capture_competitive_evidence.mjs [options]

Requires an already running local frontend and backend. This command never starts,
stops, initializes, or mutates either service.

Options:
  --frontend-url <url>  Local frontend URL (default: ${DEFAULT_FRONTEND_URL})
  --api-base <url>      Local backend URL (default: ${DEFAULT_API_BASE})
  --output-dir <path>   Curated evidence directory (default: ${DEFAULT_OUTPUT_DIR})
  --chrome-path <path>  Chrome/Chromium executable path
  --samples <1-10>      Browser-navigation samples per viewport (default: 3)
  --headful             Show the browser for a visual operator check
  --no-motion           Skip GIF/MP4 generation; still captures PNGs and metrics
  --mode preview        Required read-only preview mode (default)
`);
}

function resolveChromePath(requestedPath) {
  const candidates = [requestedPath, process.env.CHROME_PATH, process.env.PUPPETEER_EXECUTABLE_PATH, ...CHROME_PATH_CANDIDATES]
    .map((value) => value?.trim())
    .filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  for (const command of CHROME_COMMAND_CANDIDATES) {
    const result = spawnSync("which", [command], { encoding: "utf8" });
    if (result.status === 0 && result.stdout.trim() && fs.existsSync(result.stdout.trim())) {
      return result.stdout.trim();
    }
  }
  throw new Error(`Chrome executable not found. Checked: ${candidates.join(", ") || "(none)"}.`);
}

function resolveExecutable(command) {
  const result = spawnSync("which", [command], { encoding: "utf8" });
  return result.status === 0 && result.stdout.trim() ? result.stdout.trim() : null;
}

function normalizeUrl(value) {
  const parsed = new URL(value);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error(`Only http(s) endpoints are supported: ${value}`);
  }
  return parsed.toString().replace(/\/+$/, "");
}

async function fetchJson(url, label) {
  let response;
  try {
    response = await fetch(url, { headers: { Accept: "application/json" } });
  } catch (error) {
    throw new Error(`${label} could not reach ${url}. Start the local service separately before capture. ${String(error)}`);
  }
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${label} failed with HTTP ${response.status}: ${body.slice(0, 300)}`);
  }
  try {
    return body ? JSON.parse(body) : {};
  } catch (error) {
    throw new Error(`${label} returned non-JSON data: ${String(error)}`);
  }
}

async function verifyLocalPreview({ frontendUrl, apiBase }) {
  const health = await fetchJson(`${apiBase}/healthz`, "Backend health check");
  if (health?.status !== "ok") {
    throw new Error(`Backend health check did not report status=ok: ${JSON.stringify(health)}`);
  }
  const preview = await fetchJson(`${apiBase}/api/product-strategy/competitive-landscape/preview`, "Read-only competitive preview");
  const [decisionContextPreview, artifactAcceptancePreview, iterationProgramPreview] = await Promise.all([
    fetchJson(`${apiBase}/api/product-strategy/decision-context-packets/preview`, "Read-only decision-context preview"),
    fetchJson(`${apiBase}/api/product-strategy/artifact-acceptance/preview`, "Read-only artifact-acceptance preview"),
    fetchJson(`${apiBase}/api/product-strategy/iteration-program/preview`, "Read-only iteration-program preview"),
  ]);
  if (!preview?.read_only || !Array.isArray(preview.products) || !Array.isArray(preview.roadmap_cards)) {
    throw new Error("Read-only competitive preview did not satisfy its expected preview contract.");
  }
  if (!preview.products.length || !preview.roadmap_cards.length) {
    throw new Error("Read-only competitive preview is empty; refusing to capture weak or blank evidence.");
  }
  if (
    !iterationProgramPreview?.read_only
    || iterationProgramPreview.iteration_program_version !== "2.10.3-2.11.7"
    || iterationProgramPreview.iterations?.length !== 15
    || iterationProgramPreview.agent_sources?.length !== 7
  ) {
    throw new Error("Read-only iteration-program preview did not expose the expected 15-version / 7-source contract.");
  }
  const response = await fetch(`${frontendUrl}/competitive`, { redirect: "error" });
  if (!response.ok) {
    throw new Error(`Frontend /competitive availability check failed with HTTP ${response.status}.`);
  }
  return {
    summary: {
      health_status: health.status,
      catalog_version: preview.catalog_version,
      catalog_digest: preview.catalog_digest,
      products: preview.products.length,
      roadmap_cards: preview.roadmap_cards.length,
      iteration_program_version: iterationProgramPreview.iteration_program_version,
      iteration_count: iterationProgramPreview.iterations.length,
      agent_source_count: iterationProgramPreview.agent_sources.length,
      preview_read_only: preview.read_only === true,
    },
    previewPayloads: new Map([
      ["/api/product-strategy/competitive-landscape", preview],
      ["/api/product-strategy/decision-context-packets", decisionContextPreview],
      ["/api/product-strategy/artifact-acceptance", artifactAcceptancePreview],
      ["/api/product-strategy/iteration-program", iterationProgramPreview],
    ]),
  };
}

function sha256File(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function median(values) {
  const ordered = values.filter(Number.isFinite).sort((left, right) => left - right);
  if (!ordered.length) return null;
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : Math.round(((ordered[middle - 1] + ordered[middle]) / 2) * 100) / 100;
}

function formatMetric(value, suffix = "ms") {
  return Number.isFinite(value) ? `${Math.round(value)} ${suffix}` : "n/a";
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

async function delay(milliseconds) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function preparePage(page, { apiBase, previewPayloads, viewport }) {
  await page.setViewport(viewport);
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await page.evaluateOnNewDocument(
    (base, overrideKey) => {
      window.localStorage.setItem(overrideKey, base);
      window.localStorage.setItem(
        "anti_fomo_app_preferences_v1",
        JSON.stringify({ fontFamily: "system", textSize: "md", language: "zh-CN", themeMode: "light" }),
      );
    },
    apiBase,
    API_BASE_OVERRIDE_KEY,
  );
  await page.setRequestInterception(true);
  const apiOrigin = new URL(apiBase).origin;
  page.on("request", (request) => {
    if (request.isInterceptResolutionHandled()) return;
    let parsed;
    try {
      parsed = new URL(request.url());
    } catch {
      request.continue().catch(() => undefined);
      return;
    }
    if (parsed.origin !== apiOrigin || !parsed.pathname.startsWith(PRODUCT_STRATEGY_PREFIX)) {
      request.continue().catch(() => undefined);
      return;
    }
    if (request.method() === "GET" && PREVIEW_PERSISTED_PATHS.has(parsed.pathname)) {
      const previewPayload = previewPayloads.get(parsed.pathname);
      if (!previewPayload) {
        request.abort("blockedbyclient").catch(() => undefined);
        return;
      }
      request
        .respond({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": "*" },
          body: JSON.stringify(previewPayload),
        })
        .catch(() => undefined);
      return;
    }
    if (request.method() !== "GET" && request.method() !== "OPTIONS") {
      request.abort("blockedbyclient").catch(() => undefined);
      return;
    }
    request.continue().catch(() => undefined);
  });
}

async function waitForCompetitivePreview(page) {
  await page.waitForSelector("[data-testid='competitive-intelligence-workspace']", { timeout: 30000 });
  await page.waitForFunction(
    () => {
      const text = document.body?.innerText || "";
      return text.includes("竞品能力证据台账")
        && text.includes("官方能力观察")
        && text.includes("拟议后续版本")
        && text.includes("15 版本受治理迭代与 Agent 能力观察");
    },
    { timeout: 30000 },
  );
  const previewReady = await page.evaluate(() => {
    const bodyText = document.body?.innerText || "";
    return bodyText.includes("厂商声明，未独立验证") && bodyText.includes("baseline_hybrid");
  });
  if (!previewReady) {
    throw new Error("The page did not render the expected read-only competitive preview boundary.");
  }
}

async function assertNoRuntimeOverlay(page, label) {
  const overlay = await page.evaluate(() => {
    const bodyText = document.body?.innerText || "";
    return ["Runtime SyntaxError", "Runtime Error", "Unhandled Runtime Error", "Unexpected end of JSON input"].find((value) => bodyText.includes(value)) || null;
  });
  if (overlay) throw new Error(`${label} contains a runtime overlay: ${overlay}`);
}

async function scrollToSelector(page, selector) {
  if (!selector) return;
  const found = await page.evaluate((targetSelector) => {
    const element = document.querySelector(targetSelector);
    if (!element) return false;
    const top = element.getBoundingClientRect().top + window.scrollY - 110;
    window.scrollTo({ top, left: 0, behavior: "instant" });
    return true;
  }, selector);
  if (!found) throw new Error(`Capture anchor did not render: ${selector}`);
  await delay(350);
}

async function scrollToText(page, expectedText) {
  if (!expectedText) return;
  const found = await page.evaluate((text) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (node.textContent?.includes(text)) {
        const element = node.parentElement?.closest("section, article, div") || node.parentElement;
        if (element) {
          window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 110), behavior: "instant" });
          return true;
        }
      }
      node = walker.nextNode();
    }
    return false;
  }, expectedText);
  if (!found) throw new Error(`Capture text did not render: ${expectedText}`);
  await delay(350);
}

async function readBrowserMetrics(page, navigationElapsedMs) {
  return page.evaluate((elapsedMs) => {
    const navigation = performance.getEntriesByType("navigation")[0];
    const paints = performance.getEntriesByType("paint");
    const paintTime = (name) => paints.find((entry) => entry.name === name)?.startTime ?? null;
    const resources = performance.getEntriesByType("resource");
    const transferSize = resources.reduce((sum, entry) => sum + (Number(entry.transferSize) || 0), 0);
    return {
      capture_ready_ms: Math.round(elapsedMs * 100) / 100,
      navigation: navigation
        ? {
            response_end_ms: Math.round(navigation.responseEnd * 100) / 100,
            dom_content_loaded_ms: Math.round(navigation.domContentLoadedEventEnd * 100) / 100,
            load_event_end_ms: Math.round(navigation.loadEventEnd * 100) / 100,
            transfer_size_bytes: Number(navigation.transferSize) || 0,
          }
        : null,
      paint: {
        first_paint_ms: paintTime("first-paint"),
        first_contentful_paint_ms: paintTime("first-contentful-paint"),
      },
      resources: {
        count: resources.length,
        transfer_size_bytes: transferSize,
      },
    };
  }, navigationElapsedMs);
}

async function openPreviewPage(browser, args, viewport, diagnostics) {
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const context = await browser.createBrowserContext();
    const page = await context.newPage();
    const consoleMessages = [];
    const requestFailures = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleMessages.push(message.text());
    });
    page.on("requestfailed", (request) => requestFailures.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText || "unknown"}`));
    page.on("pageerror", (error) => pageErrors.push(error.message));
    try {
      await preparePage(page, { apiBase: args.apiBase, previewPayloads: args.previewPayloads, viewport });
      const start = performance.now();
      await page.goto(`${args.frontendUrl}/competitive`, { waitUntil: "domcontentloaded", timeout: 30000 });
      await waitForCompetitivePreview(page);
      await assertNoRuntimeOverlay(page, "Competitive preview");
      await page.waitForNetworkIdle({ idleTime: 200, timeout: 5000 }).catch(() => undefined);
      await delay(300);
      const metrics = await readBrowserMetrics(page, performance.now() - start);
      diagnostics.console_messages.push(...consoleMessages);
      diagnostics.request_failures.push(...requestFailures);
      diagnostics.page_errors.push(...pageErrors);
      return { context, page, metrics };
    } catch (error) {
      lastError = error;
      await context.close();
      if (attempt < 3) await delay(1500);
    }
  }
  throw new Error(`Competitive preview did not become stable after 3 attempts: ${String(lastError)}`);
}

async function captureFrames(browser, args, tempDir) {
  const entries = [];
  const motionFrames = [];
  for (const capture of CAPTURES) {
    const diagnostics = { console_messages: [], request_failures: [], page_errors: [] };
    const { context, page, metrics } = await openPreviewPage(browser, args, capture.viewport, diagnostics);
    try {
      await scrollToSelector(page, capture.scrollSelector);
      await scrollToText(page, capture.scrollText);
      await assertNoRuntimeOverlay(page, capture.key);
      const filePath = path.join(tempDir, capture.filename);
      await page.screenshot({ path: filePath, type: "png", fullPage: false });
      const size = fs.statSync(filePath).size;
      if (size < MIN_CAPTURE_BYTES) {
        throw new Error(`${capture.filename} is only ${size} bytes; refusing to publish a likely blank capture.`);
      }
      entries.push({
        ...capture,
        file: capture.filename,
        file_size_bytes: size,
        sha256: sha256File(filePath),
        browser_metrics: metrics,
        diagnostics,
        source_mode: "read_only_preview",
        physical_device_capture: false,
      });
      if (capture.formFactor === "desktop_browser") motionFrames.push(filePath);
    } finally {
      await context.close();
    }
  }
  return { entries, motionFrames };
}

async function sampleBrowserMetrics(browser, args) {
  const profiles = {
    desktop_browser: { width: 1600, height: 1100, deviceScaleFactor: 1 },
    mobile_viewport: { width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true },
  };
  const sampled = {};
  for (const [profile, viewport] of Object.entries(profiles)) {
    const samples = [];
    for (let index = 0; index < args.samples; index += 1) {
      const diagnostics = { console_messages: [], request_failures: [], page_errors: [] };
      const { context, metrics } = await openPreviewPage(browser, args, viewport, diagnostics);
      try {
        samples.push({ sample: index + 1, ...metrics, diagnostics });
      } finally {
        await context.close();
      }
    }
    const nav = samples.map((sample) => sample.navigation || {});
    const paint = samples.map((sample) => sample.paint || {});
    const resource = samples.map((sample) => sample.resources || {});
    sampled[profile] = {
      viewport: { ...viewport, physical_device_capture: false },
      samples,
      median: {
        capture_ready_ms: median(samples.map((sample) => sample.capture_ready_ms)),
        response_end_ms: median(nav.map((entry) => entry.response_end_ms)),
        dom_content_loaded_ms: median(nav.map((entry) => entry.dom_content_loaded_ms)),
        load_event_end_ms: median(nav.map((entry) => entry.load_event_end_ms)),
        first_paint_ms: median(paint.map((entry) => entry.first_paint_ms)),
        first_contentful_paint_ms: median(paint.map((entry) => entry.first_contentful_paint_ms)),
        resource_count: median(resource.map((entry) => entry.count)),
        resource_transfer_size_bytes: median(resource.map((entry) => entry.transfer_size_bytes)),
      },
    };
  }
  return sampled;
}

function generatePerformanceSvg(browserMetrics) {
  const rows = [
    ["桌面浏览器", browserMetrics.desktop_browser],
    ["移动 CSS 视口", browserMetrics.mobile_viewport],
  ].map(([label, profile], index) => {
    const metrics = profile.median;
    const y = 205 + index * 142;
    return `
      <rect x="48" y="${y - 34}" width="1104" height="112" rx="20" fill="#ffffff" stroke="#dbe4ee" />
      <text x="78" y="${y}" font-size="22" font-weight="700" fill="#14213d">${escapeXml(label)}</text>
      <text x="78" y="${y + 29}" font-size="15" fill="#5b667a">${profile.samples.length} 次本地浏览器导航采样的中位数</text>
      <text x="455" y="${y - 2}" font-size="15" fill="#5b667a">Ready</text>
      <text x="455" y="${y + 25}" font-size="25" font-weight="700" fill="#0f766e">${escapeXml(formatMetric(metrics.capture_ready_ms))}</text>
      <text x="650" y="${y - 2}" font-size="15" fill="#5b667a">DCL</text>
      <text x="650" y="${y + 25}" font-size="25" font-weight="700" fill="#0f766e">${escapeXml(formatMetric(metrics.dom_content_loaded_ms))}</text>
      <text x="825" y="${y - 2}" font-size="15" fill="#5b667a">FCP</text>
      <text x="825" y="${y + 25}" font-size="25" font-weight="700" fill="#0f766e">${escapeXml(formatMetric(metrics.first_contentful_paint_ms))}</text>
      <text x="1005" y="${y - 2}" font-size="15" fill="#5b667a">Resources</text>
      <text x="1005" y="${y + 25}" font-size="25" font-weight="700" fill="#0f766e">${escapeXml(formatMetric((metrics.resource_transfer_size_bytes || 0) / 1024, "KiB"))}</text>`;
  }).join("\n");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="430" viewBox="0 0 1200 430" role="img" aria-label="Anti-FOMO competitive preview local browser metric summary">
  <rect width="1200" height="430" fill="#f7fafc" />
  <text x="48" y="68" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="32" font-weight="700" fill="#14213d">Anti-FOMO /competitive 浏览器采样</text>
  <text x="48" y="103" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="17" fill="#5b667a">只读 preview · 本地环境 · 非生产压测 · 非真机测试</text>
  <g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">${rows}</g>
  <text x="48" y="405" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="14" fill="#6b7280">Ready = 页面满足 /competitive 预览内容断言的总耗时；DCL/FCP 来自浏览器 Performance API。</text>
</svg>`;
}

function generateMotion(ffmpegPath, motionFrames, tempDir) {
  const frameDir = path.join(tempDir, "motion-frames");
  fs.mkdirSync(frameDir, { recursive: true });
  motionFrames.forEach((frame, index) => fs.copyFileSync(frame, path.join(frameDir, `frame-${String(index + 1).padStart(2, "0")}.png`)));
  const mp4Path = path.join(tempDir, "competitive-preview-demo.mp4");
  const gifPath = path.join(tempDir, "competitive-preview-demo.gif");
  const inputPattern = path.join(frameDir, "frame-%02d.png");
  const mp4 = spawnSync(
    ffmpegPath,
    ["-y", "-framerate", "1", "-i", inputPattern, "-vf", "scale=1200:-2:flags=lanczos,format=yuv420p", "-movflags", "+faststart", mp4Path],
    { encoding: "utf8" },
  );
  if (mp4.status !== 0) throw new Error(`ffmpeg MP4 generation failed: ${mp4.stderr.slice(-1000)}`);
  const gif = spawnSync(
    ffmpegPath,
    ["-y", "-framerate", "1", "-i", inputPattern, "-vf", "fps=10,scale=960:-2:flags=lanczos", "-loop", "0", gifPath],
    { encoding: "utf8" },
  );
  if (gif.status !== 0) throw new Error(`ffmpeg GIF generation failed: ${gif.stderr.slice(-1000)}`);
  return ["competitive-preview-demo.mp4", "competitive-preview-demo.gif"];
}

function copyCuratedArtifacts(tempDir, outputDir, names) {
  fs.mkdirSync(outputDir, { recursive: true });
  for (const name of names) {
    fs.copyFileSync(path.join(tempDir, name), path.join(outputDir, name));
  }
}

async function main() {
  const rawArgs = parseArgs(process.argv);
  const args = {
    ...rawArgs,
    frontendUrl: normalizeUrl(rawArgs.frontendUrl),
    apiBase: normalizeUrl(rawArgs.apiBase),
  };
  const previewVerification = await verifyLocalPreview(args);
  const preview = previewVerification.summary;
  args.previewPayloads = previewVerification.previewPayloads;
  const chromePath = resolveChromePath(args.chromePath);
  const ffmpegPath = args.generateMotion ? resolveExecutable("ffmpeg") : null;
  if (args.generateMotion && !ffmpegPath) {
    throw new Error("ffmpeg is required for GIF/MP4 evidence. Install it or rerun with --no-motion for PNG and JSON only.");
  }
  const outputDir = path.resolve(args.outputDir);
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "anti-fomo-competitive-evidence-"));
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: args.headless ? "new" : false,
    protocolTimeout: 120000,
    args: ["--no-first-run", "--no-default-browser-check"],
  });
  try {
    const captured = await captureFrames(browser, args, tempDir);
    const browserMetrics = await sampleBrowserMetrics(browser, args);
    const performanceFilename = "competitive-browser-performance.json";
    const performanceSvgFilename = "competitive-browser-performance.svg";
    const performance = {
      schema_version: "anti-fomo-competitive-browser-metrics/v1",
      generated_at: new Date().toISOString(),
      source_mode: "read_only_preview",
      startup_behavior: "does_not_start_or_stop_services",
      claim_boundary: {
        local_browser_measurement_only: true,
        physical_device_capture: false,
        production_performance_benchmark: false,
        release_approval_evidence: false,
      },
      frontend_url: args.frontendUrl,
      api_base: args.apiBase,
      preview,
      browser_metrics: browserMetrics,
    };
    fs.writeFileSync(path.join(tempDir, performanceFilename), `${JSON.stringify(performance, null, 2)}\n`, "utf8");
    fs.writeFileSync(path.join(tempDir, performanceSvgFilename), generatePerformanceSvg(browserMetrics), "utf8");
    const motionFilenames = args.generateMotion ? generateMotion(ffmpegPath, captured.motionFrames, tempDir) : [];
    const manifestFilename = "competitive-evidence-manifest.json";
    const artifactNames = [
      ...captured.entries.map((entry) => entry.file),
      ...motionFilenames,
      performanceFilename,
      performanceSvgFilename,
    ];
    const manifest = {
      schema_version: "anti-fomo-competitive-evidence/v1",
      generated_at: new Date().toISOString(),
      source_mode: "read_only_preview",
      startup_behavior: "does_not_start_or_stop_services",
      physical_device_capture: false,
      production_claim: false,
      release_approval_evidence: false,
      capture_scope: "local browser and simulated mobile CSS viewport",
      preview,
      capture_entries: captured.entries,
      artifacts: artifactNames.map((name) => ({
        file: `docs/assets/competitive-evidence/${name}`,
        file_size_bytes: fs.statSync(path.join(tempDir, name)).size,
        sha256: sha256File(path.join(tempDir, name)),
      })),
    };
    fs.writeFileSync(path.join(tempDir, manifestFilename), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    copyCuratedArtifacts(tempDir, outputDir, [...artifactNames, manifestFilename]);
    console.log(
      JSON.stringify(
        {
          status: "ok",
          output_dir: outputDir,
          captures: captured.entries.length,
          motion: motionFilenames,
          performance_samples_per_viewport: args.samples,
          mode: "read_only_preview",
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
