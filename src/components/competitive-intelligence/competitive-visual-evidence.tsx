"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { createVisualEvidenceRevision, getOfficeEvidenceReceipts, getResponsiveEvidence, getVisualEvidenceRevisions } from "@/lib/api/competitive-intelligence";
import { isApiRequestError } from "@/lib/api/client";
import type {
  ApiProductStrategyOfficeEvidenceReceipt,
  ApiProductStrategyVisualCaptureKind,
  ApiProductStrategyVisualChecklist,
  ApiProductStrategyVisualCheckStatus,
  ApiProductStrategyVisualEvidenceLandscape,
  ApiProductStrategyVisualEvidenceRevision,
  ApiProductStrategyResponsiveEvidence,
} from "@/lib/api/type-contracts/competitive-intelligence";

const checklistLabels = {
  clipping: "截断与裁切",
  overlap: "文字与元素重叠",
  legibility: "文字清晰可读",
  assets: "图片与图表完整",
  pagination: "分页与页面连续性",
} as const;
const checkKeys = Object.keys(checklistLabels) as (keyof ApiProductStrategyVisualChecklist)[];
const statusLabels: Record<ApiProductStrategyVisualCheckStatus, string> = { unknown: "未确认", pass: "通过", fail: "需修订" };
const captureLabels: Record<ApiProductStrategyVisualCaptureKind, string> = {
  office_page: "Office 渲染页",
  desktop_browser: "桌面浏览器截图",
  mobile_viewport: "移动视口截图（不等于真机）",
};

function emptyChecklist(): ApiProductStrategyVisualChecklist {
  return Object.fromEntries(checkKeys.map((key) => [key, { status: "unknown", note: "" }])) as ApiProductStrategyVisualChecklist;
}

function shortDigest(value: string | null): string {
  return value ? `${value.slice(0, 12)}…${value.slice(-6)}` : "无（首个修订）";
}

function displayValue(value: unknown): string {
  return value === null || value === undefined ? "—" : typeof value === "string" ? value : JSON.stringify(value);
}

function errorMessage(caught: unknown): string {
  if (isApiRequestError(caught)) {
    let detail = "";
    try {
      const body = JSON.parse(caught.body) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item: { msg?: string }) => item.msg ?? "字段不符合要求").join("；");
    } catch { /* Preserve a readable status even for a non-JSON proxy response. */ }
    if (caught.status === 409) return `绑定收据或修订基线已变化，请刷新并核对最新摘要后重试。表单内容已保留。${detail ? ` ${detail}` : ""}`;
    return `证据请求失败（${caught.status}），表单内容已保留。${detail ? ` ${detail}` : "请稍后重试。"}`;
  }
  return caught instanceof Error ? caught.message : "无法处理视觉证据，请重试。";
}

function imageBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("无法读取 PNG，请重新选择文件。"));
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const separator = result.indexOf(",");
      if (separator < 0) reject(new Error("PNG 编码失败，请重新选择文件。"));
      else resolve(result.slice(separator + 1));
    };
    reader.readAsDataURL(file);
  });
}

