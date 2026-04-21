"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createResearchConversation,
  getResearchJobTimeline,
  listResearchConversations,
  sendResearchConversationMessage,
  type ApiResearchConversation,
  type ApiResearchJobTimelineEvent,
  type ApiResearchTrackingTopic,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

type ResearchConsolePanelProps = {
  title?: string;
  description?: string;
  topicId?: string;
  topicName?: string;
  trackingTopics?: Pick<ApiResearchTrackingTopic, "id" | "name" | "keyword">[];
};

function timelineTone(stageKey: string) {
  if (stageKey === "failed") return "bg-rose-100 text-rose-700";
  if (stageKey === "completed" || stageKey === "packaging") return "bg-emerald-100 text-emerald-700";
  if (stageKey === "search" || stageKey === "extracting" || stageKey === "synthesizing") {
    return "bg-sky-100 text-sky-700";
  }
  return "bg-slate-100 text-slate-500";
}

function messageTone(role: "user" | "assistant") {
  return role === "assistant"
    ? "border-sky-100 bg-sky-50/70 text-slate-700"
    : "border-slate-200 bg-white/75 text-slate-700";
}

function parseSuggestedFollowups(conversation: ApiResearchConversation | null): string[] {
  if (!conversation) return [];
  const latestAssistant = [...conversation.messages]
    .reverse()
    .find((message) => message.role === "assistant");
  const value = latestAssistant?.payload?.suggested_followups;
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 4);
}

