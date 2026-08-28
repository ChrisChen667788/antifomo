"use client";

import type { ChangeEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  importWechatFavorites,
  listWechatFavoriteImportBatches,
  previewWechatFavorites,
} from "@/lib/api";
import type {
  CollectorWechatFavoriteImportBatch,
  CollectorWechatFavoriteImportResponse,
  CollectorWechatFavoritePreviewResponse,
} from "@/lib/api/types";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

interface WechatFavoritesImportPanelProps {
  onImported?: (result: CollectorWechatFavoriteImportResponse) => void;
  onBatchSelected?: (batch: CollectorWechatFavoriteImportBatch) => void;
}

const WECHAT_IMPORT_BATCH_KEY = "anti_fomo_wechat_import_review_batch_id";
const WECHAT_FAVORITES_FOCUS_GOAL_KEY = "anti_fomo_wechat_favorites_focus_goal";

function formatBatchStatus(status: string) {
  if (status === "ready") return "可处理";
  if (status === "processing") return "解析中";
  if (status === "failed") return "有失败";
  if (status === "reviewed") return "已处理";
  if (status === "empty") return "空批次";
  return status || "未知";
}

function batchChipClass(status: string) {
  if (status === "ready") return "af-chip-success";
  if (status === "processing") return "af-chip-info";
  if (status === "failed") return "af-chip-danger";
  if (status === "reviewed") return "af-chip";
  return "af-chip-warning";
}

