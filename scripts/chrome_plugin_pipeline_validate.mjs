#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import puppeteer from "puppeteer-core";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_URL_FILE = ".tmp/wechat_urls_17_wechat_only.txt";
const DEFAULT_REPORT = ".tmp/chrome_plugin_pipeline_remaining16.md";
const DEFAULT_EXCLUDE = "https://mp.weixin.qq.com/s/KA-D3o_8Eil7jdkmIjW8XA";
const DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function parseArgs(argv) {
  const args = {
    apiBase: DEFAULT_API_BASE,
    file: DEFAULT_URL_FILE,
    report: DEFAULT_REPORT,
    excludeUrl: DEFAULT_EXCLUDE,
    timeoutSec: 240,
    pollIntervalMs: 1500,
    headless: true,
    chromePath: DEFAULT_CHROME_PATH,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--api-base" && next) {
      args.apiBase = next;
      i += 1;
      continue;
    }
    if (token === "--file" && next) {
      args.file = next;
      i += 1;
      continue;
    }
    if (token === "--report" && next) {
      args.report = next;
      i += 1;
      continue;
    }
    if (token === "--exclude-url" && next) {
      args.excludeUrl = next;
      i += 1;
      continue;
    }
    if (token === "--timeout-sec" && next) {
      args.timeoutSec = Number(next) || args.timeoutSec;
      i += 1;
      continue;
    }
    if (token === "--poll-ms" && next) {
      args.pollIntervalMs = Number(next) || args.pollIntervalMs;
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
  }
  return args;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function loadUrls(filePath) {
  const absPath = path.resolve(filePath);
  const content = fs.readFileSync(absPath, "utf-8");
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

async function apiCall(apiBase, route, { method = "GET", payload } = {}) {
  const response = await fetch(`${apiBase.replace(/\/+$/, "")}${route}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status} ${route}: ${body}`);
  }
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

async function extractFromPage(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  await sleep(1800);

  return page.evaluate(() => {
    const normalize = (value) => String(value || "").replace(/\s+/g, " ").trim();
    const pickMeta = (...keys) => {
      for (const key of keys) {
        const node =
          document.querySelector(`meta[name="${key}"]`) ||
          document.querySelector(`meta[property="${key}"]`);
        const value = normalize(node?.getAttribute("content"));
        if (value) return value;
      }
      return "";
    };

    const nodeText = (node) => {
      if (!node) return "";
      const cloned = node.cloneNode(true);
      cloned.querySelectorAll("script,style,noscript,iframe").forEach((child) => child.remove());
      return normalize(cloned.innerText || cloned.textContent || "");
    };

    const isWeChat = location.hostname.includes("mp.weixin.qq.com");
    const wxTitle = normalize(
      document.querySelector("#activity-name")?.textContent ||
        document.querySelector(".rich_media_title")?.textContent,
    );
    const wxAuthor = normalize(
      document.querySelector("#js_name")?.textContent ||
        document.querySelector(".rich_media_meta_nickname a")?.textContent,
    );
    const wxPublishTime = normalize(
      document.querySelector("#publish_time")?.textContent ||
        document.querySelector(".rich_media_meta.rich_media_meta_text")?.textContent,
    );

    const title = normalize(wxTitle || pickMeta("og:title", "twitter:title") || document.title || "");
    const keywords = normalize(pickMeta("keywords"));
    const description = normalize(
      pickMeta("og:description", "description", "twitter:description"),
    );

    const candidates = [];
    if (isWeChat) {
      const wechatMain = nodeText(document.querySelector("#js_content"));
      if (wechatMain.length >= 80) {
        candidates.push(wechatMain);
      }
    }

    const selectors = [
      "article",
      "main",
      '[role="main"]',
      ".article-content, .post-content, #content, .entry-content",
    ];
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach((node) => {
        const text = nodeText(node);
        if (text.length >= 80) {
          candidates.push(text);
        }
      });
    }

    if (candidates.length === 0) {
      const bodyText = nodeText(document.body);
      if (bodyText.length >= 40) candidates.push(bodyText);
    }

    candidates.sort((a, b) => b.length - a.length);
    const body = (candidates[0] || "").slice(0, 18000);

    const lines = [];
    if (title) lines.push(`标题：${title}`);
    if (wxAuthor) lines.push(`作者：${wxAuthor}`);
    if (wxPublishTime) lines.push(`发布时间：${wxPublishTime}`);
    if (keywords) lines.push(`关键词：${keywords}`);
    if (description) lines.push(`摘要线索：${description}`);
    if (body) lines.push(`正文：${body}`);

    return {
      page_url: location.href,
      title,
      raw_content: lines.join("\n"),
      has_body: body.length >= 120,
      content_length: body.length,
      source_domain: location.hostname || "",
      is_wechat: isWeChat,
    };
  });
}

async function waitItems(apiBase, itemIds, timeoutSec, pollIntervalMs) {
  const pending = new Set(itemIds);
  const details = new Map();
  const deadline = Date.now() + timeoutSec * 1000;

  while (pending.size > 0 && Date.now() < deadline) {
    for (const itemId of Array.from(pending)) {
      const item = await apiCall(apiBase, `/api/items/${itemId}`);
      details.set(itemId, item);
      if (item.status === "ready" || item.status === "failed") {
        pending.delete(itemId);
      }
    }
    if (pending.size > 0) {
      await sleep(pollIntervalMs);
    }
  }
  return details;
}

function mdEscape(text) {
  return String(text || "").replace(/\|/g, "%7C").replace(/\n/g, " ");
}

function renderReport(reportPath, context) {
  const lines = [
    "# Chrome 插件路径验证报告（剩余16条）",
    "",
    `- API: \`${context.apiBase}\``,
    `- URL 文件: \`${context.filePath}\``,
    `- 本次验证数: **${context.rows.length}**`,
    `- ready: **${context.readyCount}**`,
    `- failed: **${context.failedCount}**`,
    `- 浏览器正文提取成功: **${context.browserBodyCount}**`,
    "",
    "| token | browser_body | item_status | title | tags | short_summary | action |",
    "|---|---:|---|---|---|---|---|",
  ];

  for (const row of context.rows) {
    lines.push(
      `| ${row.token} | ${row.browserBody ? "yes" : "no"} | ${row.status} | ${mdEscape(row.title)} | ` +
        `${mdEscape(row.tags.join(","))} | ${mdEscape(row.shortSummary)} | ${mdEscape(row.action)} |`,
    );
  }

  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, `${lines.join("\n")}\n`, "utf-8");
}