function formatTimestamp(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function ResearchConsolePanel({
  title,
  description,
  topicId,
  topicName,
  trackingTopics = [],
}: ResearchConsolePanelProps) {
  const { t } = useAppPreferences();
  const [allConversations, setAllConversations] = useState<ApiResearchConversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [timeline, setTimeline] = useState<ApiResearchJobTimelineEvent[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [topicFilterId, setTopicFilterId] = useState(topicId || "all");

  const effectiveTopicFilterId = topicId || topicFilterId;

  const visibleConversations = useMemo(() => {
    if (topicId) {
      return allConversations.filter((conversation) => conversation.topic_id === topicId);
    }
    if (!effectiveTopicFilterId || effectiveTopicFilterId === "all") {
      return allConversations;
    }
    return allConversations.filter((conversation) => conversation.topic_id === effectiveTopicFilterId);
  }, [allConversations, effectiveTopicFilterId, topicId]);

  const selectedConversation = useMemo(
    () =>
      visibleConversations.find((conversation) => conversation.id === selectedConversationId) ||
      visibleConversations[0] ||
      null,
    [selectedConversationId, visibleConversations],
  );

  const suggestedFollowups = useMemo(
    () => parseSuggestedFollowups(selectedConversation),
    [selectedConversation],
  );

  const reloadConversations = async (preserveSelection = true) => {
    if (!preserveSelection) {
      setSelectedConversationId("");
    }
    setError("");
    setLoading(!preserveSelection);
    setRefreshing(preserveSelection);
    try {
      const conversations = await listResearchConversations();
      setAllConversations(conversations);
      if (!preserveSelection && conversations.length) {
        const filtered = topicId
          ? conversations.filter((conversation) => conversation.topic_id === topicId)
          : effectiveTopicFilterId === "all"
            ? conversations
            : conversations.filter((conversation) => conversation.topic_id === effectiveTopicFilterId);
        setSelectedConversationId(filtered[0]?.id || conversations[0]?.id || "");
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : t("research.consoleLoadFailed", "研究对话加载失败，请稍后重试。"),
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void reloadConversations(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId]);

  useEffect(() => {
    if (!selectedConversationId && visibleConversations.length) {
      setSelectedConversationId(visibleConversations[0].id);
      return;
    }
    if (
      selectedConversationId &&
      visibleConversations.length &&
      !visibleConversations.some((conversation) => conversation.id === selectedConversationId)
    ) {
      setSelectedConversationId(visibleConversations[0].id);
    }
  }, [selectedConversationId, visibleConversations]);

  useEffect(() => {
    if (!selectedConversation?.job_id) {
      setTimeline([]);
      return;
    }
    let active = true;
    getResearchJobTimeline(selectedConversation.job_id)
      .then((events) => {
        if (!active) return;
        setTimeline(events || []);
      })
      .catch(() => {
        if (!active) return;
        setTimeline([]);
      });
    return () => {
      active = false;
    };
  }, [selectedConversation?.job_id]);

  const createConversation = async () => {
    const anchorTopicId =
      topicId ||
      (effectiveTopicFilterId !== "all" ? effectiveTopicFilterId : trackingTopics[0]?.id) ||
      undefined;
    const anchorTopic =
      trackingTopics.find((item) => item.id === anchorTopicId) ||
      (topicId ? { id: topicId, name: topicName || "", keyword: topicName || "" } : null);
    const nextConversation = await createResearchConversation({
      title:
        anchorTopic?.name
          ? `${anchorTopic.name}${t("research.consoleConversationSuffix", " 继续追问")}`
          : t("research.consoleDefaultTitle", "研究对话"),
      topic_id: anchorTopicId,
    });
    setAllConversations((current) => [
      nextConversation,
      ...current.filter((conversation) => conversation.id !== nextConversation.id),
    ]);
    setSelectedConversationId(nextConversation.id);
    return nextConversation;
  };

  const handleSend = async () => {
    const content = draft.trim();
    if (!content || sending) return;
    setSending(true);
    setError("");
    try {
      const currentConversation = selectedConversation || (await createConversation());
      const updated = await sendResearchConversationMessage(currentConversation.id, {
        content,
      });
      setAllConversations((current) => [
        updated,
        ...current.filter((conversation) => conversation.id !== updated.id),
      ]);
      setSelectedConversationId(updated.id);
      setDraft("");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : t("research.consoleSendFailed", "追问发送失败，请稍后重试。"),
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">{title || t("research.consoleKicker", "Research Console")}</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900">
            {topicName
              ? `${topicName}${t("research.consoleTopicTitleSuffix", " 研究追问")}`
              : t("research.consoleTitle", "边追问边查看研究过程")}
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {description ||
              t(
                "research.consoleDesc",
                "围绕专题或历史研究任务继续追问，保留关键证据和阶段进度，不再把研报当成一次性生成结果。",
              )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!topicId && trackingTopics.length ? (
            <select
              value={topicFilterId}
              onChange={(event) => setTopicFilterId(event.target.value)}
              className="af-input min-w-[180px] bg-white/75 text-sm"
            >
              <option value="all">{t("research.consoleAllTopics", "全部专题")}</option>
              {trackingTopics.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          ) : null}
          <button
            type="button"
            onClick={() => {
              void createConversation();
            }}
            disabled={sending}
            className="af-btn af-btn-secondary border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="spark" className="h-4 w-4" />
            {t("research.consoleNewConversation", "新建对话")}
          </button>
          <button
            type="button"
            onClick={() => {
              void reloadConversations(true);
            }}
            disabled={refreshing}
            className="af-btn af-btn-secondary border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            <AppIcon name="refresh" className="h-4 w-4" />
            {refreshing ? t("common.refreshing", "刷新中...") : t("common.refresh", "刷新")}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 rounded-2xl border border-rose-200/80 bg-rose-50/80 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-[320px,minmax(0,1fr)]">
        <div className="space-y-3">
          {loading ? (
            <div className="rounded-[24px] border border-white/70 bg-white/65 px-4 py-5 text-sm text-slate-500">
              {t("common.loading", "加载中")}
            </div>
          ) : visibleConversations.length ? (
            visibleConversations.map((conversation) => {
              const isActive = conversation.id === selectedConversation?.id;
              const latestMessage = [...conversation.messages].reverse()[0];
              return (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => setSelectedConversationId(conversation.id)}
                  className={`block w-full rounded-[24px] border px-4 py-4 text-left transition ${
                    isActive
                      ? "border-sky-200 bg-sky-50/75 shadow-[0_14px_35px_rgba(56,189,248,0.14)]"
                      : "border-white/70 bg-white/68 hover:bg-white/80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-900">{conversation.title}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {formatTimestamp(conversation.updated_at)}
                      </p>
                    </div>
                    {conversation.job_id ? (
                      <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[10px] font-semibold text-white">
                        Job
                      </span>
                    ) : null}
                  </div>
                  {latestMessage?.content ? (
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
                      {latestMessage.content}
                    </p>
                  ) : null}
                </button>
              );
            })
          ) : (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-white/70 px-4 py-5 text-sm text-slate-500">
              {t("research.consoleEmpty", "当前还没有研究对话，先创建一个专题追问窗口。")}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <article className="rounded-[26px] border border-white/70 bg-white/72 p-4">
            {selectedConversation ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{selectedConversation.title}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {selectedConversation.topic_id
                        ? `${t("research.consoleTopicTag", "专题")} · ${topicName || selectedConversation.context_payload?.topic_name || "—"}`
                        : t("research.consoleUnboundTopic", "未绑定专题")}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                    {selectedConversation.messages.length} {t("research.consoleMessageCount", "条消息")}
                  </span>
                </div>

                <div className="mt-4 space-y-3">
                  {selectedConversation.messages.map((message) => (
                    <div
                      key={message.id}
                      className={`rounded-[20px] border px-4 py-3 ${messageTone(message.role)}`}
                    >
                      <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.16em] text-slate-400">
                        <span>
                          {message.role === "assistant"
                            ? t("research.consoleAssistant", "assistant")
                            : t("research.consoleUser", "user")}
                        </span>
                        <span>{formatTimestamp(message.created_at)}</span>
                      </div>
                      <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                        {message.content}
                      </div>
                    </div>
                  ))}
                </div>

                {suggestedFollowups.length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {suggestedFollowups.map((question) => (
                      <button
                        key={question}
                        type="button"
                        onClick={() => setDraft(question)}
                        className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-700"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className="mt-4 flex items-end gap-3">
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={t("research.consoleInputPlaceholder", "继续追问预算节点、甲方、竞品、伙伴或执行动作...")}
                    rows={3}
                    className="af-input min-h-[104px] flex-1 resize-y bg-white/85 leading-6"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      void handleSend();
                    }}
                    disabled={sending || !draft.trim()}
                    className="af-btn af-btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {sending ? t("research.consoleSending", "发送中...") : t("research.consoleSend", "发送追问")}
                  </button>
                </div>
              </>
            ) : (
              <div className="rounded-[20px] border border-dashed border-slate-200 bg-white/70 px-4 py-8 text-sm text-slate-500">
                {t("research.consoleSelectHint", "左侧选择一个对话，或新建对话开始继续追问。")}
              </div>
            )}
          </article>

          <article className="rounded-[26px] border border-white/70 bg-white/72 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {t("research.consoleTimelineTitle", "研究进度 / Timeline")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {selectedConversation?.job_id
                    ? t("research.consoleTimelineDesc", "展示该研究任务的阶段推进和关键状态。")
                    : t("research.consoleTimelineNoJob", "当前对话未绑定研究任务，先基于专题版本继续追问。")}
                </p>
              </div>
            </div>
            {timeline.length ? (
              <div className="mt-4 space-y-3">
                {timeline.map((event) => (
                  <div key={`${event.created_at}-${event.stage_key}`} className="rounded-[18px] border border-slate-200/80 bg-slate-50/85 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-slate-900">{event.stage_label}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-500">{event.message}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${timelineTone(event.stage_key)}`}>
                        {event.progress_percent}%
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] text-slate-400">{formatTimestamp(event.created_at)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-[18px] border border-dashed border-slate-200 bg-white/70 px-4 py-4 text-sm text-slate-500">
                {selectedConversation?.job_id
                  ? t("research.consoleTimelineEmpty", "当前任务还没有额外的阶段事件。")
                  : t("research.consoleTimelineTopicHint", "继续追问时会直接使用当前专题的最新版本内容。")}
              </div>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}
