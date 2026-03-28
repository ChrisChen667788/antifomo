#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import puppeteer from "puppeteer-core";

const DEFAULTS = {
  apiBase: "http://127.0.0.1:8000",
  chromePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  sourceApiPath: "/api/collector/sources?enabled_only=true&limit=500",
  sourceFile: ".tmp/wechat_collector_sources.txt",
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
    if (token === "--no-post-cycle") {
      args.runPostCycle = false;
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
  await sleep(1600);

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

    const lines = [];
    if (title) lines.push(`标题：${title}`);
    if (author) lines.push(`作者：${author}`);
    if (publishTime) lines.push(`发布时间：${publishTime}`);
    if (keywords) lines.push(`关键词：${keywords}`);
    if (description) lines.push(`摘要线索：${description}`);
    if (body) lines.push(`正文：${body}`);

    return {
      final_url: location.href,
      title,
      source_domain: location.hostname || "",
      raw_content: lines.join("\n"),
      has_body: body.length >= 120,
      content_length: body.length,
    };
  });
}

function renderRunReport(reportPath, summary) {
  const rows = summary.rows || [];
  const lines = [
    "# Desktop WeChat Collector 报告",
    "",
    `- time: ${new Date().toISOString()}`,
    `- source_mode: ${summary.sourceMode || "unknown"}`,
    `- source_count: ${summary.sourceCount}`,
    `- discovered_links: ${summary.discoveredCount}`,
    `- collected: ${summary.collectedCount}`,
    `- submitted_plugin: ${summary.pluginCount}`,
    `- submitted_url_fallback: ${summary.urlCount}`,
    `- submitted_ocr_fallback: ${summary.ocrCount}`,
    `- skipped_seen: ${summary.skippedSeenCount}`,
    `- failed: ${summary.failedCount}`,
    "",
    "| source | article | mode | item_id | status | note |",
    "|---|---|---|---|---|---|",
  ];
  for (const row of rows) {
    lines.push(
      `| ${row.sourceToken} | ${row.articleToken} | ${row.mode} | ${row.itemId || ""} | ${row.status} | ${row.note || ""} |`,
    );
  }
  const abs = path.resolve(reportPath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, `${lines.join("\n")}\n`, "utf-8");
}

async function runPostCycleTasks(args) {
  if (!args.runPostCycle) {
    return;
  }

  try {
    const flush = await apiCall(
      args.apiBase,
      `/api/collector/process-pending?limit=${encodeURIComponent(String(args.flushPendingLimit))}`,
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
      args.apiBase,
      `/api/collector/daily-summary?hours=${encodeURIComponent(String(args.dailySummaryHours))}` +
        `&limit=${encodeURIComponent(String(args.dailySummaryLimit))}`,
    );
    const markdown = String(daily?.markdown || "").trim();
    if (markdown) {
      const abs = path.resolve(args.dailySummaryReport);
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
      sourceCount: 0,
      discoveredCount: 0,
      collectedCount: 0,
      pluginCount: 0,
      urlCount: 0,
      ocrCount: 0,
      skippedSeenCount: 0,
      failedCount: 0,
      rows: [],
    };
  }

  const state = loadState(args.stateFile);
  state.seen_links = state.seen_links || {};

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

  try {
    for (const sourceUrl of sources) {
      if (collectedCount >= args.maxCollectPerCycle) break;
      const sourcePage = await browser.newPage();
      let articleLinks = [];
      try {
        articleLinks = await discoverArticleLinks(sourcePage, sourceUrl, args.maxDiscoverPerSource);
      } catch (error) {
        rows.push({
          sourceToken: sourceUrl.split("/").pop() || sourceUrl,
          articleToken: "-",
          mode: "discover",
          itemId: "",
          status: "failed",
          note: `discover failed: ${error?.message || error}`,
        });
        failedCount += 1;
      } finally {
        await sourcePage.close();
      }
      discoveredCount += articleLinks.length;

      for (const articleUrl of articleLinks) {
        if (collectedCount >= args.maxCollectPerCycle) break;
        if (state.seen_links[articleUrl]) {
          skippedSeenCount += 1;
          continue;
        }

        const articlePage = await browser.newPage();
        try {
          const extracted = await extractFromArticle(articlePage, articleUrl);
          const sourceToken = sourceUrl.split("/").pop() || sourceUrl;
          const articleToken = articleUrl.split("/").pop() || articleUrl;

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
          }

          state.seen_links[articleUrl] = {
            seen_at: new Date().toISOString(),
            item_id: itemId,
            mode,
            status,
          };
          rows.push({ sourceToken, articleToken, mode, itemId, status, note });
          collectedCount += 1;
          console.log(
            `[collector] ${mode} ${articleUrl} -> ${itemId || "no-item"} (${status})`,
          );
        } catch (error) {
          failedCount += 1;
          rows.push({
            sourceToken: sourceUrl.split("/").pop() || sourceUrl,
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
  state.runs.unshift({
    ts: new Date().toISOString(),
    source_mode: sourceMode,
    source_count: sources.length,
    discovered_count: discoveredCount,
    collected_count: collectedCount,
    plugin_count: pluginCount,
    url_count: urlCount,
    ocr_count: ocrCount,
    skipped_seen_count: skippedSeenCount,
    failed_count: failedCount,
  });
  state.runs = state.runs.slice(0, 50);
  saveState(args.stateFile, state);

  const summary = {
    sourceMode,
    sourceCount: sources.length,
    discoveredCount,
    collectedCount,
    pluginCount,
    urlCount,
    ocrCount,
    skippedSeenCount,
    failedCount,
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
