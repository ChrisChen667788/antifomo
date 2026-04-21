"use client";

import { useEffect, useState } from "react";
import {
  createCollectorRssSource,
  listCollectorFeedSources,
  pullCollectorRssFeeds,
  type CollectorFeedSource,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

function formatTime(value: string | null) {
  if (!value) return "未同步";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function CollectorImportsPanel() {
  const { preferences } = useAppPreferences();
  const [feeds, setFeeds] = useState<CollectorFeedSource[]>([]);
  const [feedUrl, setFeedUrl] = useState("");
  const [feedTitle, setFeedTitle] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadFeeds = async () => {
    setLoading(true);
    try {
      const response = await listCollectorFeedSources("rss");
      setFeeds(response.items || []);
    } catch {
      setFeeds([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadFeeds();
  }, []);

  const handleCreate = async () => {
    if (!feedUrl.trim()) {
      setMessage("请先填写 RSS URL。");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      await createCollectorRssSource({
        source_url: feedUrl.trim(),
        title: feedTitle.trim() || undefined,
        pull_immediately: true,
        output_language: preferences.language,
      });
      setFeedUrl("");
      setFeedTitle("");
      setMessage("RSS 源已创建并完成首轮同步。");
      await loadFeeds();
    } catch {
      setMessage("RSS 源创建失败，请检查地址。");
    } finally {
      setSaving(false);
    }
  };

  const handlePull = async (feedId?: string) => {
    setSaving(true);
    setMessage("");
    try {
      const response = await pullCollectorRssFeeds({
        feed_id: feedId,
        limit: 8,
        output_language: preferences.language,
      });
      const first = response.results[0];
      setMessage(
        first
          ? `${first.feed_title}：新增 ${first.new_items}，去重 ${first.deduplicated_items}，跳过 ${first.skipped_items}。`
          : "RSS 已同步。",
      );
      await loadFeeds();
    } catch {
      setMessage("RSS 同步失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">Multi-format Intake</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-slate-900">RSS / 文件输入层</h3>
          <p className="mt-2 text-sm text-slate-500">
            管理多格式导入入口，先把 RSS 源同步进统一 Item 流，再让 Inbox 或研究流程继续处理。
          </p>
        </div>
        <button type="button" onClick={() => void handlePull()} disabled={saving} className="af-btn af-btn-secondary">
          {saving ? "同步中..." : "同步全部 RSS"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1.6fr_1fr_auto]">
        <input
          type="url"
          value={feedUrl}
          onChange={(event) => setFeedUrl(event.target.value)}
          placeholder="https://example.com/feed.xml"
          className="af-input"
        />
        <input
          type="text"
          value={feedTitle}
          onChange={(event) => setFeedTitle(event.target.value)}
          placeholder="标题（可选）"
          className="af-input"
        />
        <button type="button" onClick={() => void handleCreate()} disabled={saving} className="af-btn af-btn-primary">
          {saving ? "处理中..." : "新增 RSS"}
        </button>
      </div>

      {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}

      <div className="mt-5 space-y-3">
        {loading ? <p className="text-sm text-slate-500">正在加载 RSS 源...</p> : null}
        {!loading && feeds.length === 0 ? (
          <p className="text-sm text-slate-500">还没有 RSS 源，先添加一个可公开访问的 feed。</p>
        ) : null}
        {feeds.map((feed) => (
          <div key={feed.id} className="rounded-2xl border border-white/80 bg-white/60 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-800">{feed.title || feed.source_url}</p>
                <p className="mt-1 break-all text-xs text-slate-500">{feed.source_url}</p>
                <p className="mt-2 text-xs text-slate-500">
                  状态：{feed.status} · 最近同步：{formatTime(feed.last_synced_at)}
                </p>
                {feed.last_error ? <p className="mt-1 text-xs text-rose-600">{feed.last_error}</p> : null}
              </div>
              <button
                type="button"
                onClick={() => void handlePull(feed.id)}
                disabled={saving}
                className="af-btn af-btn-secondary px-3 py-2 text-sm"
              >
                同步
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
