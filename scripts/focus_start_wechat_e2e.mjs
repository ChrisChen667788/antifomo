#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3010";
const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";
const DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const API_BASE_OVERRIDE_KEY = "anti_fomo_api_base_override";
const FOCUS_WECHAT_BATCH_OVERRIDE_KEY = "anti_fomo_focus_wechat_batch_override";

function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    backendUrl: DEFAULT_BACKEND_URL,
    chromePath: process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH || "",
    totalItems: 1,
    segmentItems: 1,
    startBatchIndex: 0,
    runOnceMaxItems: 1,
    timeoutSec: 240,
    artifactDir: ".tmp/focus-start-wechat-e2e",
    reportFile: ".tmp/focus_start_wechat_e2e_report.json",
    headless: true,
    allowSeenOnly: true,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--frontend-url" && next) {
      args.frontendUrl = next;
      i += 1;
    } else if (token === "--backend-url" && next) {
      args.backendUrl = next;
      i += 1;
    } else if (token === "--chrome-path" && next) {
      args.chromePath = next;
      i += 1;
    } else if (token === "--total-items" && next) {
      args.totalItems = Number(next);
      i += 1;
    } else if (token === "--segment-items" && next) {
      args.segmentItems = Number(next);
      i += 1;
    } else if (token === "--start-batch-index" && next) {
      args.startBatchIndex = Number(next);
      i += 1;
    } else if (token === "--run-once-max-items" && next) {
      args.runOnceMaxItems = Number(next);
      i += 1;
    } else if (token === "--timeout-sec" && next) {
      args.timeoutSec = Number(next);
      i += 1;
    } else if (token === "--artifact-dir" && next) {
      args.artifactDir = next;
      i += 1;
    } else if (token === "--report-file" && next) {
      args.reportFile = next;
      i += 1;
    } else if (token === "--headful") {
      args.headless = false;
    } else if (token === "--strict-url") {
      args.allowSeenOnly = false;
    } else if (token === "--allow-seen-only") {
      args.allowSeenOnly = true;
    }
  }

  args.totalItems = clampInt(args.totalItems, 1, 60, 1);
  args.segmentItems = clampInt(args.segmentItems, 1, args.totalItems, 1);
  args.startBatchIndex = clampInt(args.startBatchIndex, 0, 5000, 0);
  args.runOnceMaxItems = clampInt(args.runOnceMaxItems, 1, 60, 1);
  args.timeoutSec = clampInt(args.timeoutSec, 30, 1800, 240);
  return args;
}

function clampInt(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
}

