export function CollectorOpsStatCard({
  label,
  value,
}: {
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.15em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
