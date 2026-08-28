"use client";

type LegacyResearchProgressCardProps = {
  progress: number;
  stateLabel: string;
  stageLabel: string;
  stageMessage: string;
  modeLabel: string;
  estimatedMinutes: number;
  keywordGroups: string[];
  modeHint: string;
  activePipelineLabel: string;
  pipelineStages: Array<{
    key: "fetch" | "clean" | "analyze";
    label: string;
    value: number;
    summary: string;
    status: "done" | "active" | "pending";
  }>;
};

function clampProgress(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function splitModeHint(value: string) {
  return value
    .split(/[。；;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 2);
}

export function LegacyResearchProgressCard({
  progress,
  stateLabel,
  stageLabel,
  stageMessage,
  modeLabel,
  estimatedMinutes,
  keywordGroups,
  modeHint,
  activePipelineLabel,
  pipelineStages,
}: LegacyResearchProgressCardProps) {
  const safeProgress = clampProgress(progress);
  const ringSize = 90;
  const strokeWidth = 10;
  const radius = (ringSize - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashLength = circumference * Math.max(0.1, safeProgress / 100);
  const dashOffset = circumference - dashLength;
  const sweepLength = Math.max(circumference * 0.14, 18);
  const hintLines = splitModeHint(modeHint);

  return (
    <section
      data-testid="research-progress-card"
      className="af-progress-card"
    >
      <div className="af-progress-row">
        <div className="af-progress-main">
          <div className="af-progress-ring">
            <div className="af-progress-ring-bg" />
            <svg
              viewBox={`0 0 ${ringSize} ${ringSize}`}
              className="af-progress-ring-svg"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="afResearchRingGradient" x1="0%" y1="100%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#6c63ff" />
                  <stop offset="34%" stopColor="#5f6fff" />
                  <stop offset="72%" stopColor="#3e8eff" />
                  <stop offset="100%" stopColor="#1fb3ff" />
                </linearGradient>
                <filter id="afResearchRingGlow" x="-60%" y="-60%" width="220%" height="220%">
                  <feGaussianBlur stdDeviation="1.05" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <circle
                cx={ringSize / 2}
                cy={ringSize / 2}
                r={radius}
                fill="none"
                stroke="var(--af-border-subtle)"
                strokeWidth={strokeWidth}
              />
              <circle
                cx={ringSize / 2}
                cy={ringSize / 2}
                r={radius}
                fill="none"
                stroke="url(#afResearchRingGradient)"
                strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={dashOffset}
                filter="url(#afResearchRingGlow)"
                className="af-research-ring-glow"
              />
              <g className="af-research-ring-sweep">
                <circle
                  cx={ringSize / 2}
                  cy={ringSize / 2}
                  r={radius}
                  fill="none"
                  stroke="var(--af-surface-elevated)"
                  strokeWidth={Math.max(2, strokeWidth - 5)}
                  strokeLinecap="round"
                  strokeDasharray={`${sweepLength} ${circumference}`}
                  strokeDashoffset={dashOffset + 8}
                  opacity="0.82"
                />
              </g>
            </svg>

            <div className="af-progress-center">
              <span className="af-progress-percent">
                {Math.round(safeProgress)}%
              </span>
              <span className="af-progress-pill">
                {modeLabel}
              </span>
              <span className="af-progress-center-label">进度</span>
            </div>
          </div>

          <div className="af-progress-copy">
            <p className="text-[11px] font-semibold tracking-[0.08em] text-slate-400">{stateLabel}</p>
            <h3 className="mt-1.5 text-[30px] font-semibold tracking-[-0.05em] text-slate-900 md:text-[34px]">
              {stageLabel}
            </h3>
            <p className="mt-2 max-w-3xl text-[14px] leading-6 text-slate-500">
              <span className="font-semibold text-slate-600">{modeLabel}</span>
              <span className="px-1.5 text-slate-300">·</span>
              <span>{stageMessage}</span>
            </p>
            {keywordGroups.length ? (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {keywordGroups.map((group) => (
                  <span
                    key={group}
                    className="rounded-full border border-sky-100/90 bg-sky-50/88 px-3 py-1 text-[11px] font-medium text-sky-700"
                  >
                    {group}
                  </span>
                ))}
              </div>
            ) : null}
            {pipelineStages.length ? (
              <div className="af-progress-pipeline">
                {pipelineStages.map((stage) => (
                  <div
                    key={stage.key}
                    className={`af-progress-stage af-progress-stage-${stage.status}`}
                  >
                    <div className="af-progress-stage-topline">
                      <span className="af-progress-stage-label">{stage.label}</span>
                      <span className="af-progress-stage-badge">
                        {stage.status === "done" ? "完成" : stage.status === "active" ? "进行中" : "等待"}
                      </span>
                    </div>
                    <p className="af-progress-stage-summary">{stage.summary}</p>
                    {stage.value > 0 ? (
                      <p className="af-progress-stage-value">已处理 {stage.value}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            <p className="mt-3 text-[11px] font-medium text-slate-400">预计耗时 · {estimatedMinutes} min</p>
          </div>
        </div>

        <div className="af-progress-mode">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-slate-400">{modeLabel}</p>
          <div className="af-progress-phase-pill">阶段 · {activePipelineLabel}</div>
          <div className="mt-2 space-y-1.5">
            {hintLines.map((line) => (
              <p key={line} className="leading-6 text-slate-600">
                {line}
              </p>
            ))}
            {hintLines.length === 0 ? <p className="leading-6 text-slate-600">{modeHint}</p> : null}
          </div>
        </div>
      </div>

      <style jsx>{`
        .af-progress-card {
          margin-top: 1.25rem;
          border-radius: 34px;
          border: 1px solid var(--af-border-subtle);
          background:
            linear-gradient(
              180deg,
              color-mix(in srgb, var(--af-surface-elevated) 96%, transparent),
              color-mix(in srgb, var(--af-surface-muted) 92%, transparent)
            );
          box-shadow:
            var(--af-shadow-card),
            inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 72%, transparent);
          padding: 1.25rem 1.5rem;
        }

        .af-progress-row {
          display: flex;
          flex-direction: column;
          gap: 1.25rem;
        }

        .af-progress-main {
          min-width: 0;
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .af-progress-ring {
          position: relative;
          width: 96px;
          height: 96px;
          flex: 0 0 96px;
        }

        .af-progress-ring-bg {
          position: absolute;
          inset: 6px;
          border-radius: 999px;
          border: 1px solid var(--af-border-subtle);
          background:
            radial-gradient(
              circle at 34% 28%,
              var(--af-surface-elevated),
              var(--af-surface-inset) 56%,
              var(--af-surface-muted)
            );
          box-shadow: 0 10px 22px -22px color-mix(in srgb, var(--af-accent) 32%, transparent);
        }

        .af-progress-ring-svg {
          position: absolute;
          inset: 3px;
          width: 90px;
          height: 90px;
          transform: rotate(-132deg);
        }

        .af-progress-center {
          position: absolute;
          inset: 14px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          border-radius: 999px;
          text-align: center;
          background: var(--af-surface-elevated);
          box-shadow: inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 76%, transparent);
        }

        .af-progress-percent {
          font-size: 16px;
          font-weight: 600;
          line-height: 1;
          letter-spacing: -0.06em;
          color: var(--af-text-primary);
        }

        .af-progress-pill {
          margin-top: 4px;
          border-radius: 999px;
          border: 1px solid var(--af-border-subtle);
          background: var(--af-surface-inset);
          padding: 2px 6px;
          font-size: 8px;
          font-weight: 600;
          line-height: 1;
          color: var(--af-text-secondary);
        }

        .af-progress-center-label {
          margin-top: 4px;
          font-size: 8px;
          font-weight: 600;
          line-height: 1;
          letter-spacing: 0.04em;
          color: var(--af-accent);
        }

        .af-progress-copy {
          min-width: 0;
          flex: 1 1 auto;
        }

        .af-progress-mode {
          width: 100%;
          max-width: 235px;
          padding: 0 0.25rem;
          font-size: 0.875rem;
          color: var(--af-text-secondary);
        }

        .af-progress-phase-pill {
          margin-top: 0.55rem;
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          border: 1px solid color-mix(in srgb, var(--af-info) 34%, var(--af-border-subtle));
          background: color-mix(in srgb, var(--af-info) 12%, var(--af-surface-muted));
          padding: 0.34rem 0.72rem;
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--af-info);
          box-shadow: inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 70%, transparent);
        }

        .af-progress-pipeline {
          margin-top: 0.85rem;
          display: grid;
          gap: 0.65rem;
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }

        .af-progress-stage {
          border-radius: 18px;
          border: 1px solid var(--af-border-subtle);
          background: linear-gradient(180deg, var(--af-surface-elevated), var(--af-surface-muted));
          padding: 0.72rem 0.78rem;
          box-shadow: inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 70%, transparent);
        }

        .af-progress-stage-done {
          border-color: color-mix(in srgb, var(--af-success) 34%, var(--af-border-subtle));
          background: color-mix(in srgb, var(--af-success) 10%, var(--af-surface-muted));
        }

        .af-progress-stage-active {
          border-color: color-mix(in srgb, var(--af-info) 38%, var(--af-border-subtle));
          background:
            radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--af-info) 14%, transparent), transparent 38%),
            linear-gradient(180deg, var(--af-surface-elevated), var(--af-surface-selected));
          box-shadow:
            0 10px 18px -20px color-mix(in srgb, var(--af-info) 26%, transparent),
            inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 72%, transparent);
        }

        .af-progress-stage-topline {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.5rem;
        }

        .af-progress-stage-label {
          font-size: 0.72rem;
          font-weight: 600;
          letter-spacing: 0.02em;
          color: var(--af-text-primary);
        }

        .af-progress-stage-badge {
          border-radius: 999px;
          background: var(--af-surface-inset);
          padding: 0.16rem 0.46rem;
          font-size: 0.62rem;
          font-weight: 600;
          color: var(--af-text-secondary);
        }

        .af-progress-stage-summary {
          margin-top: 0.45rem;
          font-size: 0.72rem;
          line-height: 1.45;
          color: var(--af-text-secondary);
        }

        .af-progress-stage-value {
          margin-top: 0.38rem;
          font-size: 0.68rem;
          font-weight: 600;
          color: var(--af-info);
        }

        .af-research-ring-glow {
          animation: af-research-ring-breathe 3.2s ease-in-out infinite;
        }

        .af-research-ring-sweep {
          transform-box: fill-box;
          transform-origin: center;
          animation: af-research-ring-sweep 4.6s linear infinite;
        }

        @keyframes af-research-ring-breathe {
          0%,
          100% {
            opacity: 0.98;
          }
          50% {
            opacity: 0.9;
          }
        }

        @keyframes af-research-ring-sweep {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        @media (min-width: 768px) {
          .af-progress-card {
            padding: 1.5rem 1.75rem;
          }

          .af-progress-main {
            gap: 1.25rem;
          }
        }

        @media (min-width: 1280px) {
          .af-progress-row {
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
          }

          .af-progress-mode {
            padding-right: 1rem;
          }
        }

        @media (max-width: 820px) {
          .af-progress-pipeline {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </section>
  );
}
