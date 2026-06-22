"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";
import { importWechatFavorites, previewWechatFavorites } from "@/lib/api";
import type {
  CollectorWechatFavoriteImportResponse,
  CollectorWechatFavoritePreviewResponse,
} from "@/lib/api/types";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

interface WechatFavoritesImportPanelProps {
  onImported?: (result: CollectorWechatFavoriteImportResponse) => void;
}

export function WechatFavoritesImportPanel({ onImported }: WechatFavoritesImportPanelProps) {
  const { preferences } = useAppPreferences();
  const [exportText, setExportText] = useState("");
  const [fileName, setFileName] = useState("");
  const [busyAction, setBusyAction] = useState<"" | "preview" | "import">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [latestResult, setLatestResult] = useState<CollectorWechatFavoriteImportResponse | null>(null);
  const [latestPreview, setLatestPreview] = useState<CollectorWechatFavoritePreviewResponse | null>(null);

  const resetFeedback = () => {
    setMessage("");
    setError("");
  };

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
      if (result.total_candidates === 0) {
        setError("没有识别到可导入的公众号文章。");
        return;
      }
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

  return (
    <section className="af-glass mb-5 rounded-3xl border border-emerald-100/80 bg-emerald-50/55 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700/80">
            WeChat Favorites
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-normal text-slate-900">
            微信收藏一键入卡片
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
            导入公众号收藏后，Anti-FOMO 会解析成首页卡片，继续用当前卡片堆快速 Ignore / Save。
          </p>
        </div>
        <span className="rounded-full border border-emerald-200 bg-white/80 px-3 py-1 text-xs font-semibold text-emerald-700">
          URL-first
        </span>
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
            选择文件
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
            剪贴板导入
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
            {busyAction === "import" ? "导入中..." : "一键导入"}
          </button>
        </div>
      </div>

      {fileName ? <p className="mt-2 text-xs text-slate-500">已选择：{fileName}</p> : null}
      {message ? <p className="mt-3 text-xs font-medium text-emerald-700">{message}</p> : null}
      {error ? <p className="mt-3 text-xs font-medium text-rose-600">{error}</p> : null}

      {latestPreview?.samples.length ? (
        <div className="mt-3 rounded-2xl border border-white/80 bg-white/75 p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700/80">
            Preview · {latestPreview.total_candidates} items
          </p>
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {latestPreview.samples.slice(0, 6).map((item) => (
              <div key={`${item.source_url || item.title}-${item.body_source}`} className="rounded-2xl border border-slate-100 bg-white/80 px-3 py-2">
                <p className="line-clamp-1 text-sm font-semibold text-slate-800">
                  {item.title || "微信收藏公众号文章"}
                </p>
                <p className="mt-1 line-clamp-1 text-xs text-slate-500">
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
            <div key={`${item.item_id || item.source_url}-${item.status}`} className="rounded-2xl border border-white/80 bg-white/75 px-3 py-2">
              <p className="line-clamp-1 text-sm font-semibold text-slate-800">
                {item.title || "微信收藏公众号文章"}
              </p>
              <p className="mt-1 line-clamp-1 text-xs text-slate-500">
                {item.status === "created" ? "新增" : "已存在"} · {item.source_url || item.body_source || "微信收藏"}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
