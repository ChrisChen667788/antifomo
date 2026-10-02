#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const DEFAULT_IMPLEMENTATION_LINE = "2.11.8-development";
const SCREENSHOT_SCROLL_TOP_PADDING = 132;
const SCREENSHOT_PREFERENCES = {
  fontFamily: "system",
  textSize: "md",
  language: "zh-CN",
};
const DARK_THEME_FEATURES = new Set([
  "Home signal dashboard",
  "Inbox research workspace",
  "Saved read-later workspace",
  "Focus session workspace",
  "Session summary workspace",
  "Collector operations workspace",
  "Research center dashboard",
  "Research topic workspace",
  "Research compare workspace",
  "Research experiment orchestration",
  "Research archive viewer",
  "Settings and tuning workspace",
  "Knowledge library workspace",
  "Knowledge commercial hub",
  "Knowledge merge workflow",
  "Competitive evidence ledger",
  "Decision Studio workspace",
]);
const MIN_SCREENSHOT_BYTES = 40_000;
const EXPECTED_PRIMARY_SURFACE_COUNT = 17;
const EXPECTED_SCREENSHOT_COUNT = EXPECTED_PRIMARY_SURFACE_COUNT * 2;
const CHROME_COMMAND_CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"];
const CHROME_PATH_CANDIDATES = [
  DEFAULT_MAC_CHROME_PATH,
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium-browser",
  "/usr/bin/chromium",
];

function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    apiBase: DEFAULT_API_BASE,
    outputDir: "docs/assets/screenshots",
    chromePath: process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH || "",
    headless: true,
    implementationLine: process.env.SCREENSHOT_IMPLEMENTATION_LINE || DEFAULT_IMPLEMENTATION_LINE,
    dataMode: process.env.SCREENSHOT_DATA_MODE || "unspecified_local_api",
    allowDirty: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--frontend-url" && next) {
      args.frontendUrl = next;
      i += 1;
      continue;
    }
    if (token === "--api-base" && next) {
      args.apiBase = next;
      i += 1;
      continue;
    }
    if (token === "--output-dir" && next) {
      args.outputDir = next;
      i += 1;
      continue;
    }
    if (token === "--chrome-path" && next) {
      args.chromePath = next;
      i += 1;
      continue;
    }
    if (token === "--implementation-line" && next) {
      args.implementationLine = next;
      i += 1;
      continue;
    }
    if (token === "--data-mode" && next) {
      args.dataMode = next;
      i += 1;
      continue;
    }
    if (token === "--headful") {
      args.headless = false;
      continue;
    }
    if (token === "--allow-dirty") {
      args.allowDirty = true;
    }
  }

  return args;
}

function assertLoopbackUrl(value, label) {
  const parsed = new URL(value);
  if (!["127.0.0.1", "localhost", "::1"].includes(parsed.hostname)) {
    throw new Error(`${label} must use a loopback host for local screenshot evidence: ${value}`);
  }
}

function resolveChromePath(requestedPath) {
  const candidates = [requestedPath, process.env.CHROME_PATH, process.env.PUPPETEER_EXECUTABLE_PATH, ...CHROME_PATH_CANDIDATES]
    .map((value) => value?.trim())
    .filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  for (const command of CHROME_COMMAND_CANDIDATES) {
    const result = spawnSync("which", [command], { encoding: "utf8" });
    if (result.status === 0) {
      const executablePath = result.stdout.trim();
      if (executablePath && fs.existsSync(executablePath)) {
        return executablePath;
      }
    }
  }
  throw new Error(
    `Chrome executable not found. Checked paths: ${candidates.join(", ") || "(none)"}; commands: ${CHROME_COMMAND_CANDIDATES.join(", ")}`,
  );
}

function readPackageVersion() {
  try {
    const packageJson = JSON.parse(fs.readFileSync(path.resolve("package.json"), "utf8"));
    return packageJson.version || "unknown";
  } catch {
    return "unknown";
  }
}