export function WechatFavoritesImportPanel({
  onImported,
  onBatchSelected,
}: WechatFavoritesImportPanelProps) {
  const { preferences } = useAppPreferences();
  const [exportText, setExportText] = useState("");
  const [fileName, setFileName] = useState("");
  const [busyAction, setBusyAction] = useState<"" | "preview" | "import" | "refresh">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [latestResult, setLatestResult] = useState<CollectorWechatFavoriteImportResponse | null>(null);
  const [latestPreview, setLatestPreview] = useState<CollectorWechatFavoritePreviewResponse | null>(null);
  const [latestBatch, setLatestBatch] = useState<CollectorWechatFavoriteImportBatch | null>(null);

  const resetFeedback = () => {
    setMessage("");
    setError("");
  };

  const refreshLatestBatch = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setBusyAction("refresh");
      setMessage("");
      setError("");
    }
    try {
      const result = await listWechatFavoriteImportBatches({ limit: 1, includeReviewed: false });
      const batch = result.items[0] || null;
      setLatestBatch(batch);
      if (batch) {
        window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, batch.id);
      }
      if (showLoading) {
        setMessage(batch ? "已恢复最近一次微信收藏导入批次。" : "暂无可继续处理的微信收藏导入批次。");
      }
    } catch {
      if (showLoading) {
        setError("恢复最近导入批次失败，请稍后重试。");
      }
    } finally {
      if (showLoading) {
        setBusyAction("");
      }
    }
  }, []);

  useEffect(() => {
    void refreshLatestBatch(false);
  }, [refreshLatestBatch]);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    resetFeedback();
    setFileName(
      files.length === 1
        ? files[0].name
        : `${files.length} 个文件：${files.slice(0, 3).map((file) => file.name).join("、")}${
            files.length > 3 ? " 等" : ""
          }`,
    );
    const textBlocks = await Promise.all(files.map((file) => file.text()));
    setExportText(textBlocks.join("\n\n").slice(0, 2_400_000));
    setLatestPreview(null);
  };

  const resolveImportText = (incomingText?: string) => (incomingText ?? exportText).trim();

  const submitPreview = async (incomingText?: string) => {
    const text = resolveImportText(incomingText);
    if (!text) {
      setError("请先选择微信收藏导出文件，或粘贴收藏链接/HTML。");
      return;
    }
    setBusyAction("preview");
    resetFeedback();
    try {
      const result = await previewWechatFavorites({
        export_text: text,
        limit: 500,
        include_text_blocks: true,
      });
      setLatestPreview(result);
      setLatestResult(null);
      setMessage(
        result.total_candidates
          ? `预检完成：识别 ${result.total_candidates} 条，其中链接 ${result.url_candidates} 条，正文块 ${result.text_candidates} 条。`
          : "预检完成：没有识别到可导入的公众号文章。",
      );
    } catch {
      setError("微信收藏预检失败，请检查导出内容或稍后重试。");
    } finally {
      setBusyAction("");
    }
  };

  const submitImport = async (incomingText?: string) => {
    const text = resolveImportText(incomingText);
    if (!text) {
      setError("请先选择微信收藏导出文件，或粘贴收藏链接/HTML。");
      return;
    }
    setBusyAction("import");
    resetFeedback();
    try {
      const result = await importWechatFavorites({
        export_text: text,
        output_language: preferences.language,
        limit: 500,
        include_text_blocks: true,
        process_immediately: false,
      });
      setLatestResult(result);
      setLatestPreview(null);
      if (result.batch) {
        setLatestBatch(result.batch);
        window.localStorage.setItem(WECHAT_IMPORT_BATCH_KEY, result.batch.id);
      }
      if (result.total_candidates === 0) {
        setError("没有识别到可导入的公众号文章。");
        return;
      }
      window.localStorage.setItem(
        WECHAT_FAVORITES_FOCUS_GOAL_KEY,
        "清理刚导入的微信收藏，保留值得沉淀的文章并形成知识库条目",
      );
      setMessage(
        `微信收藏已入队：新增 ${result.created}，去重 ${result.deduplicated}，无效 ${result.invalid}。`,
      );
      setExportText("");
      setFileName("");
      onImported?.(result);
    } catch {
      setError("微信收藏导入失败，请检查导出内容或稍后重试。");
    } finally {
      setBusyAction("");
    }
  };

  const importFromClipboard = async () => {
    if (!navigator.clipboard?.readText) {
      setError("当前浏览器不支持读取剪贴板。");
      return;
    }
    resetFeedback();
    try {
      const text = await navigator.clipboard.readText();
      await submitImport(text);
    } catch {
      setError("读取剪贴板失败，请粘贴内容后再导入。");
    }
  };

  const latestImportPreview = latestResult?.results
    .filter((item) => item.status === "created" || item.status === "deduplicated")
    .slice(0, 4);
  const latestBatchProgress = useMemo(() => {
    if (!latestBatch?.item_ids.length) return 0;
    const handled = latestBatch.ready + latestBatch.failed + latestBatch.triaged;
    return Math.min(100, Math.round((handled / latestBatch.item_ids.length) * 100));
  }, [latestBatch]);
  const latestBatchLabel = latestBatch ? formatBatchStatus(latestBatch.status) : "";
  const latestBatchCreatedAt = latestBatch
    ? new Date(latestBatch.created_at).toLocaleString(preferences.language, {
        hour12: false,
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <section className="af-glass mb-5 rounded-3xl p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">
            WeChat Favorites
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-normal text-[var(--af-text-primary)]">
            微信收藏导入
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-[var(--af-text-tertiary)]">
            支持导出文件、复制链接、HTML/TXT 批量导入。微信暂无公开收藏夹 API，自动化采集需走本地 Agent。
          </p>
        </div>
        <span className="af-chip af-chip-info px-3 py-1 text-xs font-semibold">
          链接优先 · 正文兜底
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-[var(--af-text-tertiary)] md:grid-cols-3">
        <div className="af-surface-card rounded-2xl border px-3 py-2">
          <p className="font-semibold text-[var(--af-text-primary)]">1. 粘贴或上传</p>
          <p className="mt-1">链接、网页源码、TXT/HTML 都可预检。</p>
        </div>
        <div className="af-surface-card rounded-2xl border px-3 py-2">
          <p className="font-semibold text-[var(--af-text-primary)]">2. 去重入队</p>
          <p className="mt-1">批量解析并复用已有卡片。</p>
        </div>
        <div className="af-surface-card rounded-2xl border px-3 py-2">
          <p className="font-semibold text-[var(--af-text-primary)]">3. 专注清理</p>
          <p className="mt-1">导入后可在 Focus 中集中筛选沉淀。</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
        <textarea
          rows={4}
          value={exportText}
          onChange={(event) => {
            resetFeedback();
            setExportText(event.target.value);
            setLatestPreview(null);
          }}
          placeholder="粘贴微信收藏导出的 HTML/TXT，或 mp.weixin.qq.com 链接列表"
          className="af-input min-h-28 resize-y leading-6"
        />
        <div className="flex flex-col gap-2 sm:flex-row lg:w-44 lg:flex-col">
          <label className="af-btn af-btn-secondary cursor-pointer justify-center px-4 py-2 text-sm">
            上传文件
            <input
              type="file"
              accept=".html,.htm,.txt,.md,.csv,.url,.webloc"
              multiple
              onChange={handleFileChange}
              className="sr-only"
            />
          </label>
          <button
            type="button"
            onClick={() => void importFromClipboard()}
            disabled={busyAction !== ""}
            className="af-btn af-btn-secondary justify-center px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            粘贴导入
          </button>
          <button
            type="button"
            onClick={() => void submitPreview()}
            disabled={busyAction !== ""}
            className="af-btn af-btn-secondary justify-center px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "preview" ? "预检中..." : "预检"}
          </button>
          <button
            type="button"
            onClick={() => void submitImport()}
            disabled={busyAction !== ""}
            className="af-btn af-btn-primary justify-center px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "import" ? "导入中..." : "导入并解析"}
          </button>
        </div>
      </div>

      {fileName ? <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">已选择：{fileName}</p> : null}
      {message ? <p className="mt-3 text-xs font-medium af-state-text-success">{message}</p> : null}
      {error ? <p className="mt-3 text-xs font-medium af-state-text-danger">{error}</p> : null}

      {latestBatch ? (
        <div className="af-surface-card mt-3 rounded-2xl border px-3 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--af-text-primary)]">
                最近导入 · {latestBatchCreatedAt}
              </p>
              <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                总计 {latestBatch.item_ids.length} · 可处理 {latestBatch.ready} · 解析中 {latestBatch.processing} · 失败 {latestBatch.failed} · 已处理 {latestBatch.triaged}
              </p>
            </div>
            <span className={`af-chip px-3 py-1 text-xs font-semibold ${batchChipClass(latestBatch.status)}`}>
              {latestBatchLabel}
            </span>
          </div>
          <div className="af-progress-track mt-3 h-1.5 overflow-hidden rounded-full">
            <div
              className="af-progress-fill h-full rounded-full transition-all"
              style={{ width: `${latestBatchProgress}%` }}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onBatchSelected?.(latestBatch)}
              className="af-btn af-btn-secondary px-3 py-1.5 text-xs"
            >
              继续处理
            </button>
            <button
              type="button"
              onClick={() => void refreshLatestBatch()}
              disabled={busyAction !== ""}
              className="af-btn af-btn-secondary px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busyAction === "refresh" ? "刷新中..." : "刷新批次"}
            </button>
            <Link href="/focus" className="af-btn af-btn-secondary px-3 py-1.5 text-xs">
              进入 Focus
            </Link>
          </div>
        </div>
      ) : null}

      {latestPreview?.samples.length ? (
        <div className="af-surface-card mt-3 rounded-2xl border p-3">
          <p className="af-kicker">
            预览 · {latestPreview.total_candidates} 条
          </p>
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {latestPreview.samples.slice(0, 6).map((item) => (
              <div key={`${item.source_url || item.title}-${item.body_source}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                <p className="line-clamp-1 text-sm font-semibold text-[var(--af-text-primary)]">
                  {item.title || "微信收藏公众号文章"}
                </p>
                <p className="mt-1 line-clamp-1 text-xs text-[var(--af-text-tertiary)]">
                  {item.body_source === "wechat_favorites_url" ? "公众号链接" : "收藏正文"} · {item.source_url || "wechat.local"}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {latestImportPreview?.length ? (
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
          {latestImportPreview.map((item) => (
            <div key={`${item.item_id || item.source_url}-${item.status}`} className="af-surface-card rounded-2xl border px-3 py-2">
              <p className="line-clamp-1 text-sm font-semibold text-[var(--af-text-primary)]">
                {item.title || "微信收藏公众号文章"}
              </p>
              <p className="mt-1 line-clamp-1 text-xs text-[var(--af-text-tertiary)]">
                {item.status === "created" ? "新增" : "已存在"} · {item.source_url || item.body_source || "微信收藏"}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
