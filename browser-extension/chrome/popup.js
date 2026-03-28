const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const SETTINGS_KEY = "antiFomoApiBaseUrl";

let currentTab = null;
let extractedPage = null;

const apiBaseInput = document.getElementById("api-base");
const pageTitleEl = document.getElementById("page-title");
const pageUrlEl = document.getElementById("page-url");
const extractInfoEl = document.getElementById("extract-info");
const includeContentInput = document.getElementById("include-content");
const statusEl = document.getElementById("status");
const sendBtn = document.getElementById("send-btn");
const feedBtn = document.getElementById("feed-btn");

function setStatus(message, level = "default") {
  statusEl.textContent = message || "";
  statusEl.className = `status${level === "default" ? "" : ` ${level}`}`;
}

function normalizeApiBase(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return DEFAULT_API_BASE;
  return trimmed.replace(/\/+$/, "");
}

function normalizeText(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function readApiBaseFromStorage() {
  return new Promise((resolve) => {
    chrome.storage.sync.get([SETTINGS_KEY], (res) => {
      resolve(normalizeApiBase(res?.[SETTINGS_KEY]));
    });
  });
}

function writeApiBaseToStorage(value) {
  return new Promise((resolve) => {
    chrome.storage.sync.set({ [SETTINGS_KEY]: normalizeApiBase(value) }, resolve);
  });
}

function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs?.[0] || null);
    });
  });
}

function setExtractInfo(message) {
  extractInfoEl.textContent = message;
}

async function extractPagePayload(tabId) {
  if (!tabId) {
    return null;
  }
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const normalize = (value) => (value || "").replace(/\s+/g, " ").trim();
        const pickMeta = (...keys) => {
          for (const key of keys) {
            const escaped = key.replace(/"/g, '\\"');
            const node =
              document.querySelector(`meta[name="${escaped}"]`) ||
              document.querySelector(`meta[property="${escaped}"]`);
            const value = normalize(node?.getAttribute("content"));
            if (value) {
              return value;
            }
          }
          return "";
        };
        const nodeText = (node) => {
          if (!node) {
            return "";
          }
          const cloned = node.cloneNode(true);
          cloned.querySelectorAll("script,style,noscript,iframe").forEach((child) => child.remove());
          return normalize(cloned.innerText || cloned.textContent || "");
        };
        const collectBySelector = (selector, minLength = 80) => {
          const outputs = [];
          document.querySelectorAll(selector).forEach((node) => {
            const text = nodeText(node);
            if (text.length >= minLength) {
              outputs.push(text);
            }
          });
          return outputs;
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

        const title = normalize(
          wxTitle || pickMeta("og:title", "twitter:title") || document.title || "",
        );
        const keywords = normalize(pickMeta("keywords"));
        const description = normalize(pickMeta("og:description", "description", "twitter:description"));

        const candidates = [];
        if (isWeChat) {
          const wechatMain = nodeText(document.querySelector("#js_content"));
          if (wechatMain.length >= 80) {
            candidates.push(wechatMain);
          }
        }

        collectBySelector("article").forEach((text) => candidates.push(text));
        collectBySelector("main").forEach((text) => candidates.push(text));
        collectBySelector('[role="main"]').forEach((text) => candidates.push(text));
        collectBySelector(".article-content, .post-content, #content, .entry-content").forEach((text) =>
          candidates.push(text),
        );

        if (candidates.length === 0) {
          const bodyText = nodeText(document.body);
          if (bodyText.length >= 40) {
            candidates.push(bodyText);
          }
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
          title,
          raw_content: lines.join("\n"),
          has_body: body.length >= 120,
          content_length: body.length,
          source_domain: location.hostname || "",
          is_wechat: isWeChat,
        };
      },
    });

    return results?.[0]?.result || null;
  } catch {
    return null;
  }
}

function buildPayload(tab) {
  const title = (tab?.title || "").trim();
  const sourceUrl = (tab?.url || "").trim();
  const fallbackText = [title, sourceUrl].filter(Boolean).join("\n");

  let finalTitle = title || null;
  let finalRawContent = fallbackText || null;
  const includeContent = Boolean(includeContentInput?.checked);
  if (includeContent && extractedPage?.raw_content) {
    finalRawContent = extractedPage.raw_content;
    if (extractedPage.title) {
      finalTitle = extractedPage.title;
    }
  }

  return {
    source_type: "plugin",
    source_url: sourceUrl || null,
    title: finalTitle,
    raw_content: finalRawContent,
  };
}

async function sendCurrentPage() {
  if (!currentTab) {
    setStatus("未读取到当前页面，请重试。", "error");
    return;
  }

  const apiBase = normalizeApiBase(apiBaseInput.value);
  await writeApiBaseToStorage(apiBase);
  const url = `${apiBase}/api/items`;
  const payload = buildPayload(currentTab);

  if (!payload.source_url && !payload.raw_content) {
    setStatus("当前页面缺少可提交内容。", "error");
    return;
  }

  sendBtn.disabled = true;
  setStatus("提交中...");

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let detail = "";
      try {
        const errorPayload = await response.json();
        detail = errorPayload?.detail ? ` (${JSON.stringify(errorPayload.detail)})` : "";
      } catch {
        detail = "";
      }
      throw new Error(`HTTP ${response.status}${detail}`);
    }

    if (includeContentInput.checked && extractedPage?.has_body) {
      setStatus(`已发送，附带正文 ${extractedPage.content_length} 字。`, "ok");
    } else {
      setStatus("已发送到 Anti-fomo Inbox。", "ok");
    }
  } catch (error) {
    setStatus(`发送失败：${error?.message || "未知错误"}`, "error");
  } finally {
    sendBtn.disabled = false;
  }
}

async function init() {
  const apiBase = await readApiBaseFromStorage();
  apiBaseInput.value = apiBase;

  currentTab = await getActiveTab();
  if (!currentTab) {
    pageTitleEl.textContent = "未识别页面";
    pageUrlEl.textContent = "--";
    setExtractInfo("未读取到页面，无法提取正文。");
    return;
  }

  const title = currentTab.title || "未识别标题";
  const sourceUrl = currentTab?.url || "未识别 URL";
  pageTitleEl.textContent = title;
  pageUrlEl.textContent = sourceUrl;

  extractedPage = await extractPagePayload(currentTab.id);
  if (extractedPage?.title) {
    pageTitleEl.textContent = extractedPage.title;
  }

  if (extractedPage?.has_body) {
    const prefix = extractedPage.is_wechat ? "微信公众号正文已提取" : "正文已提取";
    setExtractInfo(`${prefix}（${extractedPage.content_length} 字）`);
  } else if (extractedPage?.raw_content && extractedPage.raw_content.length > 20) {
    setExtractInfo("未提取到完整正文，将提交页面元信息。");
  } else {
    setExtractInfo("当前页面不支持正文提取，将仅提交标题与链接。");
  }
}

sendBtn.addEventListener("click", () => {
  void sendCurrentPage();
});

feedBtn.addEventListener("click", () => {
  const apiBase = normalizeApiBase(apiBaseInput.value);
  void writeApiBaseToStorage(apiBase).then(() => {
    chrome.tabs.create({ url: "http://localhost:3000" });
  });
});

apiBaseInput.addEventListener("blur", () => {
  void writeApiBaseToStorage(apiBaseInput.value);
});

void init();
