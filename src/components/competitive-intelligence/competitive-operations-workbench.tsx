"use client";

import { FormEvent, useEffect, useState } from "react";
import { isApiRequestError } from "@/lib/api/client";
import {
  createOperationEvidence, getOperationAuditBundle, getOperationAuditHandoff, getOperationEvidence, replayOperationProposal,
  type OperationEvidence, type OperationFormKind, type OperationLandscape,
} from "@/lib/api/product-strategy-operations";

const forms: Record<OperationFormKind, { label: string; fields: string; note: string }> = {
  capabilities: {
    label: "模型与技能登记",
    fields: "capability_key, model_id, model_revision, skill_digest, tool_key, allowed_parameters[], required_parameters[], allowed_hosts[], effect, prohibited_actions[], evaluation_digest?, observed_at, expires_at",
    note: "填写真实模型 ID 与版本；skill_digest 为实际文件 SHA-256。effect 为 read_only / local_write / external_write。主机必须精确列出，不接受通配符。时间须带时区。登记不证明模型已加载、签名可信或已独立评测。",
  },
  skills: {
    label: "技能完整性与来源台账",
    fields: "skill_key, vendor, model_id, model_revision, skill_revision, skill_digest, source_url, source_digest, signature_digest?, integrity_status, permission_scope[], prohibited_actions[], risk_level, evaluation_evidence_key?, observed_at, expires_at",
    note: "只记录模型/技能边界、来源摘要、签名摘要和风险；verified 必须提供签名摘要。不会安装、加载或授权第三方技能，供应商声明仍需独立安全评审。",
  },
  proposals: {
    label: "执行提案与权限预览",
    fields: "context_packet_key, expected_context_digest, capability_evidence_key, arguments{}, target_urls[], budget_usd, estimated_cost_usd?, idempotency_key, rollback_plan",
    note: "绑定已持久化上下文的当前摘要和能力登记键。参数仅允许短描述，禁止密钥。未知成本、越权目标、过期能力会阻断计划；提交只保存预览，不执行工具或付费调用。重试同一提案请保留幂等键。",
  },
  "dry-runs": {
    label: "工具 dry-run 回执",
    fields: "proposal_evidence_key, expected_proposal_digest, environment_fingerprint, operator_reference, simulated_effects[], failure_policy, idempotency_key",
    note: "dry-run 只绑定已有提案并生成无副作用回执；不调用工具、不写文件、不发送消息，也不代表具名执行批准。",
  },
  "rollback-rehearsals": {
    label: "回滚失败演练",
    fields: "proposal_evidence_key, expected_proposal_digest, environment_fingerprint, failure_code, recovery_action, idempotency_key",
    note: "只在内存快照上演练恢复路径，保留失败码和摘要；不证明外部服务回滚已验证。",
  },
  performance: {
    label: "性能与成本样本",
    fields: "environment_fingerprint, source_revision, workload, provenance, samples[{latency_ms, success, cost_usd?}], max_p95_ms, max_error_rate, max_total_cost_usd?, baseline_evidence_key?",
    note: "provenance 为 local_measurement / synthetic_fixture / external_unverified。至少 30 个本地实测样本才参与本地阈值通过判断；成本未知用 null，不写 0。基线必须匹配环境、工作负载和来源；提交的测量仍未独立核验，不能证明生产 SLA。",
  },
  feedback: {
    label: "任务反馈与相关性标注",
    fields: "task_key, artifact_revision_digest, consent_reference, deidentified, source_kind, task_author_reference, reviewer_reference, blinded, relevance_labels{evidence_key: 0..3}, feedback",
    note: "只提交已获授权、去标识化内容（deidentified 必须为 true）。source_kind 为 real_task_self_attested / synthetic_fixture；作者与评审引用必须不同。摘要绑定当前工件；自填身份、同意记录和盲评声明均不等于客户验收。",
  },
  "source-reviews": {
    label: "来源变更复核",
    fields: "source_url, observed_at, previous_content_digest?, content_digest, decision, reviewer_reference, rationale, claim_status",
    note: "仅记录最近 14 天观察；来源须为 HTTPS。decision 为 build / integrate / defer / explicitly_not_copy。claim_status 固定 vendor_claim_unverified；说明变更和判断依据，不会自动修改路线图或关闭 GitHub issue。",
  },
  "gate-reviews": {
    label: "证据续期与撤销门禁",
    fields: "gate_key, evidence_keys[], expected_digest, decision, reviewer_reference, rationale, expires_at, idempotency_key",
    note: "decision 为 renew / revoke / hold。续期必须绑定当前证据索引摘要，任一上游 HOLD 或过期都会阻断；事件不改变 baseline_hybrid 或 release-readiness。",
  },
};
const labels: Record<OperationEvidence["kind"], string> = {
  capability: "模型能力", skill_inventory: "技能完整性", execution_proposal: "执行提案", dry_run: "dry-run 回执", replay: "本地回放", rollback_rehearsal: "回滚演练", performance: "性能与成本", task_feedback: "任务反馈", source_review: "来源复核", evidence_gate_review: "证据门禁",
};

