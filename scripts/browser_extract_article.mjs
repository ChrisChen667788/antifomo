#!/usr/bin/env node
import process from "node:process";
import puppeteer from "puppeteer-core";

const DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function parseArgs(argv) {
  const args = {
    url: "",
    chromePath: DEFAULT_CHROME_PATH,
    timeoutSec: 28,
    headless: true,
    userDataDir: "",
    profileDir: "",
  };

  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === "--url" && next) {
      args.url = next;
      i += 1;
      continue;
    }
    if (token === "--chrome-path" && next) {
      args.chromePath = next;
      i += 1;
      continue;
    }
    if (token === "--timeout-sec" && next) {
      args.timeoutSec = Number(next) || args.timeoutSec;
      i += 1;
      continue;
    }
    if (token === "--user-data-dir" && next) {
      args.userDataDir = next;
      i += 1;
      continue;
    }
    if (token === "--profile-dir" && next) {
      args.profileDir = next;
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

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
      body_text: body,
      raw_content: lines.join("\n"),
      has_body: body.length >= 120,
      content_length: body.length,
      source_domain: location.hostname || "",
      is_wechat: isWeChat,
    };
  });
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.url) {
    throw new Error("--url is required");
  }

  const launchOptions = {
    executablePath: args.chromePath,
    headless: args.headless,
    defaultViewport: { width: 1440, height: 920 },
    args: [
      "--no-first-run",
      "--disable-blink-features=AutomationControlled",
      "--disable-dev-shm-usage",
    ],
  };

  if (args.userDataDir) {
    launchOptions.userDataDir = args.userDataDir;
  }
  if (args.profileDir) {
    launchOptions.args.push(`--profile-directory=${args.profileDir}`);
  }

  const browser = await puppeteer.launch(launchOptions);
  try {
    const page = await browser.newPage();
    const extracted = await extractFromPage(page, args.url);
    process.stdout.write(`${JSON.stringify({
      ...extracted,
      title: normalizeText(extracted.title),
      body_text: normalizeText(extracted.body_text),
      raw_content: normalizeText(extracted.raw_content),
      source_domain: normalizeText(extracted.source_domain),
    })}\n`);
    await page.close();
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || error?.message || String(error)}\n`);
  process.exit(1);
});
