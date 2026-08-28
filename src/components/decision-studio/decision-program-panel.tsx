"use client";

import { useCallback, useEffect, useState } from "react";
import {
  freezeDecisionReleaseCandidate,
  getDecisionProgramOverview,
  getDecisionVerticalPacks,
  previewDecisionReleaseCandidate,
  seedDecisionVerticalPacks,
} from "@/lib/api/decision-program";
import type {
  DecisionProgramOverview,
  DecisionReleaseCandidate,
  DecisionReleaseCandidatePreview,
  DecisionVerticalPack,
} from "@/lib/api/type-contracts/decision-program";


function statusClass(status: string): string {
  if (["pass", "active"].includes(status)) return "text-[var(--af-success)] border-[color-mix(in_srgb,var(--af-success)_38%,var(--af-border-subtle))]";
  if (["blocked", "validation_pending"].includes(status)) return "text-[var(--af-danger)] border-[color-mix(in_srgb,var(--af-danger)_38%,var(--af-border-subtle))]";
  return "text-[var(--af-warning)] border-[color-mix(in_srgb,var(--af-warning)_38%,var(--af-border-subtle))]";
}

function StatusPill({ status, label }: { status: string; label?: string }) {
  return <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(status)}`}>{label ?? status}</span>;
}

function shortHash(value: string): string {
  return value ? `${value.slice(0, 10)}...${value.slice(-6)}` : "-";
}

function evidenceSummary(evidence: Record<string, unknown>): string {
  const rows = Object.entries(evidence)
    .filter(([, value]) => typeof value === "number" || typeof value === "string")
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`);
  return rows.join(" · ") || "等待运行证据";
}

