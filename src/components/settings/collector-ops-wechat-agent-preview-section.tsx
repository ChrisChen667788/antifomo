
"use client";

import Image from "next/image";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import {
  formatBytes,
  shortText,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentPreviewSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentPreviewSection({
  controller,
  text,
}: CollectorOpsWechatAgentPreviewSectionProps) {
  const {
    wechatAgentCapturePreview,
    wechatAgentOCRPreview,
  } = controller;

  return (
    <>
      {wechatAgentCapturePreview ? (
        <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {text("wechatAgentPreviewImage")}
          </p>
          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
            {text("wechatAgentPreviewSize")}: {formatBytes(wechatAgentCapturePreview.image_size_bytes)}
          </p>
          <Image
            src={`data:${wechatAgentCapturePreview.mime_type};base64,${wechatAgentCapturePreview.image_base64}`}
            alt="wechat-capture-preview"
            width={Math.max(wechatAgentCapturePreview.region?.width || 0, 1)}
            height={Math.max(wechatAgentCapturePreview.region?.height || 0, 1)}
            unoptimized
            className="mt-2 w-full rounded-lg border border-[var(--af-border-subtle)] object-cover"
          />
        </div>
      ) : null}

      {wechatAgentOCRPreview ? (
        <div className="mt-3 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3 text-xs text-[var(--af-text-secondary)]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-[var(--af-text-primary)]">{text("wechatAgentPreviewOCRTitle")}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] ${
                wechatAgentOCRPreview.quality_ok
                  ? "border af-chip-success"
                  : "border af-chip-warning"
              }`}
            >
              {text("wechatAgentPreviewOCRQuality")}:
              {" "}
              {wechatAgentOCRPreview.quality_ok
                ? text("wechatAgentPreviewOCRQualityOK")
                : text("wechatAgentPreviewOCRQualityBad")}
            </span>
          </div>
          <p className="mt-2">
            {text("wechatAgentPreviewOCRProvider")}: {wechatAgentOCRPreview.provider}
            {" · "}
            conf={wechatAgentOCRPreview.confidence.toFixed(3)}
            {" · "}
            len={wechatAgentOCRPreview.text_length}
          </p>
          {wechatAgentOCRPreview.quality_reason ? (
            <p className="mt-1 text-[var(--af-warning)]">
              {text("wechatAgentPreviewOCRReason")}: {wechatAgentOCRPreview.quality_reason}
            </p>
          ) : null}
          <p className="mt-2 font-semibold text-[var(--af-text-primary)]">{shortText(wechatAgentOCRPreview.title, 140)}</p>
          <p className="mt-2 whitespace-pre-wrap leading-6 text-[var(--af-text-secondary)]">
            {shortText(wechatAgentOCRPreview.body_preview, 480)}
          </p>
          <p className="mt-2 text-[var(--af-text-tertiary)]">
            {text("wechatAgentPreviewOCRKeywords")}:
            {" "}
            {wechatAgentOCRPreview.keywords.length ? wechatAgentOCRPreview.keywords.join(", ") : "-"}
          </p>
        </div>
      ) : null}
    </>
  );
}
