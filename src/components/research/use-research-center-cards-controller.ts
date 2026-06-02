"use client";

import { useEffect, useState } from "react";
import { listKnowledgeEntries } from "@/lib/api";
import {
  normalizeResearchEntry,
  sortEntries,
  type ResearchCenterEntry,
} from "@/components/research/research-center-utils";

type TranslationFn = (key: string, fallback: string) => string;

export function useResearchCenterCardsController({
  t,
  focusOnly,
  query,
}: {
  t: TranslationFn;
  focusOnly: boolean;
  query: string;
}) {
  const [reports, setReports] = useState<ResearchCenterEntry[]>([]);
  const [actions, setActions] = useState<ResearchCenterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadResearchCards = async () => {
    const [reportRes, actionRes] = await Promise.all([
      listKnowledgeEntries(40, {
        sourceDomain: "research.report",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
      listKnowledgeEntries(60, {
        sourceDomain: "research.action_card",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
    ]);
    setReports(sortEntries((reportRes.items || []).map(normalizeResearchEntry)));
    setActions(sortEntries((actionRes.items || []).map(normalizeResearchEntry)));
  };

  useEffect(() => {
    let active = true;
    Promise.all([
      listKnowledgeEntries(40, {
        sourceDomain: "research.report",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
      listKnowledgeEntries(60, {
        sourceDomain: "research.action_card",
        query: query || undefined,
        focusReferenceOnly: focusOnly,
      }),
    ])
      .then(([reportRes, actionRes]) => {
        if (!active) return;
        setReports(sortEntries((reportRes.items || []).map(normalizeResearchEntry)));
        setActions(sortEntries((actionRes.items || []).map(normalizeResearchEntry)));
        setError("");
      })
      .catch(() => {
        if (!active) return;
        setReports([]);
        setActions([]);
        setError(t("research.centerLoadFailed", "商机情报中心加载失败，请稍后重试"));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [focusOnly, query, t]);

  return {
    reports,
    actions,
    loading,
    error,
    refreshResearchCards: loadResearchCards,
  };
}