async function main() {
  const args = parseArgs(process.argv);
  const apiBase = args.apiBase.replace(/\/+$/, "");
  const urls = loadUrls(args.file).filter((url) => url !== args.excludeUrl);
  if (urls.length === 0) {
    throw new Error("No target URLs found after exclude filter.");
  }
  if (!fs.existsSync(args.chromePath)) {
    throw new Error(`Chrome executable not found: ${args.chromePath}`);
  }

  const health = await apiCall(apiBase, "/healthz");
  if (health.status !== "ok") {
    throw new Error("API health check failed.");
  }

  const browser = await puppeteer.launch({
    executablePath: args.chromePath,
    headless: args.headless,
    defaultViewport: { width: 1440, height: 900 },
    args: [
      "--no-first-run",
      "--disable-blink-features=AutomationControlled",
      "--disable-dev-shm-usage",
    ],
  });

  const created = [];
  let browserBodyCount = 0;
  try {
    for (const url of urls) {
      const page = await browser.newPage();
      const extracted = await extractFromPage(page, url);
      await page.close();

      const finalTitle = normalizeText(extracted.title) || null;
      const finalRaw = extracted.raw_content ? normalizeText(extracted.raw_content) : null;
      if (extracted.has_body) {
        browserBodyCount += 1;
      }

      const payload = {
        source_type: "plugin",
        source_url: url,
        title: finalTitle,
        raw_content: finalRaw,
      };
      const item = await apiCall(apiBase, "/api/items", { method: "POST", payload });
      created.push({
        url,
        token: url.split("/").pop() || url,
        itemId: item.id,
        browserBody: Boolean(extracted.has_body),
      });
      process.stdout.write(
        `[submit] ${url} | browser_body=${extracted.has_body ? "yes" : "no"} | item=${item.id}\n`,
      );
    }
  } finally {
    await browser.close();
  }

  const details = await waitItems(
    apiBase,
    created.map((row) => row.itemId),
    args.timeoutSec,
    args.pollIntervalMs,
  );

  const rows = created.map((row) => {
    const item = details.get(row.itemId) || {};
    return {
      token: row.token,
      browserBody: row.browserBody,
      status: item.status || "unknown",
      title: item.title || "",
      tags: Array.isArray(item.tags) ? item.tags.map((tag) => tag.tag_name || "") : [],
      shortSummary: (item.short_summary || "").slice(0, 140),
      action: item.action_suggestion || "",
    };
  });

  const readyCount = rows.filter((row) => row.status === "ready").length;
  const failedCount = rows.filter((row) => row.status === "failed").length;

  const reportPath = path.resolve(args.report);
  renderReport(reportPath, {
    apiBase,
    filePath: path.resolve(args.file),
    rows,
    readyCount,
    failedCount,
    browserBodyCount,
  });

  process.stdout.write(
    `[done] validated=${rows.length} ready=${readyCount} failed=${failedCount} browser_body=${browserBodyCount}\n`,
  );
  process.stdout.write(`[report] ${reportPath}\n`);
}

main().catch((err) => {
  process.stderr.write(`[error] ${err?.message || err}\n`);
  process.exit(1);
});
