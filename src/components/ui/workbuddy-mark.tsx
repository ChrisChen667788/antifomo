import type { HTMLAttributes } from "react";

interface WorkBuddyMarkProps extends HTMLAttributes<HTMLSpanElement> {
  size?: number;
  withLabel?: boolean;
  label?: string;
}

export function WorkBuddyMark({
  size = 18,
  withLabel = false,
  label = "WorkBuddy",
  className = "",
  ...props
}: WorkBuddyMarkProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 ${className}`.trim()}
      {...props}
    >
      <img
        src="/brand/workbuddy.png"
        alt="WorkBuddy"
        width={size}
        height={size}
        className="h-auto w-auto object-contain"
      />
      {withLabel ? <span>{label}</span> : null}
    </span>
  );
}
