
"use client";

import type { WechatAgentConfig } from "@/lib/api";
import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentConfigSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentConfigSection({
  controller,
  text,
}: CollectorOpsWechatAgentConfigSectionProps) {
  const {
    wechatAgentConfig,
    setWechatAgentConfig,
    savingWechatAgentConfig,
    wechatHotspotsText,
    setWechatHotspotsText,
    wechatMenuOffsetsText,
    setWechatMenuOffsetsText,
    handleSaveWechatAgentConfig,
    updateWechatAgentIntField,
  } = controller;

  return (
    <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
      <p className="text-sm font-semibold text-[var(--af-text-primary)]">
        {text("wechatAgentConfigTitle")}
      </p>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigProfile")}
          <select
            value={wechatAgentConfig?.article_link_profile ?? "auto"}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      article_link_profile: event.target.value as WechatAgentConfig["article_link_profile"],
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          >
            <option value="auto">{text("wechatAgentConfigProfileAuto")}</option>
            <option value="compact">{text("wechatAgentConfigProfileCompact")}</option>
            <option value="standard">{text("wechatAgentConfigProfileStandard")}</option>
            <option value="wide">{text("wechatAgentConfigProfileWide")}</option>
            <option value="manual">{text("wechatAgentConfigProfileManual")}</option>
          </select>
          <span className="text-[11px] text-[var(--af-text-tertiary)]">
            {text("wechatAgentConfigProfileHint")}
          </span>
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigRows")}
          <input
            type="number"
            value={wechatAgentConfig?.rows_per_batch ?? ""}
            onChange={(event) => updateWechatAgentIntField("rows_per_batch", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigBatches")}
          <input
            type="number"
            value={wechatAgentConfig?.batches_per_cycle ?? ""}
            onChange={(event) => updateWechatAgentIntField("batches_per_cycle", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigRowHeight")}
          <input
            type="number"
            value={wechatAgentConfig?.article_row_height ?? ""}
            onChange={(event) => updateWechatAgentIntField("article_row_height", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigMinFileSize")}
          <input
            type="number"
            value={wechatAgentConfig?.min_capture_file_size_kb ?? ""}
            onChange={(event) => updateWechatAgentIntField("min_capture_file_size_kb", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigInterval")}
          <input
            type="number"
            value={wechatAgentConfig?.loop_interval_sec ?? ""}
            onChange={(event) => updateWechatAgentIntField("loop_interval_sec", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigHealthStale")}
          <input
            type="number"
            value={wechatAgentConfig?.health_stale_minutes ?? ""}
            onChange={(event) => updateWechatAgentIntField("health_stale_minutes", event.target.value)}
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigListOrigin")} x
          <input
            type="number"
            value={wechatAgentConfig?.list_origin?.x ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      list_origin: { ...prev.list_origin, x: Number.parseInt(event.target.value || "0", 10) || 0 },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigListOrigin")} y
          <input
            type="number"
            value={wechatAgentConfig?.list_origin?.y ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      list_origin: { ...prev.list_origin, y: Number.parseInt(event.target.value || "0", 10) || 0 },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigCapture")} x
          <input
            type="number"
            value={wechatAgentConfig?.article_capture_region?.x ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      article_capture_region: {
                        ...prev.article_capture_region,
                        x: Number.parseInt(event.target.value || "0", 10) || 0,
                      },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigCapture")} y
          <input
            type="number"
            value={wechatAgentConfig?.article_capture_region?.y ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      article_capture_region: {
                        ...prev.article_capture_region,
                        y: Number.parseInt(event.target.value || "0", 10) || 0,
                      },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigCapture")} w
          <input
            type="number"
            value={wechatAgentConfig?.article_capture_region?.width ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      article_capture_region: {
                        ...prev.article_capture_region,
                        width: Number.parseInt(event.target.value || "0", 10) || 0,
                      },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigCapture")} h
          <input
            type="number"
            value={wechatAgentConfig?.article_capture_region?.height ?? ""}
            onChange={(event) =>
              setWechatAgentConfig((prev) =>
                prev
                  ? {
                      ...prev,
                      article_capture_region: {
                        ...prev.article_capture_region,
                        height: Number.parseInt(event.target.value || "0", 10) || 0,
                      },
                    }
                  : prev,
              )
            }
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
        </label>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigHotspots")}
          <input
            type="text"
            value={wechatHotspotsText}
            onChange={(event) => setWechatHotspotsText(event.target.value)}
            placeholder="44:26, 84:26, 124:26, 44:58"
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
          <span className="text-[11px] text-[var(--af-text-tertiary)]">
            {text("wechatAgentConfigHotspotsHint")}
          </span>
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--af-text-secondary)]">
          {text("wechatAgentConfigMenuOffsets")}
          <input
            type="text"
            value={wechatMenuOffsetsText}
            onChange={(event) => setWechatMenuOffsetsText(event.target.value)}
            placeholder="0:42, 0:78, 0:112, -52:78, 52:78"
            className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-primary)] outline-none transition focus:border-[var(--af-accent)]"
          />
          <span className="text-[11px] text-[var(--af-text-tertiary)]">
            {text("wechatAgentConfigMenuHint")}
          </span>
        </label>
      </div>
      <div className="mt-3">
        <button
          type="button"
          onClick={() => void handleSaveWechatAgentConfig()}
          disabled={!wechatAgentConfig || savingWechatAgentConfig}
          className="af-btn af-btn-secondary px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-60"
        >
          {savingWechatAgentConfig ? "..." : text("wechatAgentConfigSave")}
        </button>
      </div>
    </div>
  );
}