export function DecisionProgramPanel() {
  const [overview, setOverview] = useState<DecisionProgramOverview | null>(null);
  const [packs, setPacks] = useState<DecisionVerticalPack[]>([]);
  const [candidate, setCandidate] = useState<DecisionReleaseCandidate | null>(null);
  const [candidatePreview, setCandidatePreview] = useState<DecisionReleaseCandidatePreview | null>(null);
  const [previewBuildId, setPreviewBuildId] = useState("");
  const [buildId, setBuildId] = useState("");
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setWorking("刷新版本证据");
    setError("");
    try {
      const [nextOverview, nextPacks] = await Promise.all([
        getDecisionProgramOverview(),
        getDecisionVerticalPacks(),
      ]);
      setOverview(nextOverview);
      setPacks(nextPacks);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setWorking("");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleFreeze() {
    if (!buildId.trim() || previewBuildId !== buildId.trim() || !candidatePreview) return;
    setWorking("冻结 2.0.7 候选");
    setError("");
    try {
      const result = await freezeDecisionReleaseCandidate({
        version: "2.0.7",
        manifest: {
          build_id: buildId.trim(),
          source: "decision-studio-ui",
          target_version: "2.2.0-development",
        },
        validation_run_ids: [],
        external_attestations: {},
      });
      setCandidate(result);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setWorking("");
    }
  }

  async function handlePreviewCandidate() {
    if (!buildId.trim()) return;
    setWorking("预检 2.0.7 候选");
    setError("");
    try {
      const result = await previewDecisionReleaseCandidate({
        version: "2.0.7",
        manifest: {
          build_id: buildId.trim(),
          source: "decision-studio-ui",
          target_version: "2.2.0-development",
        },
        validation_run_ids: [],
        external_attestations: {},
      });
      setCandidatePreview(result);
      setPreviewBuildId(buildId.trim());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setWorking("");
    }
  }

  async function handleSeedPacks() {
    setWorking("校验行业包");
    setError("");
    try {
      setPacks(await seedDecisionVerticalPacks());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setWorking("");
    }
  }

  return (
    <div className="space-y-4">
      <section className="af-glass rounded-lg p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">2.0.7 - 2.2.0 版本收口</h2>
              {overview ? <StatusPill status={overview.overall_acceptance_status} label={`${overview.engineering_status} · ${overview.overall_acceptance_status}`} /> : null}
            </div>
            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{overview?.version ?? "2.2.0-development"}</p>
          </div>
          <button className="af-btn af-btn-secondary px-3 py-1.5 text-xs" onClick={() => void refresh()} disabled={Boolean(working)}>
            刷新证据
          </button>
        </div>
        {working ? <p className="mt-2 text-xs text-[var(--af-info)]">{working}...</p> : null}
        {error ? <p className="mt-2 break-words text-xs text-[var(--af-danger)]">{error}</p> : null}
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {overview?.milestones.map((milestone) => (
          <article key={milestone.version} className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <strong className="text-sm text-[var(--af-text-primary)]">{milestone.version}</strong>
                <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{milestone.label}</p>
              </div>
              <StatusPill status={milestone.acceptance_status} />
            </div>
            <p className="mt-3 break-words text-[11px] leading-5 text-[var(--af-text-tertiary)]">{evidenceSummary(milestone.evidence)}</p>
            {milestone.blockers[0] ? <p className="mt-2 border-t border-[var(--af-border-subtle)] pt-2 text-[11px] leading-5 text-[var(--af-warning)]">{milestone.blockers[0]}</p> : null}
          </article>
        ))}
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <section className="af-glass rounded-lg p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">Release Candidate</h2>
            {candidate ? <StatusPill status={candidate.acceptance_status} label={candidate.status} /> : null}
          </div>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              className="af-input min-w-0 flex-1"
              value={buildId}
              onChange={(event) => {
                setBuildId(event.target.value);
                setCandidatePreview(null);
                setPreviewBuildId("");
              }}
              placeholder="Git commit / build id"
            />
            <button className="af-btn af-btn-secondary shrink-0" onClick={() => void handlePreviewCandidate()} disabled={Boolean(working) || !buildId.trim()}>
              预检 digest
            </button>
            <button className="af-btn af-btn-primary shrink-0" onClick={() => void handleFreeze()} disabled={Boolean(working) || previewBuildId !== buildId.trim() || !candidatePreview}>
              冻结候选
            </button>
          </div>
          {candidatePreview && !candidate ? (
            <div className="mt-4 rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] p-3">
              <p className="font-mono text-[11px] text-[var(--af-text-secondary)]">{shortHash(candidatePreview.build_digest)}</p>
              <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">预检未落库 · 绑定 {candidatePreview.validation_run_ids.length} 个验证运行</p>
              {candidatePreview.blockers.slice(0, 3).map((blocker) => <p key={blocker} className="mt-1 text-[11px] leading-5 text-[var(--af-warning)]">{blocker}</p>)}
            </div>
          ) : null}
          {candidate ? (
            <div className="mt-4 rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] p-3">
              <p className="font-mono text-[11px] text-[var(--af-text-secondary)]">{shortHash(candidate.build_digest)}</p>
              <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">绑定 {candidate.validation_run_ids.length} 个验证运行</p>
              {candidate.blockers.slice(0, 3).map((blocker) => <p key={blocker} className="mt-1 text-[11px] leading-5 text-[var(--af-warning)]">{blocker}</p>)}
            </div>
          ) : null}
        </section>

        <section className="af-glass rounded-lg p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">行业证据包</h2>
            <button className="af-btn af-btn-secondary px-3 py-1.5 text-xs" onClick={() => void handleSeedPacks()} disabled={Boolean(working)}>
              校验内置包
            </button>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-3">
            {packs.map((pack) => (
              <article key={pack.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <strong className="text-xs text-[var(--af-text-primary)]">{pack.sector}</strong>
                  <StatusPill status={pack.status} />
                </div>
                <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{pack.title}</p>
                <p className="mt-2 font-mono text-[10px] text-[var(--af-text-tertiary)]">{shortHash(pack.content_hash)}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
