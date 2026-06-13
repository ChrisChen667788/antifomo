#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const SCREENSHOT_SCROLL_TOP_PADDING = 132;
const SCREENSHOT_PREFERENCES = {
  fontFamily: "system",
  textSize: "md",
  language: "zh-CN",
};
const DARK_THEME_FEATURES = new Set([
  "Home signal dashboard",
  "Inbox research workspace",
  "Research center dashboard",
  "Settings and tuning workspace",
]);
const MIN_SCREENSHOT_BYTES = 40_000;
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
    if (token === "--headful") {
      args.headless = false;
    }
  }

  return args;
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
    console.warn(`[screenshots] knowledge fetch failed: ${response.status}`);
    return [];
  }
  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}

function createCaptureManifestEntry(item, outputDir) {
  const filePath = path.join(outputDir, item.filename);
  const stats = fs.statSync(filePath);
  return {
    feature: item.feature,
    route: item.route,
    theme: item.theme,
    file: `docs/assets/screenshots/${item.filename}`,
    description: item.description,
    quality_gate: {
      status: "accepted",
      min_file_size_bytes: MIN_SCREENSHOT_BYTES,
      actual_file_size_bytes: stats.size,
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
  const mergeRoute =
    mergeEntryIds.length >= 2
      ? `/knowledge/merge?ids=${mergeEntryIds.map((id) => encodeURIComponent(id)).join(",")}&title=${encodeURIComponent("政务云投标推进材料合并")}`
      : "/knowledge/merge";

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
      filename: "research-center-dashboard.png",
      description: "Research center overview for watchlists, archives, retrieval health, architecture readiness, and delivery diagnostics.",
    },
    {
      feature: "Research topic workspace",
      route: topicId ? `/research/topics/${topicId}` : "/research",
      waitText: "专题工作台",
      filename: "research-topic-workspace.png",
      description: "Topic-version workspace for evidence density, follow-up impact, and long-running changes.",
    },
    {
      feature: "Research compare workspace",
      route: snapshotId && topicId ? `/research/compare?snapshot=${snapshotId}&topicId=${topicId}` : "/research/compare",
      waitText: "对比矩阵",
      filename: "research-compare-workspace.png",
      description: "Multi-version comparison matrix for account, competitor, evidence, and delivery deltas.",
    },
    {
      feature: "Research experiment orchestration",
      route: "/research",
      waitText: "实验编排层",
      scrollSelector: "[data-screenshot-anchor='research-experiment-control-plane']",
      scrollText: "实验编排层",
      filename: "research-experiment-control-plane.png",
      description: "Configurable strategy plans, frozen cohorts, locked baselines, rollout gates, and runtime policy diagnostics.",
    },
    ...(archiveId
      ? [
          {
            feature: "Research archive viewer",
            route: `/research/archives/${archiveId}`,
            waitText: "Markdown 归档",
            filename: "research-archive-viewer.png",
            description: "Historical Markdown archive viewer with delivery digest, section links, and version context.",
          },
        ]
      : []),
  ].map((item) => ({ ...item, theme: "light" }));

  const darkCaptures = lightCaptures
    .filter((item) => DARK_THEME_FEATURES.has(item.feature))
    .map((item) => ({
      ...item,
      theme: "dark",
      filename: item.filename.replace(/\.png$/, "-dark.png"),
      description: `${item.description} Dark-theme regression baseline.`,
    }));

  return [...lightCaptures, ...darkCaptures];
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
    console.warn(`[screenshots] text not found before capture: "${text}"`);
    return false;
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
  if (!selector) return;
  await page.waitForSelector(selector, { timeout: 45000 });
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

async function capturePage(page, { baseUrl, route, theme, waitText, scrollSelector, scrollText, filePath }) {
  const targetUrl = `${baseUrl.replace(/\/+$/, "")}${route}`;
  console.log(`[screenshots] capturing ${path.basename(filePath)} from ${route}`);
  await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await waitForPageContent(page, route);
  await assertThemeApplied(page, theme, filePath);
  await waitForText(page, waitText);
  await waitForCaptureAnchor(page, scrollSelector);
  await scrollToSelector(page, scrollSelector);
  await scrollToText(page, scrollText);
  await assertNoRuntimeOverlay(page, filePath);
  await hideDevelopmentChrome(page);
  await page.screenshot({
    path: filePath,
    fullPage: false,
    type: "png",
  });
  validateScreenshotFile(filePath);
}

async function main() {
  const args = parseArgs(process.argv);
  const chromePath = resolveChromePath(args.chromePath);
  const outputDir = path.resolve(args.outputDir);
  fs.mkdirSync(outputDir, { recursive: true });

  const [workspace, knowledgeEntries] = await Promise.all([
    fetchWorkspace(args.apiBase),
    fetchKnowledgeEntries(args.apiBase),
  ]);
  const captures = buildCaptures(workspace, knowledgeEntries);

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

  try {
    const manifestEntries = [];
    for (const item of captures) {
      const page = await browser.newPage();
      try {
        await preparePageForCapture(page, item.theme);
        await capturePage(page, {
          baseUrl: args.frontendUrl,
          route: item.route,
          theme: item.theme,
          waitText: item.waitText,
          scrollSelector: item.scrollSelector,
          scrollText: item.scrollText,
          filePath: path.join(outputDir, item.filename),
        });
        manifestEntries.push(createCaptureManifestEntry(item, outputDir));
      } finally {
        await page.close();
      }
    }
    const manifest = {
      version: readPackageVersion(),
      generated_at: new Date().toISOString(),
      viewport: {
        width: 1600,
        height: 1100,
        device_scale_factor: 1.2,
      },
      quality_gate: {
        min_file_size_bytes: MIN_SCREENSHOT_BYTES,
        runtime_overlay_check: true,
        expected_screenshot_count: captures.length,
        accepted_screenshot_count: manifestEntries.length,
      },
      screenshots: manifestEntries,
    };
    fs.writeFileSync(path.join(outputDir, "screenshot-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