function readGitMetadata() {
  const commit = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" });
  const status = spawnSync("git", ["status", "--porcelain"], { encoding: "utf8" });
  return {
    commit: commit.status === 0 ? commit.stdout.trim() : "unknown",
    working_tree_dirty: status.status !== 0 || Boolean(status.stdout.trim()),
  };
}

async function fetchWorkspace(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/+$/, "")}/api/research/workspace`);
  if (!response.ok) {
    throw new Error(`Workspace fetch failed: ${response.status}`);
  }
  return response.json();
}

async function fetchKnowledgeEntries(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/+$/, "")}/api/knowledge?limit=2`);
  if (!response.ok) {
    throw new Error(`Knowledge fixture fetch failed: ${response.status}`);
  }
  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function readPngDimensions(filePath) {
  const buffer = fs.readFileSync(filePath);
  const signature = buffer.subarray(0, 8).toString("hex");
  if (signature !== "89504e470d0a1a0a" || buffer.length < 24) {
    throw new Error(`Screenshot is not a valid PNG: ${path.basename(filePath)}`);
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function createStagingDirectory(publishDir) {
  const parentDir = path.dirname(publishDir);
  const baseName = path.basename(publishDir);
  fs.mkdirSync(parentDir, { recursive: true });
  return fs.mkdtempSync(path.join(parentDir, `.${baseName}.staging-`));
}

function publishDirectoryAtomically(stagingDir, publishDir) {
  const backupDir = `${publishDir}.backup-${process.pid}-${Date.now()}`;
  const hadPreviousDirectory = fs.existsSync(publishDir);
  if (hadPreviousDirectory) fs.renameSync(publishDir, backupDir);
  try {
    fs.renameSync(stagingDir, publishDir);
  } catch (error) {
    if (hadPreviousDirectory && fs.existsSync(backupDir) && !fs.existsSync(publishDir)) {
      fs.renameSync(backupDir, publishDir);
    }
    throw error;
  }
  if (hadPreviousDirectory) {
    try {
      fs.rmSync(backupDir, { recursive: true, force: true });
    } catch (error) {
      console.warn(`[screenshots] published successfully but could not remove ${backupDir}: ${String(error)}`);
    }
  }
}

function createCaptureManifestEntry(item, stagingDir, publishDir, diagnostics) {
  const filePath = path.join(stagingDir, item.filename);
  const stats = fs.statSync(filePath);
  const png = fs.readFileSync(filePath);
  const relativeRepositoryPath = path.relative(process.cwd(), path.join(publishDir, item.filename));
  const repositoryFile =
    !path.isAbsolute(relativeRepositoryPath) && !relativeRepositoryPath.startsWith(`..${path.sep}`)
      ? relativeRepositoryPath.split(path.sep).join("/")
      : null;
  return {
    feature: item.feature,
    route: item.route,
    theme: item.theme,
    file: item.filename,
    repository_file: repositoryFile,
    sha256: sha256(png),
    pixel_dimensions: readPngDimensions(filePath),
    description: item.description,
    quality_gate: {
      automated_status: "passed",
      min_file_size_bytes: MIN_SCREENSHOT_BYTES,
      actual_file_size_bytes: stats.size,
      console_error_count: diagnostics.consoleErrors.length,
      request_failure_count: diagnostics.requestFailures.length,
      http_error_count: diagnostics.responseErrors.length,
      page_error_count: diagnostics.pageErrors.length,
      readiness_mode: diagnostics.readinessMode,
    },
  };
}

function validateScreenshotFile(filePath) {
  const stats = fs.statSync(filePath);
  if (stats.size < MIN_SCREENSHOT_BYTES) {
    throw new Error(
      `Screenshot ${path.basename(filePath)} is only ${stats.size} bytes; expected at least ${MIN_SCREENSHOT_BYTES} bytes.`,
    );
  }
}

function buildCaptures(workspace, knowledgeEntries) {
  const topicId = workspace?.tracking_topics?.[0]?.id || "";
  const snapshotId = workspace?.compare_snapshots?.[0]?.id || "";
  const archiveId = workspace?.markdown_archives?.[0]?.id || "";
  const mergeEntryIds = (knowledgeEntries || [])
    .map((entry) => entry?.id)
    .filter(Boolean)
    .slice(0, 2);
  const missingFixtures = [];
  if (!topicId) missingFixtures.push("tracking topic");
  if (!snapshotId) missingFixtures.push("compare snapshot");
  if (!archiveId) missingFixtures.push("markdown archive");
  if (mergeEntryIds.length < 2) missingFixtures.push("two knowledge entries");
  if (missingFixtures.length) {
    throw new Error(`Screenshot fixture set is incomplete: ${missingFixtures.join(", ")}.`);
  }
  const mergeRoute = `/knowledge/merge?ids=${mergeEntryIds.map((id) => encodeURIComponent(id)).join(",")}&title=${encodeURIComponent("政务云投标推进材料合并")}`;

  const lightCaptures = [
    {
      feature: "Home signal dashboard",
      route: "/",
      waitText: "Anti-FOMO",
      filename: "home-signal-dashboard.png",
      description: "Feed triage homepage with WeChat Favorites import, latest-batch review, and quick route switching.",
    },
    {
      feature: "Inbox research workspace",
      route: "/inbox",
      waitText: "添加内容",
      filename: "inbox-research-workspace.png",
      description: "Intake, keyword research, report generation, architecture readiness, architect workbench review, and formal delivery export workspace.",
    },
    {
      feature: "Saved read-later workspace",
      route: "/saved",
      waitText: "稍后再读",
      filename: "saved-readlater-workspace.png",
      description: "Saved-item and read-later review surface with topic and scoring context.",
    },
    {
      feature: "Focus session workspace",
      route: "/focus",
      waitText: "专注模式",
      filename: "focus-session-workspace.png",
      description: "Focused execution timer with headless-source-first collector startup and WeChat PC supplementary harvesting.",
    },
    {
      feature: "Session summary workspace",
      route: "/session-summary",
      waitText: "专注总结",
      filename: "session-summary-workspace.png",
      description: "Session metrics, markdown summary, reading list, and follow-up draft workspace.",
    },
    {
      feature: "Collector operations workspace",
      route: "/collector",
      waitText: "采集器",
      filename: "collector-operations-workspace.png",
      description: "Desktop collector, source health diagnostics, coverage rates, OCR backfill, pending queue, and daily export operations panel.",
    },
    {
      feature: "Settings and tuning workspace",
      route: "/settings",
      waitText: "设置",
      filename: "settings-tuning-workspace.png",
      description: "Preference, WorkBuddy, collector, and recommender tuning controls.",
    },
    {
      feature: "Knowledge library workspace",
      route: "/knowledge",
      waitText: "知识库",
      filename: "knowledge-library-workspace.png",
      description: "Knowledge list, commercial dashboard, account signals, and saved intelligence cards.",
    },
    {
      feature: "Knowledge commercial hub",
      route: "/knowledge/accounts",
      waitText: "账户情报",
      filename: "knowledge-commercial-hub.png",
      description: "Account intelligence, opportunity context, review queues, and commercial follow-up actions.",
    },
    {
      feature: "Knowledge merge workflow",
      route: mergeRoute,
      waitText: "知识卡片合并",
      filename: "knowledge-merge-workflow.png",
      description: "Knowledge-card merge preview, inherited state checks, and target-title workflow.",
    },
    {
      feature: "Research center dashboard",
      route: "/research",
      waitText: "商机情报中心",
      readySelector: "[data-screenshot-anchor='research-experiment-control-plane']",
      waitUntilTextGone: "加载中",
      filename: "research-center-dashboard.png",
      description: "Research center overview for watchlists, archives, retrieval health, architecture readiness, and delivery diagnostics.",
    },
    {
      feature: "Competitive evidence ledger",
      route: "/competitive",
      waitText: "官方能力观察",
      filename: "competitive-evidence-ledger.png",
      description: "Competitive evidence ledger separating vendor claims, local implementation, acceptance gates, and release status.",
    },
    {
      feature: "Decision Studio workspace",
      route: "/studio",
      waitText: "Decision Studio",
      filename: "decision-studio-workspace.png",
      description: "Evidence-bound notebook, claim graph, document governance, and decision-program workspace.",
    },
    {
      feature: "Research topic workspace",
      route: `/research/topics/${topicId}`,
      waitText: "专题工作台",
      filename: "research-topic-workspace.png",
      description: "Topic-version workspace for evidence density, follow-up impact, and long-running changes.",
    },
    {
      feature: "Research compare workspace",
      route: `/research/compare?snapshot=${snapshotId}&topicId=${topicId}`,
      waitText: "对比矩阵",
      filename: "research-compare-workspace.png",
      description: "Multi-version comparison matrix for account, competitor, evidence, and delivery deltas.",
    },
    {
      feature: "Research experiment orchestration",
      route: "/research",
      waitText: "报告质量",
      scrollSelector: "[data-screenshot-anchor='research-experiment-control-plane']",
      scrollText: "策略发布",
      waitUntilTextGone: "加载中",
      filename: "research-experiment-control-plane.png",
      description: "Configurable strategy plans, frozen cohorts, locked baselines, rollout gates, and runtime policy diagnostics.",
    },
    {
      feature: "Research archive viewer",
      route: `/research/archives/${archiveId}`,
      waitText: "历史归档",
      filename: "research-archive-viewer.png",
      description: "Historical Markdown archive viewer with delivery digest, section links, and version context.",
    },
  ].map((item) => ({ ...item, theme: "light" }));

  const darkCaptures = lightCaptures
    .filter((item) => DARK_THEME_FEATURES.has(item.feature))
    .map((item) => ({
      ...item,
      theme: "dark",
      filename: item.filename.replace(/\.png$/, "-dark.png"),
      description: `${item.description} Dark-theme regression baseline.`,
    }));

  const captures = [...lightCaptures, ...darkCaptures];
  if (lightCaptures.length !== EXPECTED_PRIMARY_SURFACE_COUNT || captures.length !== EXPECTED_SCREENSHOT_COUNT) {
    throw new Error(
      `Screenshot matrix mismatch: expected ${EXPECTED_PRIMARY_SURFACE_COUNT} surfaces and ${EXPECTED_SCREENSHOT_COUNT} captures, received ${lightCaptures.length} and ${captures.length}.`,
    );
  }
  const filenames = new Set(captures.map((item) => item.filename));
  if (filenames.size !== captures.length) throw new Error("Screenshot matrix contains duplicate filenames.");
  return captures;
}

async function waitForText(page, text) {
  if (!text) return true;
  try {
    await page.waitForFunction(
      (expected) => document.body?.innerText?.includes(expected),
      { timeout: 20000 },
      text,
    );
    return true;
  } catch {
    throw new Error(`Required text did not render before capture: "${text}"`);
  }
}

async function waitForTextToDisappear(page, text) {
  if (!text) return;
  try {
    await page.waitForFunction(
      (expected) => !document.body?.innerText?.includes(expected),
      { timeout: 120000 },
      text,
    );
  } catch {
    throw new Error(`Loading text did not clear before capture: "${text}"`);
  }
}

function attachDiagnostics(page, monitoredOrigins) {
  const diagnostics = {
    consoleErrors: [],
    requestFailures: [],
    responseErrors: [],
    pageErrors: [],
    readinessMode: "pending",
  };
  const isMonitored = (value) => {
    try {
      return monitoredOrigins.has(new URL(value).origin);
    } catch {
      return false;
    }
  };
  page.on("console", (message) => {
    if (message.type() === "error") diagnostics.consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const error = request.failure()?.errorText || "unknown";
    if (!isMonitored(request.url()) || error.includes("ERR_ABORTED")) return;
    diagnostics.requestFailures.push({
      url: request.url(),
      resource_type: request.resourceType(),
      error,
    });
  });
  page.on("response", (response) => {
    if (response.status() < 400 || !isMonitored(response.url())) return;
    try {
      if (new URL(response.url()).pathname === "/favicon.ico") return;
    } catch {
      // The monitored-origin check already parsed the URL; keep this response if parsing changes unexpectedly.
    }
    diagnostics.responseErrors.push({
      url: response.url(),
      status: response.status(),
      resource_type: response.request().resourceType(),
    });
  });
  page.on("pageerror", (error) => diagnostics.pageErrors.push(String(error)));
  return diagnostics;
}

async function waitForCaptureStability(page, route, diagnostics) {
  try {
    await page.waitForNetworkIdle({ idleTime: 600, timeout: 8000 });
    diagnostics.readinessMode = "network_idle";
    return;
  } catch {
    // Research surfaces may keep polling the local API after their visible state settles.
  }

  const deadline = Date.now() + 30000;
  let previousSnapshot = "";
  let stableSamples = 0;
  while (Date.now() < deadline) {
    const snapshot = await page.evaluate(() =>
      JSON.stringify({
        readyState: document.readyState,
        text: (document.body?.innerText || "").trim(),
        scrollHeight: document.documentElement.scrollHeight,
      }),
    );
    if (snapshot === previousSnapshot) {
      stableSamples += 1;
      if (stableSamples >= 3) {
        diagnostics.readinessMode = "dom_stable_with_background_network";
        return;
      }
    } else {
      previousSnapshot = snapshot;
      stableSamples = 0;
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(`Page did not reach network-idle or a stable rendered state before capture: ${route}`);
}

async function assertHealthyCapture(page, route, diagnostics) {
  const bodyText = await page.evaluate(() => (document.body?.innerText || "").trim());
  if (bodyText.length < 200) {
    throw new Error(`Critical page content is too short for ${route}: ${bodyText.length} characters.`);
  }
  const failureMarkers = ["Internal Server Error", "Unhandled Runtime Error"];
  const marker = failureMarkers.find((value) => bodyText.includes(value));
  if (marker) {
    throw new Error(`Page ${route} contains a failure marker: ${marker}`);
  }
  if (
    diagnostics.pageErrors.length ||
    diagnostics.requestFailures.length ||
    diagnostics.responseErrors.length ||
    diagnostics.consoleErrors.length
  ) {
    throw new Error(
      `Browser diagnostics failed for ${route}: ${JSON.stringify(diagnostics)}`,
    );
  }
}

async function waitForPageContent(page, route) {
  try {
    await page.waitForFunction(
      () => (document.body?.innerText || "").trim().length > 40,
      { timeout: 30000 },
    );
  } catch {
    throw new Error(`Page content did not render before capture: ${route}`);
  }
}

async function waitForCaptureAnchor(page, selector) {
  if (!selector) return false;
  try {
    await page.waitForSelector(selector, { timeout: 120000 });
    return true;
  } catch {
    console.warn(`[screenshots] capture anchor not rendered: "${selector}"`);
    return false;
  }
}

async function scrollToText(page, text) {
  if (!text) return;
  await page.evaluate((expected, topPadding) => {
    document.documentElement.style.scrollBehavior = "auto";
    document.body.style.scrollBehavior = "auto";
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (node.textContent?.includes(expected)) {
        const element = node.parentElement?.closest("section, article, div") || node.parentElement;
        if (element) {
          const top = element.getBoundingClientRect().top + window.scrollY - topPadding;
          window.scrollTo({ top, left: 0, behavior: "auto" });
        }
        break;
      }
      node = walker.nextNode();
    }
  }, text, SCREENSHOT_SCROLL_TOP_PADDING);
  await new Promise((resolve) => setTimeout(resolve, 450));
}

async function scrollToSelector(page, selector) {
  if (!selector) return;
  await page.evaluate((targetSelector, topPadding) => {
    document.documentElement.style.scrollBehavior = "auto";
    document.body.style.scrollBehavior = "auto";
    const element = document.querySelector(targetSelector);
    if (element) {
      const top = element.getBoundingClientRect().top + window.scrollY - topPadding;
      window.scrollTo({ top, left: 0, behavior: "auto" });
    }
  }, selector, SCREENSHOT_SCROLL_TOP_PADDING);
  await new Promise((resolve) => setTimeout(resolve, 450));
}

async function assertNoRuntimeOverlay(page, filePath) {
  const overlayDetected = await page.evaluate(() => {
    const bodyText = document.body?.innerText || "";
    return (
      bodyText.includes("Runtime SyntaxError") ||
      bodyText.includes("Runtime Error") ||
      bodyText.includes("Unhandled Runtime Error") ||
      bodyText.includes("Unexpected end of JSON input")
    );
  });
  if (overlayDetected) {
    throw new Error(`Runtime overlay detected before writing ${path.basename(filePath)}`);
  }
}

async function preparePageForCapture(page, theme) {
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: theme }]);
  await page.evaluateOnNewDocument((preferences, selectedTheme) => {
    window.localStorage.setItem(
      "anti_fomo_app_preferences_v1",
      JSON.stringify({ ...preferences, themeMode: selectedTheme }),
    );
  }, SCREENSHOT_PREFERENCES, theme);
}

