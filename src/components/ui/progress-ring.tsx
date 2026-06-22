"use client";

type ProgressRingProps = {
  value: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  className?: string;
  subtitle?: string;
};

function clamp(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function ProgressRing({
  value,
  size = 108,
  strokeWidth = 10,
  label,
  className = "",
  subtitle,
}: ProgressRingProps) {
  const safeValue = clamp(value);
  const angle = Math.max(safeValue, 4) * 3.6;
  const shellInset = Math.max(8, Math.round(strokeWidth));
  const middleInset = shellInset + Math.max(6, Math.round(strokeWidth * 0.55));
  const coreInset = middleInset + Math.max(12, Math.round(strokeWidth * 1.4));
  const ringBackground = `conic-gradient(from 220deg, #8b5cf6 0deg, #6366f1 70deg, #0ea5e9 ${angle}deg, rgba(148,163,184,0.18) ${angle}deg 360deg)`;

  return (
    <div
      className={`relative shrink-0 ${className}`.trim()}
      style={{ width: `${size}px`, height: `${size}px` }}
      aria-label={label ? `${label} ${safeValue}%` : `${safeValue}%`}
    >
      <div
        className="absolute inset-0 rounded-full border border-[var(--af-border-subtle)] shadow-[0_28px_62px_-34px_rgba(14,165,233,0.22)]"
        style={{ background: ringBackground }}
      />
      <div
        className="absolute rounded-full border border-[var(--af-border-subtle)]"
        style={{
          inset: `${shellInset}px`,
          background: "radial-gradient(circle at 28% 18%, var(--af-surface-elevated), transparent 42%)",
          boxShadow: "inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 72%, transparent)",
        }}
      />
      <div
        className="absolute rounded-full border border-[var(--af-border-subtle)]"
        style={{
          inset: `${middleInset}px`,
          background: "radial-gradient(circle at 30% 18%, var(--af-surface-elevated), var(--af-surface-muted) 48%, var(--af-surface-inset))",
        }}
      />
      <div
        className="absolute rounded-full border border-[var(--af-border-subtle)]"
        style={{
          inset: `${coreInset}px`,
          background: "radial-gradient(circle at 30% 18%, var(--af-surface-elevated), var(--af-surface-muted) 54%, var(--af-surface-inset))",
          boxShadow: "inset 0 1px 0 color-mix(in srgb, var(--af-surface-elevated) 72%, transparent)",
        }}
      />
      <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
        <span className="text-[26px] font-semibold leading-none tracking-[-0.06em] text-[var(--af-text-primary)]">
          {Math.round(safeValue)}%
        </span>
        {label ? (
          <span className="mt-1 text-[10px] font-semibold tracking-[0.14em] text-[var(--af-text-tertiary)]">
            {label}
          </span>
        ) : null}
        {subtitle ? <span className="mt-1 text-[10px] text-[var(--af-text-tertiary)]">{subtitle}</span> : null}
      </div>
    </div>
  );
}
