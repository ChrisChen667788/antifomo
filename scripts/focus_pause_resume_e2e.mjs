#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const DEFAULT_FRONTEND_URL = "http://127.0.0.1:3000";
const DEFAULT_BACKEND_URL = "http://127.0.0.1:8011";
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

function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    backendUrl: DEFAULT_BACKEND_URL,
    chromePath: process.env.CHROME_PATH || process.env.PUPPETEER_EXECUTABLE_PATH || "",
    headless: true,
    artifactDir: "",
    reportFile: "",
    startBackend: true,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--frontend-url" && next) {
      args.frontendUrl = next;
      i += 1;
      continue;
    }
    if (token === "--backend-url" && next) {
      args.backendUrl = next;
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
      continue;
    }
    if (token === "--artifact-dir" && next) {
      args.artifactDir = next;
      i += 1;
      continue;
    }
    if (token === "--report-file" && next) {
      args.reportFile = next;
      i += 1;
      continue;
    }
    if (token === "--reuse-backend") {
      args.startBackend = false;
      continue;
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

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function writeReport(reportFile, payload) {
  if (!reportFile) {
    return;
  }
  const targetPath = path.resolve(reportFile);
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function writeTextArtifact(artifactDir, filename, content) {
  if (!artifactDir) {
    return null;
  }
  const targetDir = path.resolve(artifactDir);
  fs.mkdirSync(targetDir, { recursive: true });
  const targetPath = path.join(targetDir, filename);
  fs.writeFileSync(targetPath, content, "utf8");
  return targetPath;
}

function pushBounded(list, value, limit = 40) {
  list.push(value);
  if (list.length > limit) {
    list.shift();
  }
}

function parseClock(value) {
  const match = String(value || "").match(/^(\d{2}):(\d{2})$/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

async function apiCall(apiBase, route, { method = "GET", payload } = {}) {
  const response = await fetch(`${apiBase.replace(/\/+$/, "")}${route}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status} ${route}: ${text}`);
  }
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

async function waitForHealth(apiBase, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const result = await apiCall(apiBase, "/healthz");
      if (result?.status === "ok") {
        return;
      }
    } catch {
      // retry
    }
    await delay(500);
  }
  throw new Error(`Backend health check timed out: ${apiBase}`);
}

async function waitForLatestSession(apiBase, predicate, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const session = await apiCall(apiBase, "/api/sessions/latest");
      if (predicate(session)) {
        return session;
      }
    } catch {
      // retry until timeout
    }
    await delay(400);
  }
  throw new Error("Timed out waiting for latest session to match expected state");
}

function deriveRuntimeConfig(frontendUrl, backendUrl) {
  const backend = new URL(backendUrl);
  const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const backendDir = path.join(repoRoot, "backend");
  const tmpDir = path.join(repoRoot, ".tmp");
  const dbPath = path.join(tmpDir, "focus_pause_resume_e2e.db");
  return {
    repoRoot,
    backendDir,
    tmpDir,
    dbPath,
    backendHost: backend.hostname,
    backendPort: String(Number(backend.port || (backend.protocol === "https:" ? 443 : 80))),
    frontendUrl: frontendUrl.replace(/\/+$/, ""),
    backendUrl: backendUrl.replace(/\/+$/, ""),
  };
}