export function CompetitiveVisualEvidence() {
  const [snapshot, setSnapshot] = useState<ApiProductStrategyVisualEvidenceLandscape | null>(null);
  const [responsive, setResponsive] = useState<ApiProductStrategyResponsiveEvidence | null>(null);
  const [receipts, setReceipts] = useState<ApiProductStrategyOfficeEvidenceReceipt[]>([]);
  const [receiptKey, setReceiptKey] = useState("");
  const [surfaceKey, setSurfaceKey] = useState("delivery-review");
  const [captureKind, setCaptureKind] = useState<ApiProductStrategyVisualCaptureKind>("desktop_browser");
  const [sourceVersion, setSourceVersion] = useState("2.10.6-local");
  const [file, setFile] = useState<File | null>(null);
  const [width, setWidth] = useState("");
  const [height, setHeight] = useState("");
  const [scale, setScale] = useState("1");
  const [page, setPage] = useState("1");
  const [checklist, setChecklist] = useState(emptyChecklist);
  const [notes, setNotes] = useState("");
  const [previousDigest, setPreviousDigest] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.all([getVisualEvidenceRevisions(), getOfficeEvidenceReceipts(), getResponsiveEvidence()])
      .then(([visual, office, responsiveSummary]) => {
        if (!active) return;
        setSnapshot(visual);
        setResponsive(responsiveSummary);
        setReceipts(office.receipts);
        setReceiptKey((current) => current || office.receipts[0]?.receipt_key || "");
      })
      .catch((caught: unknown) => { if (active) setError(errorMessage(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const selectedReceipt = receipts.find((receipt) => receipt.receipt_key === receiptKey);
  const latestRevision = useMemo(() => (snapshot?.revisions ?? [])
    .filter((revision) => revision.office_receipt_key === receiptKey && revision.surface_key === surfaceKey.trim() && revision.capture_kind === captureKind)
    .reduce<ApiProductStrategyVisualEvidenceRevision | null>((latest, current) => !latest || current.revision > latest.revision ? current : latest, null),
  [snapshot, receiptKey, surfaceKey, captureKind]);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [visual, office, responsiveSummary] = await Promise.all([getVisualEvidenceRevisions(), getOfficeEvidenceReceipts(), getResponsiveEvidence()]);
      setSnapshot(visual);
      setResponsive(responsiveSummary);
      setReceipts(office.receipts);
      setReceiptKey((current) => current || office.receipts[0]?.receipt_key || "");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!selectedReceipt || !file) {
      setError("请选择现有 Office 收据和 PNG 文件后再提交。");
      return;
    }
    if (!/\.png$/i.test(file.name) || (file.type && file.type !== "image/png") || !file.size || file.size > 8 * 1024 * 1024) {
      setError("仅支持非空 PNG 文件，大小不得超过 8 MB。文件内容将由服务端再次校验。");
      return;
    }
    if (latestRevision && previousDigest.trim() !== latestRevision.revision_digest) {
      setError("当前页面已有更新的修订，请核对差异并使用最新修订为基线；表单内容已保留。");
      return;
    }
    setSubmitting(true);
    try {
      const result = await createVisualEvidenceRevision({
        office_receipt_key: selectedReceipt.receipt_key,
        expected_office_receipt_digest: selectedReceipt.receipt_digest,
        surface_key: surfaceKey.trim(),
        capture_kind: captureKind,
        source_version: sourceVersion.trim(),
        file_name: file.name,
        image_base64: await imageBase64(file),
        ...(captureKind === "office_page"
          ? { office_page_number: Number(page) }
          : { viewport: { width: Number(width), height: Number(height), device_scale_factor: Number(scale) } }),
        checklist,
        notes,
        previous_revision_digest: previousDigest.trim() || null,
      });
      setPreviousDigest(result.revision.revision_digest);
      setSnapshot((current) => {
        const revisions = [result.revision, ...(current?.revisions ?? []).filter((revision) => revision.revision_key !== result.revision.revision_key)];
        return {
          visual_evidence_version: "2.10.6", revisions, revision_count: revisions.length,
          needs_revision_count: revisions.filter((revision) => revision.review_status === "needs_revision").length,
          acceptance_status: "hold", blocking_status: "blocked", note: current?.note ?? "视觉记录不替代具名人工验收。",
        };
      });
      setMessage(result.deduplicated ? "相同证据已存在，已返回原有修订。验收仍为 HOLD。" : "视觉证据和修订差异已记录。验收仍为 HOLD，等待具名人工复核。");
      try {
        setSnapshot(await getVisualEvidenceRevisions());
      } catch {
        setError("提交已成功，但列表刷新失败。已保留新修订及表单，请点击刷新证据，无需重复上传。");
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]" data-testid="competitive-visual-evidence">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">2.10.6 Visual Evidence</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">视觉验收证据与修订差异</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">将 PNG、页面或视口信息及五项检查绑定到现有 Office 收据。每次修订保留上一版本摘要和字段差异；上传记录和自填检查结果不能替代具名人工验收。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="af-chip bg-rose-100 text-rose-700">HOLD · blocked</span>
          <button type="button" className="af-btn af-btn-secondary px-3 py-2 text-xs" onClick={() => void refresh()} disabled={loading || submitting}>刷新证据</button>
        </div>
      </div>
      {loading ? <p role="status" className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取视觉证据和 Office 收据...</p> : null}
      {error ? <p role="alert" className="mt-4 rounded-[16px] bg-rose-50 p-3 text-sm text-rose-800">{error}</p> : null}
      {message ? <p role="status" className="mt-4 rounded-[16px] bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p> : null}
      <p className="mt-4 text-xs text-[var(--af-text-secondary)]">已记录 {snapshot?.revision_count ?? 0} 个修订 · 待修订记录 {snapshot?.needs_revision_count ?? 0} 条 · 证据层次：本地记录、检查者身份未核实 · 生产未授权</p>
      {responsive ? <div className="mt-3 rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3 text-xs leading-5 text-[var(--af-text-secondary)]"><strong className="text-[var(--af-text-primary)]">2.11.3 响应式证据摘要：</strong>桌面 {responsive.desktop_browser_count} · 移动视口 {responsive.mobile_viewport_count} · Office 页 {responsive.office_page_count} · 物理真机：否 · 生产性能基准：否。{responsive.blockers.length ? ` 阻断：${responsive.blockers.join("、")}` : ""}</div> : null}
      <form onSubmit={submit} className="mt-4 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <fieldset disabled={submitting} className="min-w-0 space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs text-[var(--af-text-secondary)]">绑定 Office 收据
              <select className="af-input mt-1 w-full" value={receiptKey} onChange={(event) => { setReceiptKey(event.target.value); setPreviousDigest(""); }} disabled={!receipts.length}>
                {!receipts.length ? <option value="">请先在上方生成 Office 证据收据，再刷新</option> : null}
                {receipts.map((receipt) => <option key={receipt.receipt_key} value={receipt.receipt_key}>{receipt.file_name} · 工件 r{receipt.artifact_revision} · {shortDigest(receipt.receipt_digest)}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--af-text-secondary)]">证据类型
              <select className="af-input mt-1 w-full" value={captureKind} onChange={(event) => { setCaptureKind(event.target.value as ApiProductStrategyVisualCaptureKind); setPreviousDigest(""); }}>
                {Object.entries(captureLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>
            <label className="text-xs text-[var(--af-text-secondary)]">页面标识（同一页面修订时保持一致）
              <input className="af-input mt-1 w-full" value={surfaceKey} onChange={(event) => { setSurfaceKey(event.target.value); setPreviousDigest(""); }} required maxLength={120} />
            </label>
            <label className="text-xs text-[var(--af-text-secondary)]">截图来源版本
              <input className="af-input mt-1 w-full" value={sourceVersion} onChange={(event) => setSourceVersion(event.target.value)} required maxLength={120} />
            </label>
          </div>
          <label className="block text-xs text-[var(--af-text-secondary)]">PNG 证据文件（最大 8 MB）
            <input type="file" accept="image/png,.png" className="mt-2 block w-full" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required />
          </label>
          {captureKind === "office_page" ? (
            <div>
              <label className="text-xs text-[var(--af-text-secondary)]">Office 页码（从 1 开始）
                <input type="number" className="af-input mt-1 block w-full sm:w-48" value={page} min={1} max={selectedReceipt?.page_count || 10000} step={1} onChange={(event) => setPage(event.target.value)} required />
              </label>
              <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">请上传该收据对应页的原始渲染 PNG；重拍、裁切或重新编码的图片不会匹配页摘要。</p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="text-xs text-[var(--af-text-secondary)]">实际视口宽度（CSS px）<input type="number" className="af-input mt-1 w-full" value={width} min={1} max={16384} step={1} onChange={(event) => setWidth(event.target.value)} required /></label>
              <label className="text-xs text-[var(--af-text-secondary)]">实际视口高度（CSS px）<input type="number" className="af-input mt-1 w-full" value={height} min={1} max={16384} step={1} onChange={(event) => setHeight(event.target.value)} required /></label>
              <label className="text-xs text-[var(--af-text-secondary)]">设备像素比<input type="number" className="af-input mt-1 w-full" value={scale} min={0.01} max={8} step="any" onChange={(event) => setScale(event.target.value)} required /></label>
            </div>
          )}
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm font-medium text-[var(--af-text-primary)]">五项视觉检查（默认未确认）</legend>
            {checkKeys.map((key) => <div className="grid items-end gap-2 sm:grid-cols-[minmax(140px,1fr)_2fr]" key={key}>
              <label className="text-xs text-[var(--af-text-secondary)]">{checklistLabels[key]}<select className="af-input mt-1 w-full" value={checklist[key].status} onChange={(event) => setChecklist((current) => ({ ...current, [key]: { ...current[key], status: event.target.value as ApiProductStrategyVisualCheckStatus } }))}>{Object.entries(statusLabels).map(([status, label]) => <option key={status} value={status}>{label}</option>)}</select></label>
              <input aria-label={`${checklistLabels[key]}说明`} placeholder="问题位置、判断依据或未确认原因" className="af-input w-full" value={checklist[key].note} maxLength={2000} onChange={(event) => setChecklist((current) => ({ ...current, [key]: { ...current[key], note: event.target.value } }))} />
            </div>)}
          </fieldset>
          <label className="block text-xs text-[var(--af-text-secondary)]">修订说明<textarea className="af-input mt-1 min-h-20 w-full" value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={10000} /></label>
          <label className="block text-xs text-[var(--af-text-secondary)]">前一修订摘要（首个修订留空）<input className="af-input mt-1 w-full font-mono text-xs" value={previousDigest} onChange={(event) => setPreviousDigest(event.target.value)} pattern="[0-9a-f]{64}" maxLength={64} /></label>
          {latestRevision ? <div className="text-xs leading-5 text-[var(--af-text-secondary)]">当前链最新 r{latestRevision.revision} · <code title={latestRevision.revision_digest}>{shortDigest(latestRevision.revision_digest)}</code><button type="button" className="af-btn af-btn-secondary ml-2 px-2 py-1 text-xs" onClick={() => setPreviousDigest(latestRevision.revision_digest)}>使用最新修订为基线</button><p>刷新保留输入和原基线。请先查看下方差异，再明确选择新的修订基线。</p></div> : null}
          <button type="submit" className="af-btn af-btn-primary px-4 py-2 text-xs" disabled={!selectedReceipt || !file || loading || submitting}>{submitting ? "记录视觉证据中..." : "记录视觉证据与修订"}</button>
        </fieldset>
      </form>
      <div className="mt-4 space-y-3">
        {!snapshot?.revisions.length && !loading ? <p className="text-sm text-[var(--af-text-tertiary)]">尚无视觉修订。上传只会记录证据，不会解除验收门禁。</p> : null}
        {snapshot?.revisions.map((revision) => <article key={revision.revision_key} className="min-w-0 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-2"><h4 className="break-all text-sm font-semibold text-[var(--af-text-primary)]">{revision.surface_key} · r{revision.revision} · {revision.file_name}</h4><span className="af-chip af-chip-warning">{revision.review_status === "needs_revision" ? "需修订" : "已记录 · 待独立复核"}</span></div>
          <p className="mt-2 text-xs text-[var(--af-text-secondary)]">{captureLabels[revision.capture_kind]} · PNG {revision.image_width} × {revision.image_height} · {revision.source_version}{revision.office_page_number ? ` · 第 ${revision.office_page_number} 页` : ""}{revision.viewport ? ` · 视口 ${revision.viewport.width} × ${revision.viewport.height} @${revision.viewport.device_scale_factor}` : ""}</p>
          <p className="mt-2 break-all text-xs text-[var(--af-text-tertiary)]">上一修订 <code title={revision.previous_revision_digest ?? ""}>{shortDigest(revision.previous_revision_digest)}</code> → 当前 <code title={revision.revision_digest}>{shortDigest(revision.revision_digest)}</code> · PNG SHA-256 <code title={revision.image_sha256}>{shortDigest(revision.image_sha256)}</code></p>
          <div className="mt-3 flex flex-wrap gap-2">{checkKeys.map((key) => <span key={key} title={revision.checklist[key].note} className="rounded-full bg-[var(--af-surface-muted)] px-2 py-1 text-xs text-[var(--af-text-secondary)]">{checklistLabels[key]}：{statusLabels[revision.checklist[key].status]}</span>)}</div>
          {revision.notes ? <p className="mt-3 whitespace-pre-wrap break-words text-xs text-[var(--af-text-secondary)]">{revision.notes}</p> : null}
          <details className="mt-3" open={revision.revision > 1}>
            <summary className="cursor-pointer text-xs font-medium text-[var(--af-text-primary)]">字段级差异（{revision.field_level_diff.length} 项）</summary>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[420px] table-fixed text-left text-xs text-[var(--af-text-secondary)]"><thead><tr><th className="p-2">字段</th><th className="p-2">修订前</th><th className="p-2">修订后</th></tr></thead><tbody>{revision.field_level_diff.map((diff) => <tr key={diff.field_path} className="border-t border-[var(--af-border-subtle)]"><td className="break-all p-2 align-top">{diff.field_path}<br />{({ added: "新增", removed: "移除", changed: "修改" })[diff.change_type]}</td><td className="whitespace-pre-wrap break-all p-2 align-top">{displayValue(diff.before)}</td><td className="whitespace-pre-wrap break-all p-2 align-top">{displayValue(diff.after)}</td></tr>)}</tbody></table></div>
          </details>
          <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">人工验收缺失 · HOLD · 不自动批准发布 · 生产未授权</p>
        </article>)}
      </div>
      {snapshot?.note ? <p className="mt-4 text-xs leading-5 text-[var(--af-text-tertiary)]">{snapshot.note}</p> : null}
    </section>
  );
}
