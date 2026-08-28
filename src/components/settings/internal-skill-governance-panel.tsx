"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getInternalSkillGovernance,
  type InternalSkillGovernanceSnapshot,
  type InternalSkillRegistryEntry,
} from "@/lib/api";

const boundaryLabels: Record<string, string> = {
  local_only: "仅本地",
  local_app: "本机应用",
  external_optional: "外部可选",
  external_blocked: "外部阻断",
};

const externalApiLabels: Record<string, string> = {
  none: "无外部 API",
  optional_disabled: "外部可选未启用",
  blocked_until_review: "评测前阻断",
};

const secretLabels: Record<string, string> = {
  not_required: "无需密钥",
  required_for_optional_external_api: "可选外部 API 需密钥",
  blocked_until_review: "评测前阻断",
};

function compactList(values: string[]) {
  if (values.length === 0) return "无";
  return values.join("、");
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${
        ok
          ? "bg-emerald-100 text-emerald-700"
          : "bg-amber-100 text-amber-700"
      }`}
    >
      {label}
    </span>
  );
}

function SkillRow({ entry }: { entry: InternalSkillRegistryEntry }) {
  return (
    <div className="rounded-2xl border border-white/85 bg-white/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{entry.name}</p>
          <p className="mt-1 text-xs text-slate-500">
            {entry.skill_id} · v{entry.version} · {entry.owner}
          </p>
        </div>
        <StatusPill
          ok={entry.default_generation_enabled}
          label={entry.default_generation_enabled ? "默认链路" : "已阻断"}
        />
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-600 md:grid-cols-3">
        <p>数据边界：{boundaryLabels[entry.data_boundary] ?? entry.data_boundary}</p>
        <p>外部 API：{externalApiLabels[entry.external_api_status] ?? entry.external_api_status}</p>
        <p>密钥：{secretLabels[entry.secret_status] ?? entry.secret_status}</p>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">{entry.admission_reason}</p>
    </div>
  );
}

export function InternalSkillGovernancePanel() {
  const [snapshot, setSnapshot] = useState<InternalSkillGovernanceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const result = await getInternalSkillGovernance();
        if (active) setSnapshot(result);
      } catch {
        if (active) setError("读取内部 Skill 治理状态失败。");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const defaultEntries = useMemo(
    () => snapshot?.entries.filter((entry) => entry.default_generation_enabled) ?? [],
    [snapshot],
  );
  const blockedEntries = useMemo(
    () => snapshot?.entries.filter((entry) => !entry.default_generation_enabled) ?? [],
    [snapshot],
  );

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="af-kicker">内部 Skill 治理</p>
          <p className="mt-2 text-sm text-slate-500">
            默认生成链路、第三方测试包和数据边界状态。
          </p>
        </div>
        <StatusPill
          ok={snapshot?.diagnostics.default_chain_blocking_enforced ?? false}
          label={snapshot?.diagnostics.default_chain_blocking_enforced ? "准入已强制" : "准入未知"}
        />
      </div>

      {loading ? <p className="mt-4 text-sm text-slate-500">读取中...</p> : null}
      {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="生产 Skill" value={snapshot.summary.production_skills} />
            <Metric label="默认链路" value={snapshot.summary.default_chain_skills} />
            <Metric label="默认阻断" value={snapshot.summary.blocked_from_default_chain} />
            <Metric label="外部 API" value={snapshot.summary.external_api_skills} />
          </div>

          <div className="mt-4 rounded-2xl border border-white/85 bg-white/60 p-4">
            <p className="text-sm font-semibold text-slate-900">运行诊断</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusPill
                ok={snapshot.diagnostics.unreviewed_default_chain_count === 0}
                label={`未评测默认：${snapshot.diagnostics.unreviewed_default_chain_count}`}
              />
              <StatusPill
                ok={!snapshot.diagnostics.secret_values_exposed}
                label="密钥值不暴露"
              />
              <StatusPill
                ok={snapshot.diagnostics.data_egress_status_visible}
                label="数据边界可见"
              />
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 text-xs leading-5 text-slate-600 md:grid-cols-3">
              <p>外部 API：{compactList(snapshot.diagnostics.external_api_skill_ids)}</p>
              <p>密钥绑定：{compactList(snapshot.diagnostics.secret_bound_skill_ids)}</p>
              <p>
                数据出境：{snapshot.diagnostics.data_egress_modes.map((mode) => boundaryLabels[mode] ?? mode).join("、")}
              </p>
            </div>
            <p className="mt-3 text-xs text-slate-500">注册表版本：{snapshot.registry_version}</p>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-slate-900">默认生成链路</p>
              <div className="mt-3 space-y-3">
                {defaultEntries.map((entry) => (
                  <SkillRow key={entry.skill_id} entry={entry} />
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">阻断候选</p>
              <div className="mt-3 space-y-3">
                {blockedEntries.map((entry) => (
                  <SkillRow key={entry.skill_id} entry={entry} />
                ))}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/85 bg-white/60 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