function startIsolatedBackend(config) {
  fs.mkdirSync(config.tmpDir, { recursive: true });
  try {
    fs.rmSync(config.dbPath, { force: true });
  } catch {
    // ignore
  }

  const child = spawn(
    path.join(config.backendDir, ".venv311", "bin", "uvicorn"),
    ["app.main:app", "--host", config.backendHost, "--port", config.backendPort],
    {
      cwd: config.backendDir,
      env: {
        ...process.env,
        DATABASE_URL: `sqlite:///${config.dbPath}`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  let output = "";
  child.stdout.on("data", (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    output += chunk.toString();
  });

  return { child, getOutput: () => output };
}

async function getSnapshot(page) {
  return page.evaluate(() => {
    const buttonTexts = [...document.querySelectorAll("button")].map((node) => node.textContent?.trim() || "");
    const chipTexts = [...document.querySelectorAll("span")].map((node) => node.textContent?.trim() || "").filter(Boolean);
    const countdown = [...document.querySelectorAll("p")]
      .map((node) => node.textContent?.trim() || "")
      .find((text) => /^\d{2}:\d{2}$/.test(text)) || null;
    return {
      buttonTexts,
      chipTexts,
      countdown,
      bodyText: document.body.innerText,
    };
  });
}

async function waitForButtonText(page, labels, timeout = 15000) {
  try {
    await page.waitForFunction(
      (candidateLabels) =>
        [...document.querySelectorAll("button")].some((node) => candidateLabels.includes(node.textContent?.trim() || "")),
      { timeout },
      labels,
    );
  } catch (error) {
    const snapshot = await getSnapshot(page);
    throw new Error(
      `Timed out waiting for button: ${labels.join(", ")}. Buttons: ${snapshot.buttonTexts.join(" | ")}. Body preview: ${snapshot.bodyText.slice(0, 200)}`,
      { cause: error },
    );
  }
}

async function capturePageArtifacts(page, artifactDir, prefix, { fullPage = true } = {}) {
  if (!page || !artifactDir) {
    return {};
  }
  const targetDir = path.resolve(artifactDir);
  fs.mkdirSync(targetDir, { recursive: true });
  const screenshotPath = path.join(targetDir, `${prefix}.png`);
  const htmlPath = path.join(targetDir, `${prefix}.html`);
  const snapshotPath = path.join(targetDir, `${prefix}.snapshot.json`);
  const artifactPaths = {};

  try {
    await page.screenshot({ path: screenshotPath, fullPage });
    artifactPaths.screenshot = screenshotPath;
  } catch {
    // ignore artifact capture failures
  }
  try {
    fs.writeFileSync(htmlPath, await page.content(), "utf8");
    artifactPaths.html = htmlPath;
  } catch {
    // ignore artifact capture failures
  }
  try {
    fs.writeFileSync(snapshotPath, `${JSON.stringify(await getSnapshot(page), null, 2)}\n`, "utf8");
    artifactPaths.snapshot = snapshotPath;
  } catch {
    // ignore artifact capture failures
  }

  return artifactPaths;
}

async function clickButtonByText(page, labels) {
  const clicked = await page.evaluate((candidateLabels) => {
    const button = [...document.querySelectorAll("button")].find((node) => candidateLabels.includes(node.textContent?.trim() || ""));
    if (!button) {
      return false;
    }
    button.click();
    return true;
  }, labels);
  if (!clicked) {
    throw new Error(`Button not found: ${labels.join(", ")}`);
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const config = deriveRuntimeConfig(args.frontendUrl, args.backendUrl);
  const report = {
    status: "running",
    frontendUrl: config.frontendUrl,
    backendUrl: config.backendUrl,
    startBackend: args.startBackend,
    artifactDir: args.artifactDir || null,
    reportFile: args.reportFile || null,
  };
  let chromePath = "";

  let backendRuntime = null;
  let browser = null;
  let page = null;
  let currentStage = "bootstrap";
  const consoleMessages = [];
  const pageErrors = [];
  const requestFailures = [];
  const pageArtifacts = {};

  try {
    chromePath = resolveChromePath(args.chromePath);
    report.chromePath = chromePath;

    if (args.startBackend) {
      currentStage = "start_backend";
      backendRuntime = startIsolatedBackend(config);
      try {
        await waitForHealth(config.backendUrl);
      } catch (error) {
        backendRuntime.child.kill("SIGINT");
        throw new Error(`${String(error)}\n${backendRuntime.getOutput()}`);
      }
    }

    browser = await puppeteer.launch({
      executablePath: chromePath,
      headless: args.headless ? "new" : false,
      args: ["--no-sandbox"],
    });

    page = await browser.newPage();
    page.on("console", (message) => {
      pushBounded(consoleMessages, {
        type: message.type(),
        text: message.text(),
      });
    });
    page.on("pageerror", (error) => {
      pushBounded(pageErrors, {
        message: error.message,
        stack: error.stack || null,
      });
    });
    page.on("requestfailed", (request) => {
      pushBounded(requestFailures, {
        url: request.url(),
        method: request.method(),
        failureText: request.failure()?.errorText || "unknown",
      });
    });
    currentStage = "open_frontend";
    await page.goto(config.frontendUrl, { waitUntil: "domcontentloaded", timeout: 15000 });
    await page.evaluate((apiBaseOverride, overrideKey) => {
      window.localStorage.setItem("anti_fomo_feed_mode", "normal");
      window.localStorage.removeItem("anti_fomo_session_id");
      window.localStorage.removeItem("anti_fomo_session_goal");
      window.localStorage.removeItem("anti_fomo_focus_wechat_agent_owned");
      window.localStorage.setItem(overrideKey, apiBaseOverride);
      window.sessionStorage.clear();
    }, config.backendUrl, API_BASE_OVERRIDE_KEY);

    currentStage = "open_focus";
    await page.goto(`${config.frontendUrl}/focus`, { waitUntil: "domcontentloaded", timeout: 15000 });
    await waitForButtonText(page, ["开始", "Start"]);
    await delay(1200);
    pageArtifacts.ready = await capturePageArtifacts(page, args.artifactDir, "focus-ready");

    currentStage = "start_focus";
    const before = await getSnapshot(page);
    await clickButtonByText(page, ["开始", "Start"]);
    await waitForButtonText(page, ["暂停", "Pause"]);
    await delay(1500);
    const running = await getSnapshot(page);
    const runningSession = await waitForLatestSession(config.backendUrl, (session) => session.status === "running");

    currentStage = "pause_focus";
    await clickButtonByText(page, ["暂停", "Pause"]);
    await waitForButtonText(page, ["继续", "Resume"]);
    const paused = await getSnapshot(page);
    pageArtifacts.paused = await capturePageArtifacts(page, args.artifactDir, "focus-paused");
    const pausedSession = await waitForLatestSession(config.backendUrl, (session) => session.status === "paused");
    await delay(1500);
    const pausedLater = await getSnapshot(page);

    currentStage = "resume_focus";
    await clickButtonByText(page, ["继续", "Resume"]);
    await waitForButtonText(page, ["暂停", "Pause"]);
    await delay(1500);
    const resumed = await getSnapshot(page);
    pageArtifacts.resumed = await capturePageArtifacts(page, args.artifactDir, "focus-resumed");
    const resumedSession = await waitForLatestSession(config.backendUrl, (session) => session.status === "running");

    currentStage = "finish_focus";
    const sessionId = String(resumedSession.id);
    const finished = await apiCall(config.backendUrl, `/api/sessions/${sessionId}/finish`, {
      method: "POST",
      payload: { output_language: "zh-CN" },
    });

    const assertions = {
      countdownStartsImmediately:
        parseClock(before.countdown) !== null &&
        parseClock(running.countdown) !== null &&
        parseClock(running.countdown) < parseClock(before.countdown),
      backendSessionRunningAfterStart: runningSession.status === "running",
      pausedShowsResume: paused.buttonTexts.some((text) => ["继续", "Resume"].includes(text)),
      backendSessionPausedAfterPause: pausedSession.status === "paused",
      pausedKeepsSameCountdown: paused.countdown === pausedLater.countdown,
      pausedDetailUpdated: /后端 session 与页面倒计时都已暂停|backend session and the page countdown are paused/i.test(paused.bodyText),
      resumedReturnsPauseButton: resumed.buttonTexts.some((text) => ["暂停", "Pause"].includes(text)),
      backendSessionRunningAfterResume: resumedSession.status === "running",
      resumedContinuesFromRemaining:
        parseClock(paused.countdown) !== null &&
        parseClock(resumed.countdown) !== null &&
        parseClock(resumed.countdown) < parseClock(paused.countdown),
      finishGeneratesSummary: Boolean(String(finished.session?.summary_text || "").trim()),
    };

    const failedAssertions = Object.entries(assertions).filter(([, value]) => !value);
    Object.assign(report, {
      status: failedAssertions.length > 0 ? "failed" : "passed",
      currentStage,
      assertions,
      failedAssertions: failedAssertions.map(([key]) => key),
      countdowns: {
        before: before.countdown,
        running: running.countdown,
        paused: paused.countdown,
        pausedLater: pausedLater.countdown,
        resumed: resumed.countdown,
      },
      sessionStatus: {
        running: {
          status: runningSession.status,
          remaining_seconds: runningSession.remaining_seconds,
        },
        paused: {
          status: pausedSession.status,
          remaining_seconds: pausedSession.remaining_seconds,
        },
        resumed: {
          status: resumedSession.status,
          remaining_seconds: resumedSession.remaining_seconds,
        },
        finished: {
          status: finished.session?.status,
          remaining_seconds: finished.session?.remaining_seconds,
        },
      },
      diagnostics: {
        consoleMessages,
        pageErrors,
        requestFailures,
      },
      artifacts: pageArtifacts,
    });
    if (backendRuntime?.getOutput().trim()) {
      report.backendLogFile = writeTextArtifact(args.artifactDir, "isolated-backend.log", backendRuntime.getOutput());
    }
    writeReport(args.reportFile, report);
    console.log(JSON.stringify(report, null, 2));

    if (failedAssertions.length > 0) {
      throw new Error(`Focus E2E failed: ${failedAssertions.map(([key]) => key).join(", ")}`);
    }
  } catch (error) {
    report.status = "failed";
    report.currentStage = currentStage;
    report.error = {
      message: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack || null : null,
    };
    if (chromePath) {
      report.chromePath = chromePath;
    }
    report.diagnostics = {
      consoleMessages,
      pageErrors,
      requestFailures,
    };
    if (backendRuntime) {
      report.backendOutput = backendRuntime.getOutput();
      report.backendLogFile = writeTextArtifact(args.artifactDir, "isolated-backend.log", backendRuntime.getOutput());
    }
    if (page) {
      pageArtifacts.failureSummary = await capturePageArtifacts(page, args.artifactDir, "focus-failure-summary", { fullPage: false });
      pageArtifacts.failureDetail = await capturePageArtifacts(page, args.artifactDir, "focus-failure-detail");
    }
    report.artifacts = pageArtifacts;
    writeReport(args.reportFile, report);
    throw error;
  } finally {
    if (browser) {
      await browser.close();
    }
    if (backendRuntime) {
      backendRuntime.child.kill("SIGINT");
      await new Promise((resolve) => {
        backendRuntime.child.once("exit", resolve);
        setTimeout(resolve, 3000);
      });
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
