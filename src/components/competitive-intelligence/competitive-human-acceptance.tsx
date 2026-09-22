"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createHumanAcceptanceEvent,
  getHumanAcceptanceEvents,
  getOfficeEvidenceReceipts,
  getReleaseEvidenceBridge,
  getVisualEvidenceRevisions,
} from "@/lib/api/competitive-intelligence";
import type {
  ApiProductStrategyHumanAcceptanceDecision,
  ApiProductStrategyHumanAcceptanceEvent,
  ApiProductStrategyHumanAcceptanceLandscape,
  ApiProductStrategyOfficeEvidenceLandscape,
  ApiProductStrategyOfficeEvidenceReceipt,
  ApiProductStrategyReleaseEvidenceBridge,
  ApiProductStrategyVisualEvidenceLandscape,
  ApiProductStrategyVisualEvidenceRevision,
} from "@/lib/api/type-contracts/competitive-intelligence";

const decisionLabels: Record<ApiProductStrategyHumanAcceptanceDecision, string> = {
  approve: "意见：通过",
  reject: "意见：拒绝",
  request_revision: "意见：要求修订",
};

function shortDigest(value: string | null | undefined): string {
  if (!value) return "未生成";
  return value.length > 18 ? `${value.slice(0, 12)}…${value.slice(-4)}` : value;
}

