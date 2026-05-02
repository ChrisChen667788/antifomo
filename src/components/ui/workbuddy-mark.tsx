import Image from "next/image";
import type { HTMLAttributes } from "react";

interface WorkBuddyMarkProps extends HTMLAttributes<HTMLSpanElement> {
  size?: number;
  withLabel?: boolean;
  label?: string;
}

export function WorkBuddyMark({
  size = 18,
  withLabel = false,
  label = "导出",
  className = "",
  ...props
}: WorkBuddyMarkProps) {
  return (
    <span
      className={`inline-flex items-center gap-2 ${className}`.trim()}
      {...props}
    >
      <Image
        src="/brand/workbuddy.png"
        alt="导出"
        width={size}
        height={size}
        className="h-auto w-auto object-contain"
      />
      {withLabel ? <span>{label}</span> : null}
    </span>
  );
}