function describeError(error: unknown): string {
  if (isApiRequestError(error)) {
    let detail = "";
    try {
      const value = JSON.parse(error.body) as { detail?: unknown };
      if (typeof value.detail === "string") detail = value.detail;
      else if (Array.isArray(value.detail)) detail = value.detail.map((item: { loc?: unknown[]; msg?: string }) => `${item.loc?.join(".") ?? "字段"}: ${item.msg ?? "格式错误"}`).join("；");
      else if (value.detail && typeof value.detail === "object" && "message" in value.detail) detail = String(value.detail.message);
    } catch { /* Do not expose an unparsed proxy body. */ }
    return `请求失败（${error.status}）${detail ? `：${detail}` : "，请稍后重试。"} 草稿已保留。`;
  }
  return error instanceof Error ? `${error.message} 草稿已保留。` : "操作失败，草稿已保留。";
}

export function CompetitiveOperationsWorkbench() {
  const [snapshot, setSnapshot] = useState<OperationLandscape | null>(null);
  const [kind, setKind] = useState<OperationFormKind>("capabilities");
  const [drafts, setDrafts] = useState<Record<OperationFormKind, string>>({ capabilities: "{}", skills: "{}", proposals: "{}", "dry-runs": "{}", "rollback-rehearsals": "{}", performance: "{}", feedback: "{}", "source-reviews": "{}", "gate-reviews": "{}" });
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [lastEvidence, setLastEvidence] = useState<OperationEvidence | null>(null);

  useEffect(() => {
    let active = true;
    void getOperationEvidence().then((value) => { if (active) setSnapshot(value); })
      .catch((caught: unknown) => { if (active) setError(describeError(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function refresh() {
    setLoading(true); setError("");
    try { setSnapshot(await getOperationEvidence()); }
    catch (caught) { setError(describeError(caught)); }
    finally { setLoading(false); }
  }

  async function write(action: () => ReturnType<typeof createOperationEvidence>) {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await action();
      setLastEvidence(result.evidence);
      setSnapshot((current) => current ? { ...current, records: [result.evidence, ...current.records.filter((row) => row.evidence_key !== result.evidence.evidence_key)] } : current);
      setMessage(`${result.outcome === "existing" ? "已返回原有" : "已记录"}${labels[result.evidence.kind]}证据；未执行外部操作，验收仍为 HOLD。`);
      try { setSnapshot(await getOperationEvidence()); }
      catch { setError("记录已成功，但列表刷新失败。新记录和草稿已保留，请刷新列表，无需重复提交。"); }
    } catch (caught) { setError(describeError(caught)); }
    finally { setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmed) { setError("请先确认内容已授权且不含密钥或个人信息。"); return; }
    let payload: unknown;
    try { payload = JSON.parse(drafts[kind]); }
    catch { setError("JSON 格式错误，请检查引号和逗号。草稿已保留。"); return; }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      setError("请求必须是 JSON 对象，不能是数组或空值。草稿已保留。"); return;
    }
    await write(() => createOperationEvidence(kind, payload as Record<string, unknown>));
  }

  async function downloadAudit() {
    setBusy(true); setError(""); setMessage("");
    let objectUrl: string | null = null;
    try {
      const bundle = await getOperationAuditBundle();
      objectUrl = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = objectUrl; link.download = `anti-fomo-operation-audit-${bundle.bundle_digest.slice(0, 12)}.json`;
      link.click();
      setMessage(`已生成操作证据审计包（非独立审计结论）。缺失证据类型：${bundle.missing_evidence_kinds.length ? bundle.missing_evidence_kinds.map((value) => labels[value]).join("、") : "无；仍需独立审计及其他发布证据"}。`);
    } catch (caught) { setError(describeError(caught)); }
    finally { if (objectUrl) URL.revokeObjectURL(objectUrl); setBusy(false); }
  }

  async function downloadHandoff() {
    setBusy(true); setError(""); setMessage("");
    let objectUrl: string | null = null;
    try {
      const handoff = await getOperationAuditHandoff();
      objectUrl = URL.createObjectURL(new Blob([JSON.stringify(handoff, null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = objectUrl; link.download = `anti-fomo-audit-handoff-${handoff.handoff_digest.slice(0, 12)}.json`; link.click();
      setMessage(`已生成独立审计交接索引；当前 ${handoff.blockers.length} 项阻断，交接不等于审计通过或生产批准。`);
    } catch (caught) { setError(describeError(caught)); }
    finally { if (objectUrl) URL.revokeObjectURL(objectUrl); setBusy(false); }
  }

  return (
    <section className="min-w-0 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5" data-testid="competitive-operations-workbench">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl"><p className="af-kicker">Governed Operations · Development</p><h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">执行与评测证据工作台</h3><p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">登记实际证据、预览权限、重放计划和比较样本。这里没有外部工具执行能力；本地快照回滚不等于外部服务回滚，证据齐全也不自动通过发布。</p></div>
        <span className="af-chip af-chip-warning">HOLD · 生产未授权</span>
      </div>
      <div className="mt-4 flex flex-wrap gap-2"><button type="button" className="af-btn af-btn-secondary px-3 py-2 text-xs" disabled={loading || busy} onClick={() => void refresh()}>刷新操作证据</button><button type="button" className="af-btn af-btn-secondary px-3 py-2 text-xs" disabled={busy} onClick={() => void downloadAudit()}>下载操作审计包</button><button type="button" className="af-btn af-btn-secondary px-3 py-2 text-xs" disabled={busy} onClick={() => void downloadHandoff()}>下载独立审计交接索引</button></div>
      {loading ? <p role="status" className="mt-3 text-sm text-[var(--af-text-secondary)]">正在读取操作证据...</p> : null}
      {error ? <p role="alert" className="mt-3 rounded-xl bg-[var(--af-surface-muted)] p-3 text-sm text-[var(--af-text-primary)]">{error}</p> : null}
      {message ? <p role="status" className="mt-3 text-sm text-[var(--af-text-secondary)]">{message}</p> : null}
      <form onSubmit={submit} className="mt-4 min-w-0 rounded-[20px] bg-[var(--af-surface-muted)] p-4">
        <fieldset disabled={busy} className="min-w-0 space-y-3">
          <label className="block text-sm text-[var(--af-text-secondary)]">证据登记类型<select className="af-input mt-1 w-full" value={kind} onChange={(event) => { setKind(event.target.value as OperationFormKind); setConfirmed(false); setError(""); }}>{Object.entries(forms).map(([value, form]) => <option key={value} value={value}>{form.label}</option>)}</select></label>
          <p id="operation-schema-note" className="break-words text-xs leading-5 text-[var(--af-text-secondary)]">{forms[kind].note}</p>
          <details><summary className="cursor-pointer text-xs text-[var(--af-text-primary)]">请求字段说明（? 为可选）</summary><p className="mt-2 break-all font-mono text-xs leading-5 text-[var(--af-text-secondary)]">{forms[kind].fields}</p><p className="mt-2 text-xs text-[var(--af-text-secondary)]">摘要均为 64 位小写十六进制。服务端会校验必填字段、边界及现有证据绑定；不会自动填充或伪造样本。</p></details>
          <label className="block text-sm text-[var(--af-text-secondary)]">证据请求 JSON<textarea aria-describedby="operation-schema-note" className="af-input mt-1 min-h-56 w-full font-mono text-xs" spellCheck={false} value={drafts[kind]} onChange={(event) => { setDrafts((current) => ({ ...current, [kind]: event.target.value })); setConfirmed(false); }} /></label>
          <p className="text-xs text-[var(--af-text-tertiary)]">草稿在本页面内按类型保留，切换类型或刷新列表不会清空；离开或重新加载页面会丢失，未写入浏览器长期存储。</p>
          <label className="flex items-start gap-2 text-xs leading-5 text-[var(--af-text-secondary)]"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />我确认这是已授权、去标识化的证据，不含密钥或个人信息；提交不代表独立评审通过。</label>
          <button type="submit" disabled={busy || !confirmed} className="af-btn af-btn-primary px-4 py-2 text-xs">{busy ? "处理中..." : "明确提交并记录证据"}</button>
        </fieldset>
      </form>
      {lastEvidence ? <p className="mt-3 break-all text-xs text-[var(--af-text-secondary)]">最近写入：{lastEvidence.evidence_key} · SHA-256 {lastEvidence.digest}</p> : null}
      <p className="mt-4 text-xs text-[var(--af-text-tertiary)]">当前展示 {snapshot?.records.length ?? 0} 条，列表最多返回 {snapshot?.limit ?? 100} 条；审计包包含全部操作证据，不含 Office、视觉或独立验收结论。</p>
      <div className="mt-3 space-y-3">{snapshot?.records.map((row) => <article key={row.evidence_key} className="min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{labels[row.kind]} · {row.kind}</h4><span className="af-chip af-chip-warning">HOLD</span></div>
        <p className="mt-2 break-all text-xs text-[var(--af-text-secondary)]">键：{row.evidence_key}<br />SHA-256：{row.digest}</p>
        <details className="mt-3"><summary className="cursor-pointer text-xs text-[var(--af-text-primary)]">查看记录、权限和阻断原因</summary><pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-[var(--af-surface-muted)] p-3 text-xs text-[var(--af-text-secondary)]">{JSON.stringify(row.payload, null, 2)}</pre></details>
        {row.kind === "execution_proposal" ? <button type="button" disabled={busy} className="af-btn af-btn-secondary mt-3 px-3 py-2 text-xs" onClick={() => void write(() => replayOperationProposal(row.evidence_key))}>仅回放此提案（不执行）</button> : null}
      </article>)}</div>
    </section>
  );
}
