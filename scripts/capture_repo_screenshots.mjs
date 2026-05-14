#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const SCREENSHOT_SCROLL_TOP_PADDING = 64;
const SCREENSHOT_PREFERENCES = {
  themeMode: "light",
  fontFamily: "system",
  textSize: "md",
  language: "zh-CN",
};
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

async function fetchWorkspace(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/+$/, "")}/api/research/workspace`);
  if (!response.ok) {
    throw new Error(`Workspace fetch failed: ${response.status}`);
  }
  return response.json();
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

async function preparePageForCapture(page) {
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await page.evaluateOnNewDocument((preferences) => {
    window.localStorage.setItem("anti_fomo_app_preferences_v1", JSON.stringify(preferences));
  }, SCREENSHOT_PREFERENCES);
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

async function capturePage(page, { baseUrl, route, waitText, scrollSelector, scrollText, filePath }) {
  const targetUrl = `${baseUrl.replace(/\/+$/, "")}${route}`;
  console.log(`[screenshots] capturing ${path.basename(filePath)} from ${route}`);
  await page.goto(targetUrl, { waitUntil: "networkidle2", timeout: 30000 });
  await waitForText(page, waitText);
  await scrollToSelector(page, scrollSelector);
  await scrollToText(page, scrollText);
  await assertNoRuntimeOverlay(page, filePath);
  await hideDevelopmentChrome(page);
  await page.screenshot({
    path: filePath,
    fullPage: false,
    type: "png",
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const chromePath = resolveChromePath(args.chromePath);
  const outputDir = path.resolve(args.outputDir);
  fs.mkdirSync(outputDir, { recursive: true });

  const workspace = await fetchWorkspace(args.apiBase);
  const topicId = workspace?.tracking_topics?.[0]?.id || "";
  const snapshotId = workspace?.compare_snapshots?.[0]?.id || "";

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
    const captures = [
      {
        route: "/inbox",
        waitText: "添加内容",
        filename: "inbox-research-workspace.png",
      },
      {
        route: topicId ? `/research/topics/${topicId}` : "/research",
        waitText: "专题工作台",
        filename: "research-topic-workspace.png",
      },
      {
        route: snapshotId && topicId ? `/research/compare?snapshot=${snapshotId}&topicId=${topicId}` : "/research/compare",
        waitText: "对比矩阵",
        filename: "research-compare-workspace.png",
      },
      {
        route: "/research",
        waitText: "实验编排层",
        scrollSelector: "[data-screenshot-anchor='research-experiment-control-plane']",
        scrollText: "实验编排层",
        filename: "research-experiment-control-plane.png",
      },
      {
        route: "/knowledge/accounts",
        waitText: "账户情报",
        filename: "knowledge-commercial-hub.png",
      },
    ];

    for (const item of captures) {
      const page = await browser.newPage();
      try {
        await preparePageForCapture(page);
        await capturePage(page, {
          baseUrl: args.frontendUrl,
          route: item.route,
          waitText: item.waitText,
          scrollSelector: item.scrollSelector,
          scrollText: item.scrollText,
          filePath: path.join(outputDir, item.filename),
        });
      } finally {
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