function refreshKey(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function CompetitiveHumanAcceptance() {
  const [receipts, setReceipts] = useState<ApiProductStrategyOfficeEvidenceLandscape | null>(null);
  const [visuals, setVisuals] = useState<ApiProductStrategyVisualEvidenceLandscape | null>(null);
  const [events, setEvents] = useState<ApiProductStrategyHumanAcceptanceLandscape | null>(null);
  const [receiptKey, setReceiptKey] = useState("");
  const [selectedVisuals, setSelectedVisuals] = useState<string[]>([]);
  const [reviewer, setReviewer] = useState("");
  const [author, setAuthor] = useState("");
  const [decision, setDecision] = useState<ApiProductStrategyHumanAcceptanceDecision>("approve");
  const [scope, setScope] = useState("桌面、移动视口和 Office 交付物的可读性与版式检查");
  const [rationale, setRationale] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [bridge, setBridge] = useState<ApiProductStrategyReleaseEvidenceBridge | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getOfficeEvidenceReceipts(), getVisualEvidenceRevisions(), getHumanAcceptanceEvents()])
      .then(([office, visual, human]) => {
        if (!active) return;
        setReceipts(office);
        setVisuals(visual);
        setEvents(human);
        setReceiptKey((current) => current || office.receipts[0]?.receipt_key || "");
      })
      .catch(() => { if (active) setError("无法读取人工验收证据；请确认 Office、视觉和验收路由已加载。"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const receipt = useMemo< ApiProductStrategyOfficeEvidenceReceipt | null>(
    () => receipts?.receipts.find((item) => item.receipt_key === receiptKey) ?? null,
    [receiptKey, receipts],
  );
  const availableVisuals = useMemo<ApiProductStrategyVisualEvidenceRevision[]>(
    () => (visuals?.revisions ?? []).filter((item) => item.office_receipt_key === receiptKey),
    [receiptKey, visuals],
  );
  const latestEvent = useMemo<ApiProductStrategyHumanAcceptanceEvent | null>(
    () => (events?.events ?? []).find((item) => item.artifact_key === receipt?.artifact_key) ?? null,
    [events, receipt],
  );

  useEffect(() => {
    setSelectedVisuals((current) => current.filter((digest) => availableVisuals.some((item) => item.revision_digest === digest)));
  }, [availableVisuals]);

  async function refresh() {
    const [office, visual, human] = await Promise.all([getOfficeEvidenceReceipts(), getVisualEvidenceRevisions(), getHumanAcceptanceEvents()]);
    setReceipts(office); setVisuals(visual); setEvents(human);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!receipt || !reviewer.trim() || !author.trim() || !rationale.trim() || !selectedVisuals.length) {
      setError("请先选择当前 Office 收据和至少一条视觉修订，并填写具名复核人、制作者及理由。");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await createHumanAcceptanceEvent({
        idempotency_key: refreshKey("human-review"),
        office_receipt_key: receipt.receipt_key,
        expected_office_receipt_digest: receipt.receipt_digest,
        expected_artifact_revision_digest: receipt.artifact_revision_digest,
        visual_revision_digests: selectedVisuals,
        reviewer_identity: reviewer.trim(),
        author_identity: author.trim(),
        decision,
        review_scope: scope.trim(),
        rationale: rationale.trim(),
        previous_event_digest: latestEvent?.event_digest ?? null,
      });
      await refresh();
      setMessage(`${result.deduplicated ? "已返回原有" : "已记录"}具名意见；身份仍是自述，验收继续 HOLD。`);
      setRationale("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "人工验收记录失败；没有改变发布状态。请刷新摘要后重试。");
    } finally { setBusy(false); }
  }

  async function loadBridge() {
    if (!receipt) return;
    setBusy(true); setError(""); setMessage("");
    try {
      setBridge(await getReleaseEvidenceBridge(receipt.artifact_key));
      setMessage("已生成只读发布证据桥接；阻断项和 baseline_hybrid 状态保持不变。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "发布证据桥接读取失败；发布状态未改变。");
    } finally { setBusy(false); }
  }

  return (
    <section className="min-w-0 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]" data-testid="competitive-human-acceptance">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl"><p className="af-kicker">2.10.7–2.10.8 Acceptance Bridge</p><h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">具名人工验收与发布证据桥接</h3><p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">记录独立于制作者的具名意见，并把当前 Office、视觉和上游 release-readiness 摘要关联起来。姓名只证明提交者自述身份，不会自动转为客户验收或生产授权。</p></div>
        <div className="flex flex-wrap gap-2"><span className="af-chip bg-rose-100 text-rose-700">HOLD · blocked</span><span className="af-chip bg-slate-100 text-slate-700">只读发布桥</span></div>
      </div>
      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取收据、视觉修订和人工意见...</p> : null}
      {error ? <p role="alert" className="mt-4 rounded-[16px] bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700">{error}</p> : null}
      {message ? <p role="status" className="mt-4 rounded-[16px] bg-emerald-50 px-3 py-2 text-sm leading-6 text-emerald-800">{message}</p> : null}

      <form className="mt-4 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4" onSubmit={submit}>
        <fieldset disabled={busy} className="space-y-3">
          <label className="block text-xs font-medium text-[var(--af-text-secondary)]">当前 Office 收据<select className="af-input mt-1 w-full" value={receiptKey} onChange={(event) => setReceiptKey(event.target.value)}>{!(receipts?.receipts.length) ? <option value="">暂无收据</option> : null}{receipts?.receipts.map((item) => <option key={item.receipt_key} value={item.receipt_key}>{item.file_name} · r{item.artifact_revision} · {shortDigest(item.receipt_digest)}</option>)}</select></label>
          <fieldset className="space-y-2"><legend className="text-xs font-medium text-[var(--af-text-secondary)]">绑定视觉修订（至少一条）</legend>{availableVisuals.length ? availableVisuals.map((item) => <label key={item.revision_digest} className="flex min-w-0 items-start gap-2 text-xs text-[var(--af-text-secondary)]"><input type="checkbox" checked={selectedVisuals.includes(item.revision_digest)} onChange={(event) => setSelectedVisuals((current) => event.target.checked ? [...current, item.revision_digest] : current.filter((value) => value !== item.revision_digest))} /><span className="min-w-0 break-all">{item.surface_key} · r{item.revision} · {item.capture_kind} · {shortDigest(item.revision_digest)}</span></label>) : <p className="text-xs text-[var(--af-text-tertiary)]">当前收据尚无视觉修订，不能提交人工意见。</p>}</fieldset>
          <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs text-[var(--af-text-secondary)]">具名复核人<input className="af-input mt-1 w-full" value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={160} required /></label><label className="text-xs text-[var(--af-text-secondary)]">制作者<input className="af-input mt-1 w-full" value={author} onChange={(event) => setAuthor(event.target.value)} maxLength={160} required /></label></div>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,220px)_1fr]"><label className="text-xs text-[var(--af-text-secondary)]">复核意见<select className="af-input mt-1 w-full" value={decision} onChange={(event) => setDecision(event.target.value as ApiProductStrategyHumanAcceptanceDecision)}>{Object.entries(decisionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-xs text-[var(--af-text-secondary)]">复核范围<input className="af-input mt-1 w-full" value={scope} onChange={(event) => setScope(event.target.value)} maxLength={2000} required /></label></div>
          <label className="block text-xs text-[var(--af-text-secondary)]">理由与问题<textarea className="af-input mt-1 min-h-24 w-full" value={rationale} onChange={(event) => setRationale(event.target.value)} maxLength={10000} required /></label>
          <p className="text-xs leading-5 text-[var(--af-text-tertiary)]">服务端会阻止相同身份、旧收据、旧视觉修订和并发覆盖。提交只追加不可变事件；`approve` 也不会解除人工、客户、生产授权等阻断项。</p>
          <button type="submit" disabled={busy || !receipt || !selectedVisuals.length} className="af-btn af-btn-primary px-4 py-2 text-xs">{busy ? "记录中..." : "追加具名复核事件"}</button>
        </fieldset>
      </form>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-[var(--af-text-tertiary)]">已记录 {events?.event_count ?? 0} 条意见 · 当前身份状态：self_attested</p><button type="button" className="af-btn af-btn-secondary px-3 py-2 text-xs" disabled={busy || !receipt} onClick={() => void loadBridge()}>生成只读发布证据桥</button></div>
      {events?.events.map((item) => <article key={item.event_key} className="mt-3 min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{item.decision} · 序列 {item.sequence}</h4><span className="af-chip af-chip-warning">自述身份 · HOLD</span></div><p className="mt-2 break-all text-xs text-[var(--af-text-secondary)]">复核人：{item.reviewer_identity} · 制作者：{item.author_identity}<br />事件摘要：{item.event_digest}</p><p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-[var(--af-text-secondary)]">{item.rationale}</p></article>)}
      {bridge ? <div className="mt-4 min-w-0 rounded-[18px] border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-950"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">2.10.8 只读桥接摘要</p><code title={bridge.bridge_digest}>{shortDigest(bridge.bridge_digest)}</code></div><p className="mt-2">收据 {bridge.office_receipts.length} 条 · 视觉修订 {bridge.visual_revisions.length} 条 · 人工事件 {bridge.human_events.length} 条</p><p className="mt-2 font-semibold">阻断项</p><ul className="mt-1 list-disc space-y-1 pl-5">{bridge.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul><p className="mt-2">此桥接为只读索引，不改变 release-readiness、`baseline_hybrid` 或生产授权。</p></div> : null}
    </section>
  );
}
