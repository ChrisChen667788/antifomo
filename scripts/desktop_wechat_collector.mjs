#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import puppeteer from "puppeteer-core";

const execFileAsync = promisify(execFile);

const DEFAULTS = {
  apiBase: "http://127.0.0.1:8000",
  chromePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  sourceApiPath: "/api/collector/sources?enabled_only=true&limit=500",
  sourceFile: ".tmp/wechat_collector_sources.txt",
  configFile: ".tmp/wechat_collector_config.json",
  stateFile: ".tmp/wechat_collector_state.json",
  reportFile: ".tmp/wechat_collector_latest.md",
  outputLanguage: "zh-CN",
  intervalSec: 300,
  maxDiscoverPerSource: 30,
  maxCollectPerCycle: 50,
  flushPendingLimit: 80,
  dailySummaryHours: 24,
  dailySummaryLimit: 12,
  dailySummaryReport: ".tmp/collector_daily_summary.md",
  runPostCycle: true,
  submitMode: "browser-batch",
  batchSubmitSize: 10,
  wechatFavoritesAutoImport: true,
  wechatCliPath: process.env.WECHAT_CLI_BIN || "wechat-cli",
  wechatClipboardAutoImport: true,
  wechatClipboardPath: process.env.WECHAT_CLIPBOARD_BIN || "pbpaste",
  wechatExportDirectoryAutoImport: true,
  wechatExportDirectoryPath: process.env.WECHAT_FAVORITES_EXPORT_DIR || ".tmp/wechat_favorites_inbox",
  headless: true,
  loop: false,
};

function parseArgs(argv) {
  const args = { ...DEFAULTS };
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--api-base" && next) {
      args.apiBase = next;
      i += 1;
      continue;
    }
    if (token === "--chrome-path" && next) {
      args.chromePath = next;
      i += 1;
      continue;
    }
    if (token === "--source-file" && next) {
      args.sourceFile = next;
      i += 1;
      continue;
    }
    if (token === "--config-file" && next) {
      args.configFile = next;
      i += 1;
      continue;
    }
    if (token === "--source-api-path" && next) {
      args.sourceApiPath = next;
      i += 1;
      continue;
    }
    if (token === "--state-file" && next) {
      args.stateFile = next;
      i += 1;
      continue;
    }
    if (token === "--report-file" && next) {
      args.reportFile = next;
      i += 1;
      continue;
    }
    if (token === "--language" && next) {
      args.outputLanguage = next;
      i += 1;
      continue;
    }
    if (token === "--interval-sec" && next) {
      args.intervalSec = Number(next) || args.intervalSec;
      i += 1;
      continue;
    }
    if (token === "--max-discover" && next) {
      args.maxDiscoverPerSource = Number(next) || args.maxDiscoverPerSource;
      i += 1;
      continue;
    }
    if (token === "--max-collect" && next) {
      args.maxCollectPerCycle = Number(next) || args.maxCollectPerCycle;
      i += 1;
      continue;
    }
    if (token === "--flush-limit" && next) {
      args.flushPendingLimit = Number(next) || args.flushPendingLimit;
      i += 1;
      continue;
    }
    if (token === "--daily-hours" && next) {
      args.dailySummaryHours = Number(next) || args.dailySummaryHours;
      i += 1;
      continue;
    }
    if (token === "--daily-limit" && next) {
      args.dailySummaryLimit = Number(next) || args.dailySummaryLimit;
      i += 1;
      continue;
    }
    if (token === "--daily-report" && next) {
      args.dailySummaryReport = next;
      i += 1;
      continue;
    }
    if (token === "--submit-mode" && next) {
      args.submitMode = next;
      i += 1;
      continue;
    }
    if (token === "--batch-submit-size" && next) {
      args.batchSubmitSize = Number(next) || args.batchSubmitSize;
      i += 1;
      continue;
    }
    if (token === "--no-post-cycle") {
      args.runPostCycle = false;
      continue;
    }
    if (token === "--no-wechat-favorites-auto") {
      args.wechatFavoritesAutoImport = false;
      continue;
    }
    if (token === "--wechat-cli-path" && next) {
      args.wechatCliPath = next;
      i += 1;
      continue;
    }
    if (token === "--no-wechat-clipboard-auto") {
      args.wechatClipboardAutoImport = false;
      continue;
    }
    if (token === "--wechat-clipboard-path" && next) {
      args.wechatClipboardPath = next;
      i += 1;
      continue;
    }
    if (token === "--no-wechat-export-directory-auto") {
      args.wechatExportDirectoryAutoImport = false;
      continue;
    }
    if (token === "--wechat-export-directory" && next) {
      args.wechatExportDirectoryPath = next;
      i += 1;
      continue;
    }
    if (token === "--headful") {
      args.headless = false;
      continue;
    }
    if (token === "--loop") {
      args.loop = true;
      continue;
    }
  }
  args.apiBase = args.apiBase.replace(/\/+$/, "");
  return args;
}

