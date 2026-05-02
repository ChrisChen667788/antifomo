#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
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
  if (!text) return;
  await page.waitForFunction(
    (expected) => document.body?.innerText?.includes(expected),
    { timeout: 20000 },
    text,
  );
}

async function capturePage(page, { baseUrl, route, waitText, filePath }) {
  const targetUrl = `${baseUrl.replace(/\/+$/, "")}${route}`;
  await page.goto(targetUrl, { waitUntil: "networkidle2", timeout: 30000 });
  await waitForText(page, waitText);
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
    defaultViewport: {
      width: 1600,
      height: 1100,
      deviceScaleFactor: 1.2,
    },
    args: ["--no-first-run", "--no-default-browser-check"],
  });

  try {
    const page = await browser.newPage();
    const captures = [
      {
        route: "/inbox",
        waitText: "生成研报",
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
        route: "/knowledge/accounts",
        waitText: "账户情报",
        filename: "knowledge-commercial-hub.png",
      },
    ];

    for (const item of captures) {
      await capturePage(page, {
        baseUrl: args.frontendUrl,
        route: item.route,
        waitText: item.waitText,
        filePath: path.join(outputDir, item.filename),
      });
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