function resolveChromePath(requestedPath) {
  const candidates = [
    requestedPath,
    process.env.CHROME_PATH,
    process.env.PUPPETEER_EXECUTABLE_PATH,
    DEFAULT_CHROME_PATH,
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  for (const command of ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "chrome"]) {
    const result = spawnSync("which", [command], { encoding: "utf8" });
    const executablePath = result.status === 0 ? result.stdout.trim() : "";
    if (executablePath && fs.existsSync(executablePath)) {
      return executablePath;
    }
  }
  throw new Error("Chrome executable not found; pass --chrome-path or set CHROME_PATH.");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiCall(backendUrl, route, { method = "GET", payload } = {}) {
  const response = await fetch(`${backendUrl.replace(/\/+$/, "")}${route}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`API ${response.status} ${route}: ${text}`);
  }
  return text ? JSON.parse(text) : {};
}

async function waitForHealth(backendUrl, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const result = await apiCall(backendUrl, "/healthz");
      if (result?.status === "ok") return;
    } catch {
      // retry
    }
    await delay(500);
  }
  throw new Error(`Backend health check timed out: ${backendUrl}/healthz`);
}

async function waitForBodyText(page, pattern, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const text = await page.evaluate(() => document.body.innerText);
    if (pattern.test(text)) {
      return text;
    }
    await delay(500);
  }
  throw new Error(`Timed out waiting for page text: ${pattern}`);
}

async function clickButtonByText(page, labels) {
  const clicked = await page.evaluate((buttonLabels) => {
    const normalized = buttonLabels.map((label) => String(label).trim());
    const buttons = Array.from(document.querySelectorAll("button"));
    const button = buttons.find((candidate) => {
      const text = String(candidate.textContent || "").trim();
      return normalized.some((label) => text === label || text.includes(label));
    });
    if (!button) return false;
    button.click();
    return true;
  }, labels);
  if (!clicked) {
    throw new Error(`Button not found: ${labels.join(", ")}`);
  }
}

async function setGoal(page, value) {
  const inputHandles = await page.$$("input");
  for (const input of inputHandles) {
    const placeholder = await input.evaluate((element) => String(element.getAttribute("placeholder") || ""));
    if (!placeholder.includes("深度文章") && !placeholder.includes("要点")) {
      continue;
    }
    await input.click({ clickCount: 3 });
    await input.type(value);
    return true;
  }
  return false;
}

async function getPageSnapshot(page) {
  return page.evaluate(() => {
    const bodyText = document.body.innerText;
    const buttons = Array.from(document.querySelectorAll("button")).map((button) =>
      String(button.textContent || "").trim(),
    );
    const countdown = bodyText.match(/\b\d{2}:\d{2}\b/)?.[0] || null;
    return { bodyText, buttons, countdown };
  });
}

async function waitForNewBatch(backendUrl, startedAfterMs, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() < deadline) {
    latest = await apiCall(backendUrl, "/api/collector/wechat-agent/batch-status");
    const startedAt = Date.parse(`${String(latest.started_at || "").replace(/Z?$/, "Z")}`);
    if (Number.isFinite(startedAt) && startedAt >= startedAfterMs - 2000) {
      return latest;
    }
    await delay(1000);
  }
  throw new Error(`Timed out waiting for Focus-started batch. Latest: ${JSON.stringify(latest)}`);
}

async function waitForBatchFinished(backendUrl, startedAtValue, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() < deadline) {
    latest = await apiCall(backendUrl, "/api/collector/wechat-agent/batch-status");
    const sameBatch = !startedAtValue || latest.started_at === startedAtValue;
    if (sameBatch && latest.started_at && !latest.running) {
      return latest;
    }
    await delay(2000);
  }
  throw new Error(`Timed out waiting for batch completion. Latest: ${JSON.stringify(latest)}`);
}

async function fetchNewItems(backendUrl, ids) {
  const items = [];
  for (const id of ids || []) {
    try {
      const item = await apiCall(backendUrl, `/api/items/${id}`);
      items.push({
        id: item.id,
        title: item.title,
        source_type: item.source_type,
        source_url: item.source_url,
        source_domain: item.source_domain,
        status: item.status,
        ingest_route: item.ingest_route,
        content_length: String(item.clean_content || item.raw_content || "").length,
      });
    } catch (error) {
      items.push({ id, error: String(error) });
    }
  }
  return items;
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

async function main() {
  const args = parseArgs(process.argv);
  const chromePath = resolveChromePath(args.chromePath);
  const report = {
    status: "running",
    frontendUrl: args.frontendUrl,
    backendUrl: args.backendUrl,
    totalItems: args.totalItems,
    segmentItems: args.segmentItems,
    startBatchIndex: args.startBatchIndex,
    runOnceMaxItems: args.runOnceMaxItems,
    allowSeenOnly: args.allowSeenOnly,
    chromePath,
    artifacts: {},
  };

  let browser = null;
  try {
    await waitForHealth(args.backendUrl);
    const statusBefore = await apiCall(args.backendUrl, "/api/collector/wechat-agent/status").catch(() => null);
    if (statusBefore?.running) {
      await apiCall(args.backendUrl, "/api/collector/wechat-agent/stop", { method: "POST", payload: {} }).catch(() => null);
      await delay(1500);
    }

    browser = await puppeteer.launch({
      executablePath: chromePath,
      headless: args.headless ? "new" : false,
      args: ["--no-sandbox"],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 1600, deviceScaleFactor: 1 });
    const batchOverride = {
      totalItems: args.totalItems,
      segmentItems: args.segmentItems,
      startBatchIndex: args.startBatchIndex,
      runOnceMaxItems: args.runOnceMaxItems,
      maxCollectPerCycle: Math.max(args.totalItems, 1),
    };
    await page.evaluateOnNewDocument((backendUrl, overrideKey, batchKey, overridePayload) => {
      window.localStorage.setItem(overrideKey, backendUrl);
      window.localStorage.setItem(batchKey, JSON.stringify(overridePayload));
      window.localStorage.setItem(
        "anti_fomo_app_preferences_v1",
        JSON.stringify({ themeMode: "system", fontFamily: "system", textSize: "md", language: "zh-CN" }),
      );
      window.localStorage.setItem("anti_fomo_feed_mode", "normal");
      window.localStorage.removeItem("anti_fomo_session_id");
      window.localStorage.removeItem("anti_fomo_session_goal");
      window.localStorage.removeItem("anti_fomo_focus_wechat_agent_owned");
      window.sessionStorage.clear();
    }, args.backendUrl, API_BASE_OVERRIDE_KEY, FOCUS_WECHAT_BATCH_OVERRIDE_KEY, batchOverride);

    const url = new URL("/focus", args.frontendUrl.replace(/\/+$/, "/"));
    url.searchParams.set("focusWechatTotalItems", String(args.totalItems));
    url.searchParams.set("focusWechatSegmentItems", String(args.segmentItems));
    url.searchParams.set("focusWechatStartBatchIndex", String(args.startBatchIndex));
    url.searchParams.set("focusWechatRunOnceMaxItems", String(args.runOnceMaxItems));
    url.searchParams.set("focusCollectorMaxPerCycle", String(batchOverride.maxCollectPerCycle));

    await page.goto(url.toString(), { waitUntil: "networkidle2", timeout: 30000 });
    await waitForBodyText(page, /专注模式|Focus/, 20000);
    await waitForBodyText(page, /测试批量|开始|Start/, 20000);
    await setGoal(page, `Focus E2E 微信小批量 ${args.totalItems} 条`);
    const readyScreenshot = path.join(args.artifactDir, "focus-start-ready.png");
    fs.mkdirSync(args.artifactDir, { recursive: true });
    await page.screenshot({ path: readyScreenshot, fullPage: true });
    report.artifacts.readyScreenshot = readyScreenshot;

    const beforeClickMs = Date.now();
    const beforeStart = await getPageSnapshot(page);
    await clickButtonByText(page, ["开始", "Start"]);
    await waitForBodyText(page, /暂停|Pause|倒计时已启动|专注进行中/, 30000);
    const afterStart = await getPageSnapshot(page);
    const startedBatch = await waitForNewBatch(args.backendUrl, beforeClickMs, 60000);
    const finalBatch = await waitForBatchFinished(args.backendUrl, startedBatch.started_at, args.timeoutSec * 1000);
    await apiCall(args.backendUrl, "/api/collector/wechat-agent/stop", { method: "POST", payload: {} }).catch(() => null);
    await delay(6500);
    const finalSnapshot = await getPageSnapshot(page);
    const finalScreenshot = path.join(args.artifactDir, "focus-start-final.png");
    await page.screenshot({ path: finalScreenshot, fullPage: true });
    report.artifacts.finalScreenshot = finalScreenshot;

    const newItems = await fetchNewItems(args.backendUrl, finalBatch.new_item_ids || []);
    await clickButtonByText(page, ["重置", "Reset"]).catch(async () => {
      const latestSession = await apiCall(args.backendUrl, "/api/sessions/latest").catch(() => null);
      if (latestSession?.id && latestSession.status !== "finished") {
        await apiCall(args.backendUrl, `/api/sessions/${latestSession.id}/finish`, {
          method: "POST",
          payload: { output_language: "zh-CN" },
        }).catch(() => null);
      }
    });

    const urlFirstTotal =
      Number(finalBatch.submitted_url || 0) + Number(finalBatch.deduplicated_existing_url || 0);
    const urlFirstTabTotal =
      Number(finalBatch.submitted_url_tab_copy_link || 0) +
      Number(finalBatch.submitted_url_tab_browser_open || 0) +
      Number(finalBatch.deduplicated_existing_url_tab_copy_link || 0) +
      Number(finalBatch.deduplicated_existing_url_tab_browser_open || 0);
    const seenOnlyCompleted =
      Number(finalBatch.skipped_seen || 0) >= args.totalItems &&
      Number(finalBatch.failed || 0) === 0 &&
      Number(finalBatch.submitted || 0) === 0;
    const collectionOutcomeAcceptable = urlFirstTotal > 0 || (args.allowSeenOnly && seenOnlyCompleted);
    const tabRouteOutcomeAcceptable = urlFirstTabTotal > 0 || (args.allowSeenOnly && seenOnlyCompleted);
    const assertions = {
      startButtonClicked: afterStart.buttons.some((text) => /暂停|Pause/.test(text)) || /倒计时已启动|专注进行中/.test(afterStart.bodyText),
      testOverrideVisible: /测试批量/.test(beforeStart.bodyText),
      batchUsesRequestedTotal: Number(finalBatch.total_items) === args.totalItems,
      batchUsesRequestedSegment: Number(finalBatch.segment_items) === args.segmentItems,
      batchFinished: finalBatch.running === false,
      noBatchFailure: Number(finalBatch.failed || 0) === 0,
      collectionOutcomeAcceptable,
      tabRouteOutcomeAcceptable,
    };
    const failedAssertions = Object.entries(assertions)
      .filter(([, value]) => !value)
      .map(([key]) => key);

    Object.assign(report, {
      status: failedAssertions.length ? "failed" : "passed",
      assertions,
      failedAssertions,
      routeEvidence: {
        urlFirstPathObserved: urlFirstTotal > 0,
        tabRouteObserved: urlFirstTabTotal > 0,
        seenOnlyCompleted,
      },
      countdowns: {
        before: beforeStart.countdown,
        afterStart: afterStart.countdown,
        final: finalSnapshot.countdown,
      },
      batch: finalBatch,
      newItems,
    });
  } catch (error) {
    Object.assign(report, {
      status: "error",
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : null,
    });
    process.exitCode = 1;
  } finally {
    if (browser) {
      await browser.close().catch(() => null);
    }
    await apiCall(args.backendUrl, "/api/collector/wechat-agent/stop", { method: "POST", payload: {} }).catch(() => null);
    if (report.status === "failed") {
      process.exitCode = 1;
    }
    writeJson(args.reportFile, report);
    console.log(JSON.stringify(report, null, 2));
  }
}

void main();