function applyRuntimeConfig(args) {
  const nextArgs = { ...args };
  const configPath = path.resolve(nextArgs.configFile || DEFAULTS.configFile);
  if (!fs.existsSync(configPath)) {
    return nextArgs;
  }
  try {
    const config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
    if (typeof config.wechat_clipboard_auto_import === "boolean") {
      nextArgs.wechatClipboardAutoImport = config.wechat_clipboard_auto_import;
    }
    if (typeof config.wechat_export_directory_auto_import === "boolean") {
      nextArgs.wechatExportDirectoryAutoImport = config.wechat_export_directory_auto_import;
    }
    if (typeof config.wechat_export_directory_path === "string" && config.wechat_export_directory_path.trim()) {
      nextArgs.wechatExportDirectoryPath = config.wechat_export_directory_path.trim();
    }
  } catch (error) {
    console.warn(`[collector] runtime config ignored: ${error?.message || error}`);
  }
  return nextArgs;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureSourceFile(filePath) {
  const abs = path.resolve(filePath);
  if (fs.existsSync(abs)) return abs;
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(
    abs,
    [
      "# 每行一个源页面 URL（可写公众号聚合页、文章目录页，或直接文章 URL）",
      "# 直接文章示例:",
      "# https://mp.weixin.qq.com/s/xxxxxxxx",
      "",
    ].join("\n"),
    "utf-8",
  );
  return abs;
}

function loadSourceUrls(filePath) {
  const abs = ensureSourceFile(filePath);
  return fs
    .readFileSync(abs, "utf-8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

async function loadSourceUrlsFromApi(apiBase, sourceApiPath) {
  const route = sourceApiPath.startsWith("/") ? sourceApiPath : `/${sourceApiPath}`;
  const response = await apiCall(apiBase, route);
  const items = Array.isArray(response?.items) ? response.items : [];
  return Array.from(
    new Set(
      items
        .map((item) => sanitizeUrl(item?.source_url))
        .filter(Boolean),
    ),
  );
}

async function resolveSourceUrls(args) {
  const fileUrls = loadSourceUrls(args.sourceFile).map((url) => sanitizeUrl(url)).filter(Boolean);
  try {
    const apiUrls = await loadSourceUrlsFromApi(args.apiBase, args.sourceApiPath);
    if (apiUrls.length > 0) {
      const merged = Array.from(new Set([...apiUrls, ...fileUrls]));
      return {
        urls: merged,
        sourceMode: fileUrls.length > 0 ? "api+file" : "api",
      };
    }
  } catch (error) {
    console.warn(`[collector] source api unavailable: ${error?.message || error}`);
  }

  return { urls: fileUrls, sourceMode: "file" };
}

function loadState(stateFilePath) {
  const abs = path.resolve(stateFilePath);
  if (!fs.existsSync(abs)) {
    return { seen_links: {}, runs: [] };
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(abs, "utf-8"));
    if (parsed && typeof parsed === "object") return parsed;
  } catch {
    // ignore
  }
  return { seen_links: {}, runs: [] };
}

function saveState(stateFilePath, state) {
  const abs = path.resolve(stateFilePath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, JSON.stringify(state, null, 2), "utf-8");
}

async function apiCall(apiBase, route, { method = "GET", payload } = {}) {
  const response = await fetch(`${apiBase}${route}`, {
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

function sanitizeUrl(url) {
  const text = String(url || "").trim();
  if (!text) return "";
  if (!/^https?:\/\//i.test(text)) return "";
  try {
    const parsed = new URL(text);
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "";
  }
}

function isDirectArticleUrl(url) {
  return /mp\.weixin\.qq\.com\/s(\/|\?)/i.test(url) || /mp\.weixin\.qq\.com\/mp\/appmsg/i.test(url);
}

function sourceToken(url) {
  try {
    const parsed = new URL(url);
    const parts = parsed.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || parsed.hostname || url;
  } catch {
    return String(url || "").split("/").pop() || String(url || "-");
  }
}

function createSourceStats(sourceUrl) {
  return {
    source_url: sourceUrl,
    source_token: sourceToken(sourceUrl),
    scanned: false,
    discovered_count: 0,
    queued_count: 0,
    collected_count: 0,
    plugin_count: 0,
    url_count: 0,
    deduplicated_count: 0,
    skipped_seen_count: 0,
    failed_count: 0,
    discover_failed_count: 0,
    last_error: "",
  };
}

function getSourceStats(sourceStats, sourceUrl) {
  if (!sourceStats.has(sourceUrl)) {
    sourceStats.set(sourceUrl, createSourceStats(sourceUrl));
  }
  return sourceStats.get(sourceUrl);
}

function ratio(numerator, denominator) {
  if (!denominator || denominator <= 0) return 0;
  return Math.max(0, Math.min(1, Math.round((numerator / denominator) * 1000) / 1000));
}

function summarizeSourceHealth(stats) {
  const handledCount = stats.collected_count + stats.skipped_seen_count;
  const denominator = Math.max(stats.discovered_count, handledCount + stats.failed_count);
  const coverageRate = ratio(handledCount, denominator);
  const bodySuccessRate = ratio(stats.plugin_count, stats.collected_count);
  let healthState = "good";
  let recommendation = "最近一轮源页面处理稳定。";

  if (stats.discover_failed_count > 0) {
    healthState = "poor";
    recommendation = "源页面打开或解析失败，检查 URL 是否可访问、是否需要登录或页面结构是否变化。";
  } else if (!stats.scanned) {
    healthState = "watch";
    recommendation = "本轮因采集上限未扫描到该源；如需全覆盖，调高单轮采集上限或减少源列表。";
  } else if (stats.discovered_count <= 0) {
    healthState = "watch";
    recommendation = "最近一轮没有发现文章；如果预期有更新，检查源页面是否仍然暴露文章链接。";
  } else if (stats.failed_count > 0 && coverageRate < 0.8) {
    healthState = "poor";
    recommendation = "发现文章后未能稳定入库，检查浏览器登录态、正文抽取或后端入库错误。";
  } else if (coverageRate < 0.9) {
    healthState = "watch";
    recommendation = "还有部分文章未处理，建议观察失败明细或提高单轮采集上限。";
  } else if (stats.collected_count > 0 && bodySuccessRate < 0.5) {
    healthState = "watch";
    recommendation = "多数文章走链接兜底，建议检查 headless 浏览器正文抽取链路。";
  }

  return {
    ...stats,
    handled_count: handledCount,
    coverage_rate: coverageRate,
    body_success_rate: bodySuccessRate,
    health_state: healthState,
    recommendation,
  };
}

function buildSourceSummaries(sources, sourceStats) {
  return sources
    .map((sourceUrl) => summarizeSourceHealth(getSourceStats(sourceStats, sourceUrl)))
    .sort((a, b) => {
      const rank = { poor: 0, watch: 1, good: 2 };
      const stateRank = (rank[a.health_state] ?? 3) - (rank[b.health_state] ?? 3);
      if (stateRank !== 0) return stateRank;
      return b.failed_count - a.failed_count || b.discovered_count - a.discovered_count;
    });
}

async function discoverArticleLinks(page, sourceUrl, maxDiscover) {
  const direct = isDirectArticleUrl(sourceUrl);
  if (direct) return [sourceUrl];

  await page.goto(sourceUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  await sleep(1500);

  const links = await page.evaluate(() => {
    const output = [];
    const seen = new Set();
    const pushLink = (value) => {
      if (!value) return;
      try {
        const abs = new URL(value, location.href).toString();
        if (seen.has(abs)) return;
        if (!abs.includes("mp.weixin.qq.com")) return;
        if (!/\/s(\/|\?)/.test(abs) && !abs.includes("/mp/appmsg")) return;
        seen.add(abs);
        output.push(abs);
      } catch {
        // ignore invalid
      }
    };

    document.querySelectorAll("a[href]").forEach((node) => {
      pushLink(node.getAttribute("href"));
      pushLink(node.href);
    });
    document.querySelectorAll("[data-url], [data-link]").forEach((node) => {
      pushLink(node.getAttribute("data-url"));
      pushLink(node.getAttribute("data-link"));
    });
    return output;
  });

  const normalized = links
    .map((url) => sanitizeUrl(url))
    .filter(Boolean)
    .slice(0, maxDiscover);
  return Array.from(new Set(normalized));
}

async function extractFromArticle(page, articleUrl) {
  await page.goto(articleUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  try {
    await page.waitForFunction(
      () => {
        const articleText = String(
          document.querySelector("#js_content")?.innerText ||
            document.querySelector("#js_content")?.textContent ||
            "",
        ).replace(/\s+/g, " ").trim();
        const pageText = String(document.body?.innerText || document.body?.textContent || "")
          .replace(/\s+/g, " ")
          .trim()
          .toLowerCase();
        const blockedMarkers = [
          "参数错误",
          "parameter error",
          "环境异常",
          "完成验证后即可继续访问",
          "访问受限",
          "链接已失效",
          "requiring captcha",
        ];
        return articleText.length >= 80 || blockedMarkers.some((marker) => pageText.includes(marker));
      },
      { timeout: 8000 },
    );
  } catch {
    // The evaluator below decides whether the page is readable.
  }

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

    const title = normalize(
      document.querySelector("#activity-name")?.textContent ||
        document.querySelector(".rich_media_title")?.textContent ||
        pickMeta("og:title", "twitter:title") ||
        document.title,
    );
    const author = normalize(
      document.querySelector("#js_name")?.textContent ||
        document.querySelector(".rich_media_meta_nickname a")?.textContent,
    );
    const publishTime = normalize(
      document.querySelector("#publish_time")?.textContent ||
        document.querySelector(".rich_media_meta.rich_media_meta_text")?.textContent,
    );
    const keywords = normalize(pickMeta("keywords"));
    const description = normalize(pickMeta("og:description", "description", "twitter:description"));
    const canonicalUrl = normalize(
      document.querySelector('link[rel="canonical"]')?.getAttribute("href") ||
        pickMeta("og:url") ||
        location.href,
    );

    const contentCandidates = [];
    const jsContent = nodeText(document.querySelector("#js_content"));
    if (jsContent.length >= 80) contentCandidates.push(jsContent);

    ["article", "main", '[role="main"]', ".article-content, .post-content, #content, .entry-content"].forEach(
      (selector) => {
        document.querySelectorAll(selector).forEach((node) => {
          const text = nodeText(node);
          if (text.length >= 80) contentCandidates.push(text);
        });
      },
    );

    if (contentCandidates.length === 0) {
      const body = nodeText(document.body);
      if (body.length >= 40) contentCandidates.push(body);
    }
    contentCandidates.sort((a, b) => b.length - a.length);
    const body = (contentCandidates[0] || "").slice(0, 18000);
    const accessCheck = `${title} ${description} ${body}`.toLowerCase();
    const blockedMarkers = [
      "参数错误",
      "parameter error",
      "环境异常",
      "完成验证后即可继续访问",
      "访问受限",
      "链接已失效",
      "requiring captcha",
    ];
    const accessLimited =
      blockedMarkers.some((marker) => accessCheck.includes(marker)) ||
      (!document.querySelector("#js_content") &&
        (title === "微信公众平台" || title.toLowerCase().includes("weixin official accounts platform")));

    const lines = [];
    if (title) lines.push(`标题：${title}`);
    if (author) lines.push(`作者：${author}`);
    if (publishTime) lines.push(`发布时间：${publishTime}`);
    if (keywords) lines.push(`关键词：${keywords}`);
    if (description) lines.push(`摘要线索：${description}`);
    if (body) lines.push(`正文：${body}`);

    return {
      final_url: canonicalUrl || location.href,
      title,
      source_domain: location.hostname || "",
      raw_content: lines.join("\n"),
      has_body: !accessLimited && body.length >= 120,
      access_limited: accessLimited,
      content_length: body.length,
    };
  });
}

function renderRunReport(reportPath, summary) {
  const rows = summary.rows || [];
  const sourceSummaries = summary.sourceSummaries || [];
  const lines = [
    "# Desktop WeChat Collector 报告",
    "",
    `- time: ${new Date().toISOString()}`,
    `- source_mode: ${summary.sourceMode || "unknown"}`,
    `- submit_mode: ${summary.submitMode || "unknown"}`,
    `- source_count: ${summary.sourceCount}`,
    `- discovered_links: ${summary.discoveredCount}`,
    `- collected: ${summary.collectedCount}`,
    `- submitted_plugin: ${summary.pluginCount}`,
    `- submitted_url_fallback: ${summary.urlCount}`,
    `- submitted_ocr_fallback: ${summary.ocrCount}`,
    `- skipped_seen: ${summary.skippedSeenCount}`,
    `- failed: ${summary.failedCount}`,
    "",
    "## Source health",
    "",
    "| source | health | discovered | handled | collected | body | skipped | failed | recommendation |",
    "|---|---|---:|---:|---:|---:|---:|---:|---|",
  ];
  for (const source of sourceSummaries.slice(0, 30)) {
    lines.push(
      `| ${source.source_token} | ${source.health_state} | ${source.discovered_count} | ` +
        `${source.handled_count} | ${source.collected_count} | ${Math.round(source.body_success_rate * 100)}% | ` +
        `${source.skipped_seen_count} | ${source.failed_count} | ${source.recommendation} |`,
    );
  }
  lines.push(
    "",
    "## Article rows",
    "",
    "| source | article | mode | item_id | status | note |",
    "|---|---|---|---|---|---|",
  );
  for (const row of rows) {
    lines.push(
      `| ${row.sourceToken} | ${row.articleToken} | ${row.mode} | ${row.itemId || ""} | ${row.status} | ${row.note || ""} |`,
    );
  }
  const abs = path.resolve(reportPath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, `${lines.join("\n")}\n`, "utf-8");
}

function chunkItems(items, chunkSize) {
  const safeSize = Math.max(1, Number(chunkSize) || 1);
  const chunks = [];
  for (let index = 0; index < items.length; index += safeSize) {
    chunks.push(items.slice(index, index + safeSize));
  }
  return chunks;
}

function collectWechatArticleUrls(value, output = new Set()) {
  if (typeof value === "string") {
    const matches = value.match(/https?:\/\/[^\s<>"']+/gi) || [];
    for (const match of matches) {
      const normalized = sanitizeUrl(match.replace(/[),.;，。；）】》]+$/g, ""));
      if (normalized && /mp\.weixin\.qq\.com\/s(?:\/|\?)/i.test(normalized)) {
        output.add(normalized);
      }
    }
    return output;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectWechatArticleUrls(item, output));
    return output;
  }
  if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectWechatArticleUrls(item, output));
  }
  return output;
}

function parseWechatCliFavorites(stdout) {
  const text = String(stdout || "").trim();
  if (!text) return [];
  try {
    return Array.from(collectWechatArticleUrls(JSON.parse(text)));
  } catch {
    return Array.from(collectWechatArticleUrls(text));
  }
}

async function readClipboardArticleUrls(args) {
  const result = {
    available: false,
    urls: [],
    message: "",
  };
  if (!args.wechatClipboardAutoImport) {
    result.message = "clipboard auto import disabled";
    return result;
  }
  try {
    const clipboard = await execFileAsync(args.wechatClipboardPath, [], {
      timeout: 2500,
      maxBuffer: 2 * 1024 * 1024,
    });
    result.available = true;
    result.urls = Array.from(collectWechatArticleUrls(clipboard.stdout || ""));
    result.message = result.urls.length
      ? `clipboard contains ${result.urls.length} article link(s)`
      : "clipboard checked; no article links";
    return result;
  } catch (error) {
    const code = String(error?.code || "");
    result.message =
      code === "ENOENT"
        ? `${args.wechatClipboardPath} not installed or unavailable`
        : `clipboard read failed: ${error?.message || error}`;
    return result;
  }
}

function isSupportedWechatExportFile(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return [".html", ".htm", ".txt", ".md", ".url", ".webloc"].includes(ext);
}

function buildExportFileKey(filePath, stat) {
  return `${path.resolve(filePath)}|${Number(stat.mtimeMs || 0).toFixed(0)}|${stat.size}`;
}

function readWechatExportDirectory(args, state) {
  const result = {
    available: false,
    directory: path.resolve(args.wechatExportDirectoryPath || DEFAULTS.wechatExportDirectoryPath),
    files: [],
    discoveredCount: 0,
    message: "",
  };
  if (!args.wechatExportDirectoryAutoImport) {
    result.message = "export directory auto import disabled";
    return result;
  }

  try {
    fs.mkdirSync(result.directory, { recursive: true });
  } catch (error) {
    result.message = `export directory unavailable: ${error?.message || error}`;
    return result;
  }

  result.available = true;
  let entries = [];
  try {
    entries = fs.readdirSync(result.directory, { withFileTypes: true });
  } catch (error) {
    result.message = `export directory read failed: ${error?.message || error}`;
    return result;
  }

  const candidates = [];
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const filePath = path.join(result.directory, entry.name);
    if (!isSupportedWechatExportFile(filePath)) continue;
    let stat;
    try {
      stat = fs.statSync(filePath);
    } catch {
      continue;
    }
    if (stat.size <= 0 || stat.size > 5 * 1024 * 1024) continue;
    candidates.push({ filePath, stat });
  }
  candidates.sort((a, b) => Number(a.stat.mtimeMs || 0) - Number(b.stat.mtimeMs || 0));

  const seenFiles = state.seen_favorite_export_files || {};
  for (const candidate of candidates.slice(0, 30)) {
    const key = buildExportFileKey(candidate.filePath, candidate.stat);
    if (seenFiles[key]) continue;
    let text = "";
    try {
      text = fs.readFileSync(candidate.filePath, "utf-8");
    } catch {
      continue;
    }
    const urls = Array.from(collectWechatArticleUrls(text));
    result.discoveredCount += urls.length;
    result.files.push({
      key,
      path: candidate.filePath,
      name: path.basename(candidate.filePath),
      text,
      urls,
    });
  }

  result.message = result.files.length
    ? `export directory found ${result.files.length} new file(s)`
    : `export directory checked; no new files`;
  return result;
}

async function importWechatExportFiles(args, state, files) {
  const result = {
    processed: 0,
    imported: 0,
    deduplicated: 0,
    invalid: 0,
    skipped: 0,
    failed: 0,
    messages: [],
  };
  state.seen_favorite_export_files = state.seen_favorite_export_files || {};

  for (const file of files) {
    try {
      const response = await apiCall(args.apiBase, "/api/collector/wechat-favorites/import", {
        method: "POST",
        payload: {
          export_text: file.text,
          urls: [],
          output_language: args.outputLanguage,
          include_text_blocks: true,
          limit: 500,
          process_immediately: false,
        },
      });
      result.processed += 1;
      result.imported += Number(response?.created || 0);
      result.deduplicated += Number(response?.deduplicated || 0);
      result.invalid += Number(response?.invalid || 0);
      result.skipped += Number(response?.skipped || 0);
      state.seen_favorite_export_files[file.key] = {
        imported_at: new Date().toISOString(),
        file_name: file.name,
        url_count: file.urls.length,
      };
      result.messages.push(`${file.name}: created=${response?.created || 0} deduplicated=${response?.deduplicated || 0}`);
    } catch (error) {
      result.failed += 1;
      result.messages.push(`${file.name}: ${error?.message || error}`);
    }
  }
  return result;
}

async function runWechatFavoritesAutoImport(args) {
  const state = loadState(args.stateFile);
  state.seen_favorite_links = state.seen_favorite_links || {};
  state.seen_favorite_export_files = state.seen_favorite_export_files || {};
  const record = {
    ts: new Date().toISOString(),
    status: "idle",
    available: false,
    discovered_count: 0,
    imported_count: 0,
    deduplicated_count: 0,
    message: "",
    adapters: {},
  };

  if (!args.wechatFavoritesAutoImport) {
    record.status = "disabled";
    record.message = "WeChat Favorites auto import disabled";
    state.last_favorites_auto = record;
    saveState(args.stateFile, state);
    return record;
  }

  const exportDirectory = readWechatExportDirectory(args, state);
  const exportImport = await importWechatExportFiles(args, state, exportDirectory.files);
  record.adapters.export_directory = {
    available: exportDirectory.available,
    enabled: Boolean(args.wechatExportDirectoryAutoImport),
    path: exportDirectory.directory,
    discovered_count: exportDirectory.discoveredCount,
    processed_count: exportImport.processed,
    failed_count: exportImport.failed,
    message: exportImport.messages.length
      ? `${exportDirectory.message}; ${exportImport.messages.slice(0, 3).join("；")}`
      : exportDirectory.message,
  };
  record.imported_count += exportImport.imported;
  record.deduplicated_count += exportImport.deduplicated;
  record.discovered_count += exportDirectory.discoveredCount;

  let cliUrls = [];
  let cliAvailable = false;
  let cliMessage = "";
  try {
    const result = await execFileAsync(
      args.wechatCliPath,
      ["favorites", "--type", "article"],
      { timeout: 45_000, maxBuffer: 8 * 1024 * 1024 },
    );
    cliAvailable = true;
    cliUrls = parseWechatCliFavorites(result.stdout || "");
    cliMessage = cliUrls.length
      ? `wechat-cli returned ${cliUrls.length} article link(s)`
      : "wechat-cli checked; no article links";
  } catch (error) {
    const code = String(error?.code || "");
    cliMessage =
      code === "ENOENT"
        ? "wechat-cli not installed; automatic Favorites import is waiting for local read-only adapter setup"
        : `wechat-cli favorites failed: ${error?.message || error}`;
    console.warn(`[collector] ${cliMessage}`);
  }
  record.adapters.wechat_cli = {
    available: cliAvailable,
    discovered_count: cliUrls.length,
    message: cliMessage,
  };

  const clipboard = await readClipboardArticleUrls(args);
  record.adapters.clipboard = {
    available: clipboard.available,
    discovered_count: clipboard.urls.length,
    message: clipboard.message,
  };

  record.available = exportDirectory.available || cliAvailable || clipboard.available;
  const discovered = Array.from(new Set([...cliUrls, ...clipboard.urls]));
  const freshUrls = discovered.filter((url) => !state.seen_favorite_links[url]);
  record.discovered_count += discovered.length;
  if (!record.available) {
    record.status = "unavailable";
    record.message = [exportDirectory.message, cliMessage, clipboard.message].filter(Boolean).join("；");
    state.last_favorites_auto = record;
    saveState(args.stateFile, state);
    console.warn(`[collector] ${record.message}`);
    return record;
  }
  if (!freshUrls.length) {
    record.status = exportImport.processed > 0 ? "imported" : "idle";
    if (discovered.length) {
      record.message = "WeChat links checked; no new article links";
    } else {
      record.message =
        [exportDirectory.message, cliMessage, clipboard.message].filter(Boolean).join("；") ||
        "WeChat links checked; no article links found";
    }
    if (exportImport.processed > 0) {
      record.message =
        `WeChat export files processed=${exportImport.processed} created=${exportImport.imported} ` +
        `deduplicated=${exportImport.deduplicated}；${record.message}`;
    }
    state.last_favorites_auto = record;
    saveState(args.stateFile, state);
    console.log(`[collector] favorites auto import ${record.status} discovered=${record.discovered_count}`);
    return record;
  }

  try {
    const result = await apiCall(args.apiBase, "/api/collector/wechat-favorites/import", {
      method: "POST",
      payload: {
        export_text: "",
        urls: freshUrls.slice(0, 200),
        output_language: args.outputLanguage,
        include_text_blocks: false,
        limit: 200,
        process_immediately: false,
      },
    });
    record.status = "imported";
    record.imported_count += Number(result?.created || 0);
    record.deduplicated_count += Number(result?.deduplicated || 0);
    record.message =
      `WeChat Favorites imported created=${record.imported_count} ` +
      `deduplicated=${record.deduplicated_count}`;
    for (const url of freshUrls.slice(0, 200)) {
      state.seen_favorite_links[url] = { seen_at: record.ts };
    }
    console.log(`[collector] ${record.message}`);
  } catch (error) {
    record.status = "error";
    record.message = `WeChat Favorites import API failed: ${error?.message || error}`;
    console.error(`[collector] ${record.message}`);
  }
  state.last_favorites_auto = record;
  saveState(args.stateFile, state);
  return record;
}

async function runPostCycleTasks(args) {
  const runtimeArgs = applyRuntimeConfig(args);
  if (!runtimeArgs.runPostCycle) {
    return;
  }

  await runWechatFavoritesAutoImport(runtimeArgs);

  try {
    const flush = await apiCall(
      runtimeArgs.apiBase,
      `/api/collector/process-pending?limit=${encodeURIComponent(String(runtimeArgs.flushPendingLimit))}`,
      {
        method: "POST",
        payload: {},
      },
    );
    console.log(
      `[collector] flush pending scanned=${flush?.scanned ?? 0} processed=${flush?.processed ?? 0} ` +
        `failed=${flush?.failed ?? 0} remaining=${flush?.remaining_pending ?? 0}`,
    );
  } catch (error) {
    console.error(`[collector] flush pending failed: ${error?.message || error}`);
  }

  try {
    const daily = await apiCall(
      runtimeArgs.apiBase,
      `/api/collector/daily-summary?hours=${encodeURIComponent(String(runtimeArgs.dailySummaryHours))}` +
        `&limit=${encodeURIComponent(String(runtimeArgs.dailySummaryLimit))}`,
    );
    const markdown = String(daily?.markdown || "").trim();
    if (markdown) {
      const abs = path.resolve(runtimeArgs.dailySummaryReport);
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      fs.writeFileSync(abs, `${markdown}\n`, "utf-8");
      console.log(`[collector] daily summary updated: ${abs}`);
    }
  } catch (error) {
    console.error(`[collector] daily summary failed: ${error?.message || error}`);
  }
}

async function runSingleCycle(args) {
  const { urls: sources, sourceMode } = await resolveSourceUrls(args);
  if (sources.length === 0) {
    console.log(
      `[collector] no source urls (mode=${sourceMode}) in ${path.resolve(args.sourceFile)}`,
    );
    return {
      sourceMode,
      submitMode: args.submitMode,
      sourceCount: 0,
      discoveredCount: 0,
      collectedCount: 0,
      pluginCount: 0,
      urlCount: 0,
      ocrCount: 0,
      skippedSeenCount: 0,
      failedCount: 0,
      sourceSummaries: [],
      rows: [],
    };
  }

  const state = loadState(args.stateFile);
  state.seen_links = state.seen_links || {};
  const sourceStats = new Map(sources.map((sourceUrl) => [sourceUrl, createSourceStats(sourceUrl)]));

  await apiCall(args.apiBase, "/healthz");

  const browser = await puppeteer.launch({
    executablePath: args.chromePath,
    headless: args.headless,
    defaultViewport: { width: 1440, height: 920 },
    args: [
      "--no-first-run",
      "--disable-blink-features=AutomationControlled",
      "--disable-dev-shm-usage",
    ],
  });

  const rows = [];
  let discoveredCount = 0;
  let collectedCount = 0;
  let pluginCount = 0;
  let urlCount = 0;
  let ocrCount = 0;
  let skippedSeenCount = 0;
  let failedCount = 0;
  const pendingArticles = [];

  try {
    for (const sourceUrl of sources) {
      if (
        (args.submitMode === "browser-batch" && pendingArticles.length >= args.maxCollectPerCycle) ||
        (args.submitMode !== "browser-batch" && collectedCount >= args.maxCollectPerCycle)
      ) {
        break;
      }
      const sourcePage = await browser.newPage();
      let articleLinks = [];
      const stats = getSourceStats(sourceStats, sourceUrl);
      stats.scanned = true;
      try {
        articleLinks = await discoverArticleLinks(sourcePage, sourceUrl, args.maxDiscoverPerSource);
      } catch (error) {
        const note = `discover failed: ${error?.message || error}`;
        stats.failed_count += 1;
        stats.discover_failed_count += 1;
        stats.last_error = String(note).slice(0, 220);
        rows.push({
          sourceToken: stats.source_token,
          articleToken: "-",
          mode: "discover",
          itemId: "",
          status: "failed",
          note,
        });
        failedCount += 1;
      } finally {
        await sourcePage.close();
      }
      discoveredCount += articleLinks.length;
      stats.discovered_count += articleLinks.length;

      for (const articleUrl of articleLinks) {
        if (
          (args.submitMode === "browser-batch" && pendingArticles.length >= args.maxCollectPerCycle) ||
          (args.submitMode !== "browser-batch" && collectedCount >= args.maxCollectPerCycle)
        ) {
          break;
        }
        if (state.seen_links[articleUrl]) {
          skippedSeenCount += 1;
          stats.skipped_seen_count += 1;
          continue;
        }

        const sourceToken = stats.source_token;
        const articleToken = articleUrl.split("/").pop() || articleUrl;

        if (args.submitMode === "browser-batch") {
          stats.queued_count += 1;
          pendingArticles.push({
            sourceUrl,
            articleUrl,
            sourceToken,
            articleToken,
          });
          continue;
        }

        const articlePage = await browser.newPage();
        try {
          const extracted = await extractFromArticle(articlePage, articleUrl);

          let itemId = "";
          let mode = "plugin";
          let status = "created";
          let note = "";

          if (extracted.has_body) {
            const payload = {
              source_url: articleUrl,
              title: normalizeText(extracted.title) || null,
              raw_content: normalizeText(extracted.raw_content) || null,
              output_language: args.outputLanguage,
              deduplicate: true,
              process_immediately: false,
            };
            const result = await apiCall(args.apiBase, "/api/collector/plugin/ingest", {
              method: "POST",
              payload,
            });
            itemId = result?.item?.id || "";
            status = result?.deduplicated ? "deduplicated" : "created";
            note = result?.deduplicated ? "plugin deduplicated" : "plugin synced";
            pluginCount += 1;
            stats.plugin_count += 1;
          } else {
            mode = "url";
            const payload = {
              source_url: articleUrl,
              title: normalizeText(extracted.title) || null,
              output_language: args.outputLanguage,
              deduplicate: true,
              process_immediately: false,
            };
            const result = await apiCall(args.apiBase, "/api/collector/url/ingest", {
              method: "POST",
              payload,
            });
            itemId = result?.item?.id || "";
            status = result?.deduplicated ? "deduplicated" : "created";
            note = result?.deduplicated ? "url deduplicated" : "url extracted by backend";
            urlCount += 1;
            stats.url_count += 1;
          }
          if (status === "deduplicated") {
            stats.deduplicated_count += 1;
          }

          state.seen_links[articleUrl] = {
            seen_at: new Date().toISOString(),
            item_id: itemId,
            mode,
            status,
          };
          rows.push({ sourceToken, articleToken, mode, itemId, status, note });
          collectedCount += 1;
          stats.collected_count += 1;
          console.log(
            `[collector] ${mode} ${articleUrl} -> ${itemId || "no-item"} (${status})`,
          );
        } catch (error) {
          failedCount += 1;
          stats.failed_count += 1;
          stats.last_error = String(error?.message || error).slice(0, 220);
          rows.push({
            sourceToken: stats.source_token,
            articleToken: articleUrl.split("/").pop() || articleUrl,
            mode: "collect",
            itemId: "",
            status: "failed",
            note: String(error?.message || error).slice(0, 180),
          });
        } finally {
          await articlePage.close();
        }
      }
    }

    if (args.submitMode === "browser-batch" && pendingArticles.length > 0) {
      const pendingMap = new Map(pendingArticles.map((entry) => [entry.articleUrl, entry]));
      const articleChunks = chunkItems(pendingArticles.map((entry) => entry.articleUrl), args.batchSubmitSize);

      for (const sourceUrls of articleChunks) {
        try {
          const batchResult = await apiCall(args.apiBase, "/api/collector/browser/batch-ingest", {
            method: "POST",
            payload: {
              source_urls: sourceUrls,
              output_language: args.outputLanguage,
              deduplicate: true,
              process_immediately: false,
            },
          });
          const results = Array.isArray(batchResult?.results) ? batchResult.results : [];
          for (const result of results) {
            const articleUrl = sanitizeUrl(result?.source_url);
            const entry = pendingMap.get(articleUrl);
            if (!entry) continue;

            const status = result?.status || "failed";
            const ingestRoute = normalizeText(result?.ingest_route || "");
            const itemId = normalizeText(result?.item_id || "");
            let mode = "browser-batch";
            let note = "";

            if (status === "failed") {
              note = normalizeText(result?.error || "browser batch ingest failed");
              failedCount += 1;
              const sourceStatsEntry = getSourceStats(sourceStats, entry.sourceUrl);
              sourceStatsEntry.failed_count += 1;
              sourceStatsEntry.last_error = note.slice(0, 220);
            } else {
              const sourceStatsEntry = getSourceStats(sourceStats, entry.sourceUrl);
              state.seen_links[articleUrl] = {
                seen_at: new Date().toISOString(),
                item_id: itemId,
                mode: ingestRoute || mode,
                status,
              };
              collectedCount += 1;
              sourceStatsEntry.collected_count += 1;
              if (status === "deduplicated") {
                sourceStatsEntry.deduplicated_count += 1;
              }
              if (ingestRoute === "browser_plugin") {
                pluginCount += 1;
                sourceStatsEntry.plugin_count += 1;
                mode = "browser_plugin";
                note = status === "deduplicated" ? "browser plugin deduplicated" : "browser plugin synced";
              } else {
                urlCount += 1;
                sourceStatsEntry.url_count += 1;
                mode = "browser_url_fallback";
                note = status === "deduplicated" ? "browser url deduplicated" : "browser url fallback";
              }
            }

            rows.push({
              sourceToken: entry.sourceToken,
              articleToken: entry.articleToken,
              mode,
              itemId,
              status,
              note,
            });
            console.log(
              `[collector] ${mode} ${articleUrl} -> ${itemId || "no-item"} (${status})`,
            );
            pendingMap.delete(articleUrl);
          }
        } catch (error) {
          for (const articleUrl of sourceUrls) {
            const entry = pendingMap.get(articleUrl);
            if (!entry) continue;
            failedCount += 1;
            const sourceStatsEntry = getSourceStats(sourceStats, entry.sourceUrl);
            sourceStatsEntry.failed_count += 1;
            sourceStatsEntry.last_error = String(error?.message || error).slice(0, 220);
            rows.push({
              sourceToken: entry.sourceToken,
              articleToken: entry.articleToken,
              mode: "browser-batch",
              itemId: "",
              status: "failed",
              note: String(error?.message || error).slice(0, 180),
            });
            pendingMap.delete(articleUrl);
          }
        }
      }
    }
  } finally {
    await browser.close();
  }

  const seenEntries = Object.entries(state.seen_links);
  if (seenEntries.length > 8000) {
    seenEntries
      .sort((a, b) => String(b[1]?.seen_at || "").localeCompare(String(a[1]?.seen_at || "")))
      .slice(8000)
      .forEach(([key]) => {
        delete state.seen_links[key];
      });
  }
  state.runs = Array.isArray(state.runs) ? state.runs : [];
  const sourceSummaries = buildSourceSummaries(sources, sourceStats);
  state.runs.unshift({
    ts: new Date().toISOString(),
    source_mode: sourceMode,
    submit_mode: args.submitMode,
    source_count: sources.length,
    discovered_count: discoveredCount,
    collected_count: collectedCount,
    plugin_count: pluginCount,
    url_count: urlCount,
    ocr_count: ocrCount,
    skipped_seen_count: skippedSeenCount,
    failed_count: failedCount,
    poor_source_count: sourceSummaries.filter((source) => source.health_state === "poor").length,
    watch_source_count: sourceSummaries.filter((source) => source.health_state === "watch").length,
  });
  state.runs = state.runs.slice(0, 50);
  state.last_rows = rows.slice(0, 20);
  state.last_source_summaries = sourceSummaries.slice(0, 100);
  saveState(args.stateFile, state);

  const summary = {
    sourceMode,
    submitMode: args.submitMode,
    sourceCount: sources.length,
    discoveredCount,
    collectedCount,
    pluginCount,
    urlCount,
    ocrCount,
    skippedSeenCount,
    failedCount,
    sourceSummaries,
    rows,
  };
  renderRunReport(args.reportFile, summary);
  return summary;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!fs.existsSync(args.chromePath)) {
    throw new Error(`chrome executable not found: ${args.chromePath}`);
  }

  if (!args.loop) {
    const summary = await runSingleCycle(args);
    await runPostCycleTasks(args);
    console.log(
      `[collector] once done sources=${summary.sourceCount} discovered=${summary.discoveredCount} ` +
        `collected=${summary.collectedCount} plugin=${summary.pluginCount} url=${summary.urlCount} ocr=${summary.ocrCount} ` +
        `skipped=${summary.skippedSeenCount} failed=${summary.failedCount}`,
    );
    return;
  }

  console.log(
    `[collector] loop start interval=${args.intervalSec}s source_file=${path.resolve(args.sourceFile)} ` +
      `state_file=${path.resolve(args.stateFile)}`,
  );
  while (true) {
    const startedAt = Date.now();
    try {
      const summary = await runSingleCycle(args);
      await runPostCycleTasks(args);
      console.log(
        `[collector] cycle done discovered=${summary.discoveredCount} collected=${summary.collectedCount} ` +
          `plugin=${summary.pluginCount} url=${summary.urlCount} ocr=${summary.ocrCount} failed=${summary.failedCount}`,
      );
    } catch (error) {
      console.error(`[collector] cycle failed: ${error?.message || error}`);
    }
    const elapsedMs = Date.now() - startedAt;
    const sleepMs = Math.max(10_000, args.intervalSec * 1000 - elapsedMs);
    await sleep(sleepMs);
  }
}

main().catch((error) => {
  console.error(`[collector] fatal: ${error?.message || error}`);
  process.exit(1);
});
