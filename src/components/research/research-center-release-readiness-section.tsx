"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getReleaseReadiness,
  type ReleaseReadinessGateStatus,
  type ReleaseReadinessSnapshot,
} from "@/lib/api";

type TranslationFn = (key: string, fallback: string) => string;

const statusClass: Record<ReleaseReadinessGateStatus, string> = {
  pass: "af-chip af-chip-success",
  watch: "af-chip af-chip-warning",
  blocked: "af-chip bg-rose-100 text-rose-700",
};

const statusText: Record<ReleaseReadinessGateStatus, string> = {
  pass: "pass",
  watch: "watch",
  blocked: "blocked",
};

const priorityClass: Record<string, string> = {
  high: "bg-rose-100 text-rose-700",
  medium: "af-chip af-chip-warning",
  low: "af-chip",
};

export function ResearchCenterReleaseReadinessSection({ t }: { t: TranslationFn }) {
  const [snapshot, setSnapshot] = useState<ReleaseReadinessSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const result = await getReleaseReadiness();
        if (active) setSnapshot(result);
      } catch {
        if (active) setError(t("research.releaseReadinessLoadFailed", "读取 release-readiness 失败。"));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [t]);

  const gateCounts = useMemo(() => {
    const counts: Record<ReleaseReadinessGateStatus, number> = {
      pass: 0,
      watch: 0,
      blocked: 0,
    };
    snapshot?.gates.forEach((gate) => {
      counts[gate.status] += 1;
    });
    return counts;
  }, [snapshot]);

  return (
    <section className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.releaseReadinessKicker", "Evidence-Closed Research")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t(
              "research.releaseReadinessDesc",
              "聚合系统健康、research diagnostics、低质量审计、独立复核和视觉门禁。",
            )}
          </p>
        </div>
        <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-semibold text-[var(--af-text-secondary)]">
          {snapshot ? `${snapshot.release_version} · ${snapshot.readiness_score}/100 · ${snapshot.overall_status}` : "..."}
        </div>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">
          {t("research.releaseReadinessLoading", "聚合 release readiness...")}
        </p>
      ) : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-3">
            {snapshot.summary_lines.map((line) => (
              <p
                key={line}
                className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]"
              >
                {line}
              </p>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="Pass" value={gateCounts.pass} />
            <Metric label="Watch" value={gateCounts.watch} />
            <Metric label="Blocked" value={gateCounts.blocked} />
            <Metric label="Actions" value={snapshot.next_actions.length} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {snapshot.gates.map((gate) => (
                <article
                  key={gate.key}
                  className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{gate.label}</p>
                      <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{gate.summary}</p>
                    </div>
                    <span className={statusClass[gate.status]}>{statusText[gate.status]}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    <p>
                      <span className="font-semibold text-[var(--af-text-primary)]">{gate.score}/100</span> · {gate.observed}
                    </p>
                    <p>{gate.target}</p>
                  </div>
                  <div className="mt-3 space-y-2">
                    {gate.evidence.slice(0, 3).map((item) => (
                      <div key={`${gate.key}-${item.label}-${item.source}`} className="rounded-[16px] bg-[var(--af-surface-muted)] p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={statusClass[item.status]}>{item.status}</span>
                          <p className="text-xs font-semibold text-[var(--af-text-primary)]">{item.label}</p>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{item.summary}</p>
                        {item.source ? (
                          <p className="mt-1 break-all text-[11px] text-[var(--af-text-tertiary)]">{item.source}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.releaseReadinessActionsTitle", "Release blockers / next actions")}
              </p>
              <div className="mt-3 space-y-2">
                {snapshot.next_actions.slice(0, 6).map((action) => (
                  <div
                    key={`${action.gate_key}-${action.owner}-${action.action}`}
                    className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${priorityClass[action.priority] || "af-chip"}`}>
                        {action.priority}
                      </span>
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{action.action}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      {action.gate_label || action.gate_key} · {action.owner} · {action.reason}
                    </p>
                  </div>
                ))}
                {!snapshot.next_actions.length ? (
                  <p className="rounded-[16px] bg-[var(--af-surface-muted)] p-3 text-xs text-[var(--af-text-tertiary)]">
                    {t("research.releaseReadinessNoActions", "当前聚合门禁没有待处理动作。")}
                  </p>
                ) : null}
              </div>

              {snapshot.operator_commands.length ? (
                <div className="mt-4">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                    {t("research.releaseReadinessCommandsTitle", "Operator commands")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {snapshot.operator_commands.slice(0, 7).map((command) => (
                      <div
                        key={`${command.gate_key}-${command.label}`}
                        className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="af-chip">{command.gate_label || command.gate_key}</span>
                          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{command.label}</p>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{command.purpose}</p>
                        <code className="mt-2 block whitespace-pre-wrap break-words rounded-[12px] bg-[var(--af-surface)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-secondary)]">
                          {command.command}
                        </code>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {snapshot.artifacts.length ? (
                <div className="mt-4">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                    {t("research.releaseReadinessArtifactsTitle", "Release artifacts")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {snapshot.artifacts.slice(0, 8).map((artifact) => (
                      <div
                        key={`${artifact.gate_key}-${artifact.path}`}
                        className="rounded-[16px] bg-[var(--af-surface-muted)] p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={statusClass[artifact.status]}>{artifact.status}</span>
                          <span className={artifact.exists ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
                            {artifact.exists ? "exists" : "missing"}
                          </span>
                          <p className="text-xs font-semibold text-[var(--af-text-primary)]">{artifact.label}</p>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{artifact.summary}</p>
                        <p className="mt-1 break-all text-[11px] text-[var(--af-text-tertiary)]">{artifact.path}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
