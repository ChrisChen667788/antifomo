"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import {
  createCollectorSource,
  deleteCollectorSource,
  importCollectorSources,
  listCollectorSources,
  updateCollectorSource,
  type CollectorSource,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import type { AppLanguage } from "@/lib/preferences";

function textByLanguage(
  language: AppLanguage,
  mapping: Partial<Record<AppLanguage, string>>,
  fallback: string,
): string {
  if (mapping[language]) return mapping[language] as string;
  if (language === "zh-TW" && mapping["zh-CN"]) return mapping["zh-CN"] as string;
  if (mapping.en) return mapping.en as string;
  return fallback;
}

function parseUrls(value: string): string[] {
  const lines = String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const urls: string[] = [];
  const seen = new Set<string>();
  for (const line of lines) {
    if (!/^https?:\/\//i.test(line)) continue;
    if (seen.has(line)) continue;
    seen.add(line);
    urls.push(line);
  }
  return urls;
}

function formatTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function CollectorSourcesPanel() {
  const { preferences } = useAppPreferences();
  const language = preferences.language;
  const [sources, setSources] = useState<CollectorSource[]>([]);
  const [sourceUrlInput, setSourceUrlInput] = useState("");
  const [sourceNoteInput, setSourceNoteInput] = useState("");
  const [batchInput, setBatchInput] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const batchUrls = useMemo(() => parseUrls(batchInput), [batchInput]);

  const i18n = {
    title: textByLanguage(
      language,
      {
        "zh-CN": "采集源管理",
        "zh-TW": "採集源管理",
        en: "Source Management",
        ja: "収集ソース管理",
        ko: "수집 소스 관리",
      },
      "采集源管理",
    ),
    description: textByLanguage(
      language,
      {
        "zh-CN": "管理采集器监控的公众号链接（文章页、目录页或聚合页均可）。",
        "zh-TW": "管理採集器監控的公眾號連結（文章頁、目錄頁或聚合頁皆可）。",
        en: "Manage collector source links (article page, index page, or aggregation page).",
        ja: "収集対象リンクを管理します（記事/一覧/集約ページ）。",
        ko: "수집 대상 링크를 관리합니다(기사/목록/집계 페이지).",
      },
      "管理采集器监控的公众号链接。",
    ),
    addSingle: textByLanguage(
      language,
      {
        "zh-CN": "新增单条",
        "zh-TW": "新增單條",
        en: "Add One",
        ja: "単体追加",
        ko: "단일 추가",
      },
      "新增单条",
    ),
    add: textByLanguage(
      language,
      {
        "zh-CN": "添加",
        "zh-TW": "添加",
        en: "Add",
        ja: "追加",
        ko: "추가",
      },
      "添加",
    ),
    note: textByLanguage(
      language,
      {
        "zh-CN": "备注（可选）",
        "zh-TW": "備註（可選）",
        en: "Note (Optional)",
        ja: "メモ（任意）",
        ko: "메모 (선택)",
      },
      "备注（可选）",
    ),
    batch: textByLanguage(
      language,
      {
        "zh-CN": "批量导入（每行一个 URL）",
        "zh-TW": "批量導入（每行一個 URL）",
        en: "Batch Import (one URL per line)",
        ja: "一括インポート（1行1URL）",
        ko: "일괄 가져오기 (줄당 URL 1개)",
      },
      "批量导入",
    ),
    import: textByLanguage(
      language,
      {
        "zh-CN": "批量导入",
        "zh-TW": "批量導入",
        en: "Import",
        ja: "一括追加",
        ko: "일괄 추가",
      },
      "批量导入",
    ),
    recognized: textByLanguage(
      language,
      {
        "zh-CN": "识别 URL",
        "zh-TW": "識別 URL",
        en: "URLs",
        ja: "URL数",
        ko: "URL 수",
      },
      "识别 URL",
    ),
    refresh: textByLanguage(
      language,
      {
        "zh-CN": "刷新",
        "zh-TW": "刷新",
        en: "Refresh",
        ja: "更新",
        ko: "새로고침",
      },
      "刷新",
    ),
    tableSource: textByLanguage(
      language,
      {
        "zh-CN": "来源链接",
        "zh-TW": "來源連結",
        en: "Source URL",
        ja: "ソースURL",
        ko: "소스 URL",
      },
      "来源链接",
    ),
    tableEnabled: textByLanguage(
      language,
      {
        "zh-CN": "状态",
        "zh-TW": "狀態",
        en: "Status",
        ja: "状態",
        ko: "상태",
      },
      "状态",
    ),
    tableCollected: textByLanguage(
      language,
      {
        "zh-CN": "最近采集",
        "zh-TW": "最近採集",
        en: "Last Collected",
        ja: "最終収集",
        ko: "최근 수집",
      },
      "最近采集",
    ),
    tableActions: textByLanguage(
      language,
      {
        "zh-CN": "操作",
        "zh-TW": "操作",
        en: "Actions",
        ja: "操作",
        ko: "작업",
      },
      "操作",
    ),
    enabled: textByLanguage(
      language,
      {
        "zh-CN": "启用",
        "zh-TW": "啟用",
        en: "Enabled",
        ja: "有効",
        ko: "활성",
      },
      "启用",
    ),
    disabled: textByLanguage(
      language,
      {
        "zh-CN": "停用",
        "zh-TW": "停用",
        en: "Disabled",
        ja: "無効",
        ko: "비활성",
      },
      "停用",
    ),
    toggle: textByLanguage(
      language,
      {
        "zh-CN": "切换",
        "zh-TW": "切換",
        en: "Toggle",
        ja: "切替",
        ko: "전환",
      },
      "切换",
    ),
    remove: textByLanguage(
      language,
      {
        "zh-CN": "删除",
        "zh-TW": "刪除",
        en: "Delete",
        ja: "削除",
        ko: "삭제",
      },
      "删除",
    ),
    empty: textByLanguage(
      language,
      {
        "zh-CN": "暂无采集源。先添加 1 条公众号链接。",
        "zh-TW": "暫無採集源。先新增 1 條公眾號連結。",
        en: "No source yet. Add one link first.",
        ja: "収集ソースがありません。まず1件追加してください。",
        ko: "수집 소스가 없습니다. 링크를 먼저 추가하세요.",
      },
      "暂无采集源。",
    ),
  };

  const refreshSources = async () => {
    setLoading(true);
    setMessage("");
    try {
      const result = await listCollectorSources(300);
      startTransition(() => {
        setSources(result.items || []);
      });
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshSources();
  }, []);

  const addSource = async () => {
    const sourceUrl = sourceUrlInput.trim();
    if (!sourceUrl) return;
    setAdding(true);
    setMessage("");
    try {
      await createCollectorSource({
        source_url: sourceUrl,
        note: sourceNoteInput.trim() || undefined,
        enabled: true,
      });
      setSourceUrlInput("");
      setSourceNoteInput("");
      await refreshSources();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setAdding(false);
    }
  };

  const importSources = async () => {
    if (!batchUrls.length) return;
    setImporting(true);
    setMessage("");
    try {
      const result = await importCollectorSources({
        urls: batchUrls,
        enabled: true,
      });
      setMessage(
        `import total=${result.total}, created=${result.created}, exists=${result.exists}, invalid=${result.invalid}`,
      );
      setBatchInput("");
      await refreshSources();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setImporting(false);
    }
  };

  const toggleSource = async (source: CollectorSource) => {
    setUpdatingId(source.id);
    setMessage("");
    try {
      await updateCollectorSource(source.id, { enabled: !source.enabled });
      await refreshSources();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setUpdatingId(null);
    }
  };

  const removeSource = async (source: CollectorSource) => {
    setDeletingId(source.id);
    setMessage("");
    try {
      await deleteCollectorSource(source.id);
      await refreshSources();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <p className="af-kicker">{i18n.title}</p>
      <p className="mt-2 text-sm text-slate-500">{i18n.description}</p>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{i18n.addSingle}</span>
          <input
            type="url"
            placeholder="https://mp.weixin.qq.com/s/..."
            className="af-input mt-2"
            value={sourceUrlInput}
            onChange={(event) => setSourceUrlInput(event.target.value)}
          />
          <input
            type="text"
            placeholder={i18n.note}
            className="af-input mt-2"
            value={sourceNoteInput}
            onChange={(event) => setSourceNoteInput(event.target.value)}
          />
          <button
            type="button"
            onClick={() => void addSource()}
            disabled={adding}
            className="af-btn af-btn-primary mt-3 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {adding ? "..." : i18n.add}
          </button>
        </label>

        <label className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{i18n.batch}</span>
          <textarea
            rows={6}
            placeholder="https://...\nhttps://..."
            className="af-input mt-2"
            value={batchInput}
            onChange={(event) => setBatchInput(event.target.value)}
          />
          <p className="mt-2 text-xs text-slate-500">
            {i18n.recognized}: {batchUrls.length}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void importSources()}
              disabled={importing || batchUrls.length === 0}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {importing ? "..." : i18n.import}
            </button>
            <button
              type="button"
              onClick={() => void refreshSources()}
              disabled={loading}
              className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "..." : i18n.refresh}
            </button>
          </div>
        </label>
      </div>

      {message ? <p className="mt-3 text-xs text-slate-500">{message}</p> : null}

      <div className="mt-4 rounded-2xl border border-white/80 bg-white/55 p-4">
        {sources.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs text-slate-600">
              <thead>
                <tr className="text-slate-500">
                  <th className="px-2 py-1">{i18n.tableSource}</th>
                  <th className="px-2 py-1">{i18n.tableEnabled}</th>
                  <th className="px-2 py-1">{i18n.tableCollected}</th>
                  <th className="px-2 py-1">{i18n.tableActions}</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id} className="border-t border-white/75">
                    <td className="px-2 py-2">
                      <a href={source.source_url} target="_blank" rel="noreferrer" className="underline">
                        {source.source_url}
                      </a>
                      {source.note ? <p className="mt-1 text-[11px] text-slate-400">{source.note}</p> : null}
                    </td>
                    <td className="px-2 py-2">
                      {source.enabled ? i18n.enabled : i18n.disabled}
                    </td>
                    <td className="px-2 py-2">{formatTime(source.last_collected_at)}</td>
                    <td className="px-2 py-2">
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={() => void toggleSource(source)}
                          disabled={updatingId === source.id}
                          className="af-btn af-btn-secondary px-2 py-1 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {updatingId === source.id ? "..." : i18n.toggle}
                        </button>
                        <button
                          type="button"
                          onClick={() => void removeSource(source)}
                          disabled={deletingId === source.id}
                          className="af-btn af-btn-secondary px-2 py-1 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {deletingId === source.id ? "..." : i18n.remove}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-500">{i18n.empty}</p>
        )}
      </div>
    </section>
  );
}
