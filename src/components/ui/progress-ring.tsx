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
        className="absolute inset-0 rounded-full border border-slate-300/55 shadow-[0_28px_62px_-34px_rgba(14,165,233,0.22)]"
        style={{ background: ringBackground }}
      />
      <div
        className="absolute rounded-full border border-white/85 bg-[radial-gradient(circle_at_28%_18%,rgba(255,255,255,0.76),rgba(255,255,255,0)_42%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]"
        style={{ inset: `${shellInset}px` }}
      />
      <div
        className="absolute rounded-full border border-slate-200/85 bg-[radial-gradient(circle_at_30%_18%,rgba(255,255,255,0.98),rgba(248,250,252,0.92)_48%,rgba(226,232,240,0.82))]"
        style={{ inset: `${middleInset}px` }}
      />
      <div
        className="absolute rounded-full border border-slate-200/90 bg-[radial-gradient(circle_at_30%_18%,rgba(255,255,255,0.98),rgba(248,250,252,0.94)_54%,rgba(232,238,246,0.84))] shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]"
        style={{ inset: `${coreInset}px` }}
      />
      <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
        <span className="text-[26px] font-semibold leading-none tracking-[-0.06em] text-slate-900">
          {Math.round(safeValue)}%
        </span>
        {label ? (
          <span className="mt-1 text-[10px] font-semibold tracking-[0.14em] text-slate-400">
            {label}
          </span>
        ) : null}
        {subtitle ? <span className="mt-1 text-[10px] text-slate-400">{subtitle}</span> : null}
      </div>
    </div>
  );
}
