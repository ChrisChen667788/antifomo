"use client";

import type { UiResearchActionCard } from "@/lib/research-action-cards";

type ResearchActionCardsPanelProps = {
  t: (key: string, fallback?: string) => string;
  title: string;
  subtitle: string;
  cards: UiResearchActionCard[];
  planning: boolean;
  saving: boolean;
  onPlan: () => void;
  onSave: () => void;
  onSaveToFocus: () => void;
};

const PHASE_TONE: Record<string, string> = {
  "短期": "1-2周",
  "中期": "2-6周",
  "长期": "6周以上",
  "Short term": "1-2周",
  "Mid term": "2-6周",
  "Long term": "6周以上",
};

export function ResearchActionCardsPanel({
  t,
  title,
  subtitle,
  cards,
  planning,
  saving,
  onPlan,
  onSave,
  onSaveToFocus,
}: ResearchActionCardsPanelProps) {
  return (
    <section className="rounded-[28px] border border-slate-200/85 bg-white/94 p-5 shadow-[0_24px_70px_-54px_rgba(15,23,42,0.24)] md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("research.actionCards", "行动卡")}</p>
          <h3 className="mt-2 text-[24px] font-semibold tracking-[-0.04em] text-slate-900">{title}</h3>
          <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onPlan}
            disabled={planning}
            className="af-btn af-btn-secondary border border-slate-200/80 bg-white px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {planning ? t("research.planningActions", "生成中...") : t("research.generateActions", "生成行动卡")}
          </button>
          {cards.length ? (
            <>
              <button
                type="button"
                onClick={onSave}
                disabled={saving}
                className="af-btn af-btn-secondary border border-slate-200/80 bg-white px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("research.saveActions", "保存行动卡")}
              </button>
              <button
                type="button"
                onClick={onSaveToFocus}
                disabled={saving}
                className="af-btn af-btn-primary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              >
                {t("research.saveActionsToFocus", "加入 Focus 参考")}
              </button>
            </>
          ) : null}
        </div>
      </div>

      {cards.length ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-3">
          {cards.map((card) => (
            <article
              key={`${card.action_type}-${card.title}`}
              className="rounded-[24px] border border-slate-200/80 bg-white p-4 shadow-[0_18px_42px_-34px_rgba(15,23,42,0.2)]"
            >
              <div className="flex items-start justify-between gap-3">
                <h4 className="min-w-0 break-words text-[17px] font-semibold leading-7 text-slate-900">
                  {card.title}
                </h4>
                <span className="shrink-0 rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white">
                {card.priorityLabel}
              </span>
            </div>

              <p className="mt-3 break-words whitespace-pre-wrap text-sm leading-6 text-slate-600">
                {card.summary}
              </p>

              <div className="mt-4 grid gap-2 text-xs text-slate-500">
                {card.target_persona ? (
                  <div className="rounded-[18px] border border-slate-200/80 bg-slate-50 px-3 py-2.5 break-words">
                    <span className="font-semibold text-slate-700">优先对象：</span>
                    {card.target_persona}
                  </div>
                ) : null}
                {card.execution_window ? (
                  <div className="rounded-[18px] border border-slate-200/80 bg-slate-50 px-3 py-2.5 break-words">
                    <span className="font-semibold text-slate-700">执行窗口：</span>
                    {card.execution_window}
                  </div>
                ) : null}
                {card.deliverable ? (
                  <div className="rounded-[18px] border border-slate-200/80 bg-slate-50 px-3 py-2.5 break-words">
                    <span className="font-semibold text-slate-700">产出物：</span>
                    {card.deliverable}
                  </div>
                ) : null}
              </div>

              {card.phases.length ? (
                <div className="mt-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">
                    {t("research.actionTimeline", "推进节奏")}
                  </div>
                  <div className="mt-2 grid gap-2.5">
                    {card.phases.map((phase) => (
                      <div
                        key={`${card.action_type}-${phase.label}-${phase.content}`}
                        className="rounded-[20px] border border-slate-200/80 bg-slate-50 px-3 py-3"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white">
                            {phase.label}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            {phase.horizon || PHASE_TONE[phase.label] || ""}
                          </span>
                        </div>
                        <div className="mt-2 break-words whitespace-pre-wrap text-xs leading-5 text-slate-600">
                          {phase.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {card.evidenceCards.length ? (
                <div className="mt-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">
                    {t("research.actionEvidence", "证据入口")}
                  </div>
                  <div className="mt-2 grid gap-2">
                    {card.evidenceCards.map((evidence) =>
                      evidence.url ? (
                        <a
                          key={`${card.action_type}-${evidence.url}`}
                          href={evidence.url}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-[18px] border border-slate-200/80 bg-white px-3 py-2 text-xs leading-5 text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
                        >
                          {evidence.label}
                        </a>
                      ) : (
                        <div
                          key={`${card.action_type}-${evidence.label}`}
                          className="rounded-[18px] border border-slate-200/80 bg-white px-3 py-2 text-xs leading-5 text-slate-600"
                        >
                          {evidence.label}
                        </div>
                      ),
                    )}
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-[22px] border border-dashed border-slate-200 bg-slate-50/75 p-4 text-sm text-slate-500">
          {t("research.actionCardsEmptyHint", "先生成行动卡，再将其批量保存到知识库或 Focus 参考。")}
        </div>
      )}
    </section>
  );
}