async function assertThemeApplied(page, expectedTheme, filePath) {
  try {
    await page.waitForFunction(
      (theme) => document.documentElement.dataset.afTheme === theme,
      { timeout: 10000 },
      expectedTheme,
    );
  } catch {
    const actualTheme = await page.evaluate(() => document.documentElement.dataset.afTheme || "unset");
    throw new Error(
      `Theme mismatch before writing ${path.basename(filePath)}: expected ${expectedTheme}, received ${actualTheme}.`,
    );
  }
}

async function hideDevelopmentChrome(page) {
  await page.addStyleTag({
    content: `
      nextjs-portal,
      [data-nextjs-toast],
      [data-nextjs-dialog-overlay],
      [data-nextjs-dev-overlay],
      [data-nextjs-build-indicator] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
      }
    `,
  });
}

async function capturePage(
  page,
  { baseUrl, apiBase, route, theme, waitText, readySelector, waitUntilTextGone, scrollSelector, scrollText, filePath },
) {
  const diagnostics = attachDiagnostics(
    page,
    new Set([new URL(baseUrl).origin, new URL(apiBase).origin]),
  );
  const targetUrl = `${baseUrl.replace(/\/+$/, "")}${route}`;
  console.log(`[screenshots] capturing ${path.basename(filePath)} from ${route}`);
  await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await waitForPageContent(page, route);
  await assertThemeApplied(page, theme, filePath);
  await waitForText(page, waitText);
  const requiredSelector = readySelector || scrollSelector;
  const selectorReady = await waitForCaptureAnchor(page, requiredSelector);
  if (requiredSelector && !selectorReady) {
    throw new Error(`Required capture anchor did not render for ${route}: ${requiredSelector}`);
  }
  await waitForTextToDisappear(page, waitUntilTextGone);
  await waitForCaptureStability(page, route, diagnostics);
  await scrollToSelector(page, scrollSelector);
  await scrollToText(page, scrollText);
  await hideDevelopmentChrome(page);
  await page.screenshot({
    path: filePath,
    fullPage: false,
    type: "png",
  });
  await new Promise((resolve) => setTimeout(resolve, 250));
  await assertNoRuntimeOverlay(page, filePath);
  await assertHealthyCapture(page, route, diagnostics);
  validateScreenshotFile(filePath);
  return diagnostics;
}

