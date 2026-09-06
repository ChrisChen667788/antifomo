"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createOfficeEvidenceReceipt,
  getArtifactAcceptance,
  getOfficeEvidenceReceipts,
} from "@/lib/api/competitive-intelligence";
import type {
  ApiProductStrategyArtifactAcceptanceArtifact,
  ApiProductStrategyOfficeEvidenceLandscape,
} from "@/lib/api/type-contracts/competitive-intelligence";

function shortDigest(value: string | null | undefined): string {
  if (!value) return "未生成";
  return value.length > 20 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("无法读取所选文件。"));
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const separator = result.indexOf(",");
      if (separator < 0) reject(new Error("无法编码所选文件。"));
      else resolve(result.slice(separator + 1));
    };
    reader.readAsDataURL(file);
  });
}

export function CompetitiveOfficeEvidenceReceipts() {
  const [snapshot, setSnapshot] = useState<ApiProductStrategyOfficeEvidenceLandscape | null>(null);
  const [artifacts, setArtifacts] = useState<ApiProductStrategyArtifactAcceptanceArtifact[]>([]);
  const [artifactKey, setArtifactKey] = useState("");
  const [sourceVersion, setSourceVersion] = useState("2.10.5-local");
  const [file, setFile] = useState<File | null>(null);
  const [renderedPdf, setRenderedPdf] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [receipts, acceptance] = await Promise.all([
          getOfficeEvidenceReceipts(),
          getArtifactAcceptance(),
        ]);
        if (!active) return;
        setSnapshot(receipts);
        setArtifacts(acceptance.artifacts);
        setArtifactKey((current) => current || acceptance.artifacts[0]?.artifact_key || "");
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "无法读取 Office 证据收据。");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const selectedArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.artifact_key === artifactKey) ?? null,
    [artifactKey, artifacts],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !artifactKey) return;
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      const result = await createOfficeEvidenceReceipt({
        artifact_key: artifactKey,
        file_name: file.name,
        media_type: file.type,
        file_base64: await fileToBase64(file),
        source_version: sourceVersion.trim() || "unspecified",
        ...(renderedPdf
          ? {
              rendered_pdf_base64: await fileToBase64(renderedPdf),
              render_engine: file.name.toLowerCase().endsWith(".pptx")
                ? ("microsoft_powerpoint_manual_export" as const)
                : ("microsoft_word_manual_export" as const),
            }
          : {}),
      });
      const refreshed = await getOfficeEvidenceReceipts();
      setSnapshot(refreshed);
      setMessage(
        result.deduplicated
          ? "相同文件摘要已存在，已返回原有不可变收据。"
          : "已记录本地结构与无头渲染证据；人工验收和发布状态仍为 HOLD。",
      );
      setFile(null);
      setRenderedPdf(null);
      const input = document.getElementById("office-evidence-file") as HTMLInputElement | null;
      if (input) input.value = "";
      const pdfInput = document.getElementById("office-evidence-rendered-pdf") as HTMLInputElement | null;
      if (pdfInput) pdfInput.value = "";
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Office 证据处理失败，未改变验收状态。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section
      className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]"
      data-testid="competitive-office-evidence-receipts"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">2.10.5 Office Evidence</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">Office 交付物证据收据</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            上传 Anti-FOMO 生成的 DOCX 或 PPTX，绑定当前 2.10.2 工件 revision，记录文件摘要、OpenXML 结构和本机渲染结果；可附上 Microsoft Office 实机导出的 PDF。收据不可自动接受工件，也不能替代具名人工复核。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="af-chip bg-rose-100 text-rose-700">HOLD · blocked</span>
          <span className="af-chip bg-sky-100 text-sky-700">本地运行证据</span>
        </div>
      </div>

      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取 Office 证据收据...</p> : null}
      {error ? <p className="mt-4 rounded-[16px] bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700">{error}</p> : null}
      {message ? <p className="mt-4 rounded-[16px] bg-emerald-50 px-3 py-2 text-sm leading-6 text-emerald-800">{message}</p> : null}

      {snapshot ? (
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="不可变收据" value={`${snapshot.receipt_count} 条`} />
          <Metric label="本地 roundtrip" value={`${snapshot.local_roundtrip_passed_count} 条`} />
          <Metric label="已渲染待人工复核" value={`${snapshot.rendered_unreviewed_count} 条`} />
          <Metric label="验收状态" value="HOLD" />
        </div>
      ) : null}

      <form className="mt-4 rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4" onSubmit={submit}>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(180px,0.6fr)]">
          <label className="text-xs font-medium text-[var(--af-text-secondary)]">
            绑定的 2.10.2 工件
            <select
              className="af-input mt-1 w-full"
              value={artifactKey}
              onChange={(event) => setArtifactKey(event.target.value)}
              disabled={!artifacts.length || submitting}
            >
              {!artifacts.length ? <option value="">请先初始化 2.10.2 验收草稿</option> : null}
              {artifacts.map((artifact) => (
                <option key={artifact.artifact_key} value={artifact.artifact_key}>
                  {artifact.title} · r{artifact.revision}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium text-[var(--af-text-secondary)]">
            来源版本
            <input
              className="af-input mt-1 w-full"
              value={sourceVersion}
              onChange={(event) => setSourceVersion(event.target.value)}
              maxLength={120}
              disabled={submitting}
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="min-w-0 flex-1 text-xs font-medium text-[var(--af-text-secondary)]">
            DOCX 或 PPTX 文件（最大 20 MB）
            <input
              id="office-evidence-file"
              type="file"
              accept=".docx,.pptx"
              className="mt-1 block w-full text-xs text-[var(--af-text-secondary)]"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              disabled={submitting}
            />
          </label>
          <button type="submit" className="af-btn af-btn-primary px-4 py-2 text-xs" disabled={!file || !artifactKey || submitting}>
            {submitting ? "校验并生成收据..." : "校验并生成收据"}
          </button>
        </div>
        <label className="mt-3 block text-xs font-medium text-[var(--af-text-secondary)]">
          可选：由 Microsoft Office 实机导出的伴随 PDF
          <input
            id="office-evidence-rendered-pdf"
            type="file"
            accept="application/pdf,.pdf"
            className="mt-1 block w-full text-xs text-[var(--af-text-secondary)]"
            onChange={(event) => setRenderedPdf(event.target.files?.[0] ?? null)}
            disabled={submitting}
          />
        </label>
        <p className="mt-2 text-[11px] leading-5 text-[var(--af-text-tertiary)]">
          {selectedArtifact
            ? `将绑定 ${selectedArtifact.artifact_key} · revision ${shortDigest(selectedArtifact.revision_digest)}${renderedPdf ? " · 同时记录 Office 实机导出 PDF 与页级哈希" : ""}`
            : "没有可绑定的工件；本操作不会自动初始化前置台账。"}
        </p>
      </form>

      {snapshot?.receipts.length ? (
        <div className="mt-4 space-y-3">
          {snapshot.receipts.map((receipt) => (
            <article key={receipt.receipt_key} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[11px] text-[var(--af-text-tertiary)]">{shortDigest(receipt.receipt_digest)}</p>
                  <h4 className="mt-1 break-words text-sm font-semibold text-[var(--af-text-primary)]">{receipt.file_name}</h4>
                  <p className="mt-1 text-xs text-[var(--af-text-secondary)]">{formatBytes(receipt.file_size_bytes)} · {receipt.page_count} 页 · {receipt.source_version}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={receipt.structure_status === "pass" ? "af-chip af-chip-success" : "af-chip bg-rose-100 text-rose-700"}>
                    结构 {receipt.structure_status}
                  </span>
                  <span className={receipt.office_roundtrip_status === "passed" ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
                    roundtrip {receipt.office_roundtrip_status}
                  </span>
                  <span className="af-chip bg-rose-100 text-rose-700">人工验收缺失</span>
                </div>
              </div>
              <div className="mt-3 grid gap-2 text-xs leading-5 text-[var(--af-text-secondary)] md:grid-cols-3">
                <Info label="文件摘要" value={shortDigest(receipt.file_sha256)} />
                <Info label="绑定 revision" value={`r${receipt.artifact_revision} · ${shortDigest(receipt.artifact_revision_digest)}`} />
                <Info label="视觉状态" value={receipt.visual_evidence_status} />
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {snapshot ? <p className="mt-3 text-[11px] leading-5 text-[var(--af-text-tertiary)]">{snapshot.note}</p> : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <p className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2">
      <span className="font-semibold text-[var(--af-text-primary)]">{label}：</span>{value}
    </p>
  );
}
