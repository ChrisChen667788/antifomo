"use client";

import { useEffect, useState } from "react";
import {
  getKnowledgeRule,
  updateKnowledgeRule,
  type ApiKnowledgeRule,
} from "@/lib/api";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

const THRESHOLDS = [3.8, 4.0, 4.3];

export function KnowledgeRuleCard() {
  const { t } = useAppPreferences();
  const [rule, setRule] = useState<ApiKnowledgeRule | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    getKnowledgeRule()
      .then((result) => {
        if (active) {
          setRule(result);
        }
      })
      .catch(() => {
        if (active) {
          setMessage(t("knowledge.ruleUnavailable", "规则服务暂不可用，当前使用默认规则。"));
          setRule({
            enabled: true,
            min_score_value: 4.0,
            archive_on_like: true,
            archive_on_save: true,
          });
        }
      });
    return () => {
      active = false;
    };
  }, [t]);

  const patchRule = async (next: Partial<ApiKnowledgeRule>) => {
    if (!rule) return;
    const optimistic = { ...rule, ...next };
    setRule(optimistic);
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateKnowledgeRule(next);
      setRule(updated);
      setMessage(t("knowledge.ruleSaved", "自动归档规则已更新"));
    } catch {
      setRule(rule);
      setMessage(t("knowledge.ruleSaveFailed", "规则更新失败，已保留原设置"));
    } finally {
      setSaving(false);
    }
  };

  if (!rule) {
    return (
      <div className="af-glass rounded-[28px] p-4 text-sm text-slate-500">
        {t("common.loading", "加载中")}
      </div>
    );
  }

  const ruleExplanation = `${t("knowledge.ruleThreshold", "最低价值分")} ${rule.min_score_value.toFixed(1)} · ${
    rule.archive_on_like ? t("knowledge.ruleLike", "感兴趣后归档") : ""
  }${rule.archive_on_like && rule.archive_on_save ? " / " : ""}${
    rule.archive_on_save ? t("knowledge.ruleSave", "稍后再读后归档") : ""
  }`;

  return (
    <div className="af-glass rounded-[28px] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">{t("knowledge.rulesTitle", "自动归档规则")}</p>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            {t(
              "knowledge.rulesSubtitle",
              "高价值且已感兴趣的内容会自动进入知识库，减少重复整理。",
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void patchRule({ enabled: !rule.enabled });
          }}
          disabled={saving}
          className={`af-btn px-4 py-2 ${
            rule.enabled ? "af-btn-primary" : "af-btn-secondary"
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          <AppIcon name="knowledge" className="h-4 w-4" />
          {rule.enabled
            ? t("knowledge.ruleEnabled", "已开启自动归档")
            : t("knowledge.ruleDisabled", "自动归档已关闭")}
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-slate-500">{t("knowledge.ruleThreshold", "最低价值分")}</span>
        {THRESHOLDS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              void patchRule({ min_score_value: value });
            }}
            disabled={saving}
            className={`af-btn px-3 py-1.5 text-sm ${
              Math.abs(rule.min_score_value - value) < 0.01 ? "af-btn-primary" : "af-btn-secondary"
            } disabled:cursor-not-allowed disabled:opacity-60`}
          >
            {value.toFixed(1)}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            void patchRule({ archive_on_like: !rule.archive_on_like });
          }}
          disabled={saving}
          className={`af-btn px-3 py-1.5 text-sm ${
            rule.archive_on_like ? "af-btn-primary" : "af-btn-secondary"
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          <AppIcon name="thumb" className="h-4 w-4" />
          {t("knowledge.ruleLike", "感兴趣后归档")}
        </button>
        <button
          type="button"
          onClick={() => {
            void patchRule({ archive_on_save: !rule.archive_on_save });
          }}
          disabled={saving}
          className={`af-btn px-3 py-1.5 text-sm ${
            rule.archive_on_save ? "af-btn-primary" : "af-btn-secondary"
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          <AppIcon name="bookmark" className="h-4 w-4" />
          {t("knowledge.ruleSave", "稍后再读后归档")}
        </button>
      </div>

      <p className="mt-3 text-sm text-slate-500">{ruleExplanation}</p>
      {message ? <p className="mt-3 text-sm text-slate-500">{message}</p> : null}
    </div>
  );
}