async function main() {
  const args = parseArgs(process.argv);
  assertLoopbackUrl(args.frontendUrl, "Frontend URL");
  assertLoopbackUrl(args.apiBase, "API base URL");
  const git = readGitMetadata();
  if (git.working_tree_dirty && !args.allowDirty) {
    throw new Error("Refusing to publish screenshot evidence from a dirty working tree. Use --allow-dirty only for disposable preflight captures.");
  }
  const chromePath = resolveChromePath(args.chromePath);
  const publishDir = path.resolve(args.outputDir);

  const [workspace, knowledgeEntries] = await Promise.all([
    fetchWorkspace(args.apiBase),
    fetchKnowledgeEntries(args.apiBase),
  ]);
  const captures = buildCaptures(workspace, knowledgeEntries);
  const fixtureSelection = {
    tracking_topic_id: workspace.tracking_topics[0].id,
    compare_snapshot_id: workspace.compare_snapshots[0].id,
    markdown_archive_id: workspace.markdown_archives[0].id,
    knowledge_entry_ids: knowledgeEntries.slice(0, 2).map((entry) => entry.id),
  };

  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: args.headless ? "new" : false,
    protocolTimeout: 120000,
    defaultViewport: {
      width: 1600,
      height: 1100,
      deviceScaleFactor: 1.2,
    },
    args: ["--no-first-run", "--no-default-browser-check"],
  });
  const stagingDir = createStagingDirectory(publishDir);

  let captureCompleted = false;
  try {
    const manifestEntries = [];
    for (const item of captures) {
      const page = await browser.newPage();
      try {
        await preparePageForCapture(page, item.theme);
        const diagnostics = await capturePage(page, {
          baseUrl: args.frontendUrl,
          apiBase: args.apiBase,
          route: item.route,
          theme: item.theme,
          waitText: item.waitText,
          readySelector: item.readySelector,
          waitUntilTextGone: item.waitUntilTextGone,
          scrollSelector: item.scrollSelector,
          scrollText: item.scrollText,
          filePath: path.join(stagingDir, item.filename),
        });
        manifestEntries.push(createCaptureManifestEntry(item, stagingDir, publishDir, diagnostics));
      } finally {
        await page.close();
      }
    }
    const generatedAt = new Date();
    const packageVersion = readPackageVersion();
    const manifest = {
      schema_version: "anti-fomo-product-screenshots/v2",
      implementation_line: args.implementationLine,
      package_version: packageVersion,
      release_tag: null,
      release_claim: false,
      evidence_tier: "local_browser_capture",
      generated_at: generatedAt.toISOString(),
      source_commit: git.commit,
      source_working_tree_dirty: git.working_tree_dirty,
      declared_data_mode: args.dataMode,
      actual_data_origins: {
        frontend: args.frontendUrl,
        api: args.apiBase,
        workspace_endpoint: "/api/research/workspace",
        knowledge_endpoint: "/api/knowledge?limit=2",
      },
      fixture_selection_digest: sha256(JSON.stringify(fixtureSelection)),
      fixture_counts: {
        tracking_topics: workspace.tracking_topics.length,
        compare_snapshots: workspace.compare_snapshots.length,
        markdown_archives: workspace.markdown_archives.length,
        selected_knowledge_entries: fixtureSelection.knowledge_entry_ids.length,
      },
      browser_version: await browser.version(),
      browser_executable: chromePath,
      human_visual_review_status: "pending",
      human_visual_review_receipt: null,
      viewport: {
        width: 1600,
        height: 1100,
        device_scale_factor: 1.2,
      },
      quality_gate: {
        min_file_size_bytes: MIN_SCREENSHOT_BYTES,
        runtime_overlay_check: true,
        browser_diagnostics_check: true,
        critical_content_check: true,
        expected_primary_surface_count: EXPECTED_PRIMARY_SURFACE_COUNT,
        expected_screenshot_count: EXPECTED_SCREENSHOT_COUNT,
        accepted_screenshot_count: manifestEntries.length,
      },
      screenshots: manifestEntries,
    };
    fs.writeFileSync(path.join(stagingDir, "screenshot-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
    captureCompleted = true;
  } catch (error) {
    fs.rmSync(stagingDir, { recursive: true, force: true });
    throw error;
  } finally {
    await browser.close();
  }
  if (!captureCompleted) {
    fs.rmSync(stagingDir, { recursive: true, force: true });
    return;
  }
  publishDirectoryAtomically(stagingDir, publishDir);
  console.log(`[screenshots] published ${EXPECTED_SCREENSHOT_COUNT} captures to ${publishDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
