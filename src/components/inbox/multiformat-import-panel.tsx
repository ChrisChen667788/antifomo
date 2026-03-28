"use client";

import { useMemo, useState } from "react";
import {
  createCollectorRssSource,
  ingestNewsletter,
  ingestYouTubeTranscript,
  pullCollectorRssFeeds,
  uploadCollectorFile,
  type ApiItem,
  type CollectorFeedPullResult,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

type ImportMode = "rss" | "newsletter" | "file" | "youtube";

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

export function MultiFormatImportPanel() {
  const { preferences, t } = useAppPreferences();
  const [mode, setMode] = useState<ImportMode>("rss");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [latestItem, setLatestItem] = useState<ApiItem | null>(null);
  const [latestPull, setLatestPull] = useState<CollectorFeedPullResult | null>(null);

  const [rssUrl, setRssUrl] = useState("");
  const [rssTitle, setRssTitle] = useState("");
  const [rssNote, setRssNote] = useState("");

  const [newsletterTitle, setNewsletterTitle] = useState("");
  const [newsletterSender, setNewsletterSender] = useState("");
  const [newsletterUrl, setNewsletterUrl] = useState("");
  const [newsletterBody, setNewsletterBody] = useState("");

  const [fileTitle, setFileTitle] = useState("");
  const [fileSourceUrl, setFileSourceUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileMimeType, setFileMimeType] = useState("");
  const [fileBase64, setFileBase64] = useState("");
  const [fileExtractedText, setFileExtractedText] = useState("");

  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeTranscript, setYoutubeTranscript] = useState("");

  const tabs = useMemo(
    () => [
      { key: "rss" as const, label: "RSS" },
      { key: "newsletter" as const, label: "Newsletter" },
      { key: "file" as const, label: "PDF / File" },
      { key: "youtube" as const, label: "YouTube" },
    ],
    [],
  );

  const resetFeedback = () => {
    setError("");
    setMessage("");
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    resetFeedback();
    setFileName(file.name);
    setFileMimeType(file.type || "application/octet-stream");
    const arrayBuffer = await file.arrayBuffer();
    setFileBase64(arrayBufferToBase64(arrayBuffer));
    try {
      const extractedText = await file.text();
      setFileExtractedText(extractedText.slice(0, 80000));
    } catch {
      setFileExtractedText("");
    }
  };

  const submitRss = async () => {
    if (!rssUrl.trim()) {
      setError(t("collector.rssMissing", "请先输入 RSS URL。"));
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      await createCollectorRssSource({
        source_url: rssUrl.trim(),
        title: rssTitle.trim() || undefined,
        note: rssNote.trim() || undefined,
        pull_immediately: true,
        limit: 8,
        output_language: preferences.language,
      });
      const pull = await pullCollectorRssFeeds({
        limit: 8,
        output_language: preferences.language,
      });
      setLatestPull(pull.results[0] || null);
      setLatestItem(null);
      setMessage(
        pull.results[0]
          ? `RSS 已同步：新增 ${pull.results[0].new_items}，去重 ${pull.results[0].deduplicated_items}。`
          : "RSS 源已创建。",
      );
      setRssUrl("");
      setRssTitle("");
      setRssNote("");
    } catch {
      setError("RSS 导入失败，请检查源地址或后端服务。");
    } finally {
      setBusy(false);
    }
  };

  const submitNewsletter = async () => {
    if (!newsletterTitle.trim() || !newsletterBody.trim()) {
      setError("请填写 newsletter 标题和正文。");
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      const response = await ingestNewsletter({
        title: newsletterTitle.trim(),
        sender: newsletterSender.trim() || undefined,
        source_url: newsletterUrl.trim() || undefined,
        raw_content: newsletterBody.trim(),
        output_language: preferences.language,
      });
      setLatestItem(response.item);
      setLatestPull(null);
      setMessage(response.deduplicated ? "该 newsletter 已存在，已直接复用。" : "Newsletter 已进入处理流。");
      setNewsletterTitle("");
      setNewsletterSender("");
      setNewsletterUrl("");
      setNewsletterBody("");
    } catch {
      setError("Newsletter 导入失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  const submitFile = async () => {
    if (!fileName || !fileBase64) {
      setError("请先选择文件。");
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      const response = await uploadCollectorFile({
        file_name: fileName,
        mime_type: fileMimeType || "application/octet-stream",
        file_base64: fileBase64,
        extracted_text: fileExtractedText || undefined,
        title: fileTitle.trim() || undefined,
        source_url: fileSourceUrl.trim() || undefined,
        output_language: preferences.language,
      });
      setLatestItem(response.item);
      setLatestPull(null);
      setMessage(
        response.deduplicated
          ? "该文件对应内容已存在，已直接复用。"
          : `文件已导入，解析状态：${String(response.metadata.parse_status || "parsed")}`,
      );
      setFileTitle("");
      setFileSourceUrl("");
      setFileName("");
      setFileMimeType("");
      setFileBase64("");
      setFileExtractedText("");
    } catch {
      setError("文件导入失败，请确认文件大小和格式。");
    } finally {
      setBusy(false);
    }
  };

  const submitYoutube = async () => {
    if (!youtubeUrl.trim()) {
      setError("请先输入 YouTube 链接。");
      return;
    }
    setBusy(true);
    resetFeedback();
    try {
      const response = await ingestYouTubeTranscript({
        video_url: youtubeUrl.trim(),
        title: youtubeTitle.trim() || undefined,
        transcript_text: youtubeTranscript.trim() || undefined,
        output_language: preferences.language,
      });
      setLatestItem(response.item);
      setLatestPull(null);
      setMessage(response.deduplicated ? "该视频已存在，已直接复用。" : "YouTube transcript 已进入处理流。");
      setYoutubeUrl("");
      setYoutubeTitle("");
      setYoutubeTranscript("");
    } catch {
      setError("YouTube 导入失败，请检查链接或补充 transcript。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <label className="block text-sm font-semibold text-slate-700">多格式输入</label>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            把 RSS、newsletter、PDF/文件和 YouTube transcript 统一导入同一条 Item 处理流。
          </p>
        </div>
        <span className="rounded-full border border-amber-200 bg-white/80 px-3 py-1 text-xs font-semibold text-amber-700">
          Collector
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setMode(tab.key)}
            className={`af-btn px-4 py-2 text-sm ${mode === tab.key ? "af-btn-primary" : "af-btn-secondary"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {mode === "rss" ? (
        <div className="mt-4 space-y-3">
          <input
            type="url"
            value={rssUrl}
            onChange={(event) => setRssUrl(event.target.value)}
            placeholder="https://example.com/feed.xml"
            className="af-input"
          />
          <input
            type="text"
            value={rssTitle}
            onChange={(event) => setRssTitle(event.target.value)}
            placeholder="RSS 标题（可选）"
            className="af-input"
          />
          <textarea
            rows={2}
            value={rssNote}
            onChange={(event) => setRssNote(event.target.value)}
            placeholder="备注（可选）"
            className="af-input resize-none leading-6"
          />
          <button type="button" onClick={() => void submitRss()} disabled={busy} className="af-btn af-btn-primary">
            {busy ? "处理中..." : "创建并同步 RSS"}
          </button>
        </div>
      ) : null}

      {mode === "newsletter" ? (
        <div className="mt-4 space-y-3">
          <input
            type="text"
            value={newsletterTitle}
            onChange={(event) => setNewsletterTitle(event.target.value)}
            placeholder="Newsletter 标题"
            className="af-input"
          />
          <div className="grid gap-3 md:grid-cols-2">
            <input
              type="text"
              value={newsletterSender}
              onChange={(event) => setNewsletterSender(event.target.value)}
              placeholder="发送方 / 邮件列表"
              className="af-input"
            />
            <input
              type="url"
              value={newsletterUrl}
              onChange={(event) => setNewsletterUrl(event.target.value)}
              placeholder="原文链接（可选）"
              className="af-input"
            />
          </div>
          <textarea
            rows={6}
            value={newsletterBody}
            onChange={(event) => setNewsletterBody(event.target.value)}
            placeholder="粘贴邮件正文或转发内容"
            className="af-input resize-y leading-6"
          />
          <button type="button" onClick={() => void submitNewsletter()} disabled={busy} className="af-btn af-btn-primary">
            {busy ? "处理中..." : "导入 Newsletter"}
          </button>
        </div>
      ) : null}

      {mode === "file" ? (
        <div className="mt-4 space-y-3">
          <input type="file" accept=".pdf,.txt,.md,.html,.csv,.json" onChange={handleFileChange} className="block w-full text-sm text-slate-600" />
          <div className="grid gap-3 md:grid-cols-2">
            <input
              type="text"
              value={fileTitle}
              onChange={(event) => setFileTitle(event.target.value)}
              placeholder="标题覆盖（可选）"
              className="af-input"
            />
            <input
              type="url"
              value={fileSourceUrl}
              onChange={(event) => setFileSourceUrl(event.target.value)}
              placeholder="原始链接（可选）"
              className="af-input"
            />
          </div>
          {fileName ? (
            <p className="text-xs text-slate-500">
              已选择：{fileName} {fileMimeType ? `· ${fileMimeType}` : ""}
            </p>
          ) : null}
          <button type="button" onClick={() => void submitFile()} disabled={busy} className="af-btn af-btn-primary">
            {busy ? "处理中..." : "上传文件"}
          </button>
        </div>
      ) : null}

      {mode === "youtube" ? (
        <div className="mt-4 space-y-3">
          <input
            type="url"
            value={youtubeUrl}
            onChange={(event) => setYoutubeUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="af-input"
          />
          <input
            type="text"
            value={youtubeTitle}
            onChange={(event) => setYoutubeTitle(event.target.value)}
            placeholder="标题覆盖（可选）"
            className="af-input"
          />
          <textarea
            rows={6}
            value={youtubeTranscript}
            onChange={(event) => setYoutubeTranscript(event.target.value)}
            placeholder="粘贴 transcript 文本；为空时仅保存视频链接"
            className="af-input resize-y leading-6"
          />
          <button type="button" onClick={() => void submitYoutube()} disabled={busy} className="af-btn af-btn-primary">
            {busy ? "处理中..." : "导入 YouTube"}
          </button>
        </div>
      ) : null}

      {message ? <p className="mt-3 text-xs text-emerald-700">{message}</p> : null}
      {error ? <p className="mt-3 text-xs text-rose-600">{error}</p> : null}

      {latestPull ? (
        <div className="mt-4 rounded-2xl border border-white/80 bg-white/70 p-3">
          <p className="text-sm font-semibold text-slate-800">{latestPull.feed_title}</p>
          <p className="mt-1 text-xs text-slate-500">
            新增 {latestPull.new_items} · 去重 {latestPull.deduplicated_items} · 跳过 {latestPull.skipped_items}
          </p>
          {latestPull.latest_titles.length ? (
            <ul className="mt-2 space-y-1 text-xs text-slate-600">
              {latestPull.latest_titles.slice(0, 3).map((title) => (
                <li key={title}>- {title}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {latestItem ? (
        <div className="mt-4 rounded-2xl border border-white/80 bg-white/70 p-3">
          <p className="text-sm font-semibold text-slate-800">{latestItem.title || "未命名内容"}</p>
          <p className="mt-1 text-xs text-slate-500">
            {latestItem.ingest_route || latestItem.source_type} · {latestItem.status}
          </p>
          <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
            {latestItem.short_summary || latestItem.source_url || "已进入处理流"}
          </p>
        </div>
      ) : null}
    </section>
  );
}
