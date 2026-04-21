import type { SVGProps } from "react";

type IconName =
  | "home"
  | "inbox"
  | "bookmark"
  | "knowledge"
  | "focus"
  | "summary"
  | "collector"
  | "settings"
  | "spark"
  | "thumb"
  | "ignore"
  | "external"
  | "refresh"
  | "flag"
  | "search"
  | "edit"
  | "merge"
  | "copy"
  | "calendar"
  | "source";

interface AppIconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
}

export function AppIcon({ name, className, ...props }: AppIconProps) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  switch (name) {
    case "home":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M4 10.5 12 4l8 6.5" />
          <path {...common} d="M6.5 9.5V20h11V9.5" />
          <path {...common} d="M10 20v-5.5h4V20" />
        </svg>
      );
    case "inbox":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M4.5 6.5h15l1.5 9.5H15.5l-2 2h-3l-2-2H3z" />
          <path {...common} d="M4.5 6.5 7 4h10l2.5 2.5" />
        </svg>
      );
    case "bookmark":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M7 4.5h10v15l-5-3.5-5 3.5z" />
        </svg>
      );
    case "knowledge":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M6 5.5h8.5A3.5 3.5 0 0 1 18 9v9.5H9.5A3.5 3.5 0 0 0 6 22z" />
          <path {...common} d="M6 5.5h8.5A3.5 3.5 0 0 1 18 9v9.5H9.5A3.5 3.5 0 0 0 6 22z" />
          <path {...common} d="M6 5.5V22" />
          <path {...common} d="M9.5 9.5h5" />
          <path {...common} d="M9.5 13h5" />
        </svg>
      );
    case "focus":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <circle {...common} cx="12" cy="12" r="7.5" />
          <circle {...common} cx="12" cy="12" r="2.5" />
          <path {...common} d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2" />
        </svg>
      );
    case "summary":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M7 4.5h10l2.5 2.5v12H7z" />
          <path {...common} d="M17 4.5v4h4" />
          <path {...common} d="M9.5 11h5M9.5 14.5h5M9.5 18h3.5" />
        </svg>
      );
    case "collector":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M6 5.5h12" />
          <path {...common} d="M8 5.5v6.5a4 4 0 1 0 8 0V5.5" />
          <path {...common} d="M7.5 18.5h9" />
        </svg>
      );
    case "settings":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path
            {...common}
            d="M10.4 3.6h3.2l.6 2.2a6.8 6.8 0 0 1 1.7.9l2-1 2.2 2.2-1 2a6.8 6.8 0 0 1 .9 1.7l2.2.6v3.2l-2.2.6a6.8 6.8 0 0 1-.9 1.7l1 2-2.2 2.2-2-1a6.8 6.8 0 0 1-1.7.9l-.6 2.2h-3.2l-.6-2.2a6.8 6.8 0 0 1-1.7-.9l-2 1-2.2-2.2 1-2a6.8 6.8 0 0 1-.9-1.7l-2.2-.6v-3.2l2.2-.6a6.8 6.8 0 0 1 .9-1.7l-1-2 2.2-2.2 2 1a6.8 6.8 0 0 1 1.7-.9z"
          />
          <circle {...common} cx="12" cy="12" r="2.6" />
        </svg>
      );
    case "spark":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="m12 3 1.6 4.6L18 9.2l-4.4 1.6L12 15.5l-1.6-4.7L6 9.2l4.4-1.6z" />
          <path {...common} d="m18.5 14 0.8 2.3 2.2 0.8-2.2 0.8-0.8 2.3-0.8-2.3-2.2-0.8 2.2-0.8z" />
        </svg>
      );
    case "thumb":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M10 10.5 12.8 4a1.8 1.8 0 0 1 1.7 2.4l-1 3.1H18a2 2 0 0 1 1.9 2.5l-1.8 6A2 2 0 0 1 16.2 20H10z" />
          <path {...common} d="M5 10.5h3V20H5z" />
        </svg>
      );
    case "ignore":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <circle {...common} cx="12" cy="12" r="7.5" />
          <path {...common} d="M9 9 15 15M15 9l-6 6" />
        </svg>
      );
    case "external":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M13 5.5h5.5V11" />
          <path {...common} d="M18.5 5.5 10 14" />
          <path {...common} d="M18 13.5V18a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V7.5A1.5 1.5 0 0 1 6 6h4.5" />
        </svg>
      );
    case "refresh":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M19 7.5V4.5h-3" />
          <path {...common} d="M5 16.5v3h3" />
          <path {...common} d="M18.2 10a6.8 6.8 0 0 0-11.6-2l-1 1" />
          <path {...common} d="M5.8 14a6.8 6.8 0 0 0 11.6 2l1-1" />
        </svg>
      );
    case "flag":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M6 20V4.5" />
          <path {...common} d="M6 5.5h9l-1.8 3L15 11.5H6z" />
        </svg>
      );
    case "search":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <circle {...common} cx="11" cy="11" r="5.8" />
          <path {...common} d="M16 16 20 20" />
        </svg>
      );
    case "edit":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M4.5 19.5 8 18.7l9.2-9.2a1.8 1.8 0 0 0 0-2.6l-.1-.1a1.8 1.8 0 0 0-2.6 0L5.3 16z" />
          <path {...common} d="M13.5 7.5 16.5 10.5" />
          <path {...common} d="M4.5 19.5h15" />
        </svg>
      );
    case "merge":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M6 6.5h6v6H6z" />
          <path {...common} d="M12 11.5h6v6h-6z" />
          <path {...common} d="M12 6.5h6v2.5M6 14.5h2.5V20" />
        </svg>
      );
    case "copy":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <rect {...common} x="8" y="8" width="10" height="11" rx="1.8" />
          <path {...common} d="M6.5 15.5H6A1.5 1.5 0 0 1 4.5 14V6A1.5 1.5 0 0 1 6 4.5h8A1.5 1.5 0 0 1 15.5 6v.5" />
        </svg>
      );
    case "calendar":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <rect {...common} x="4.5" y="5.5" width="15" height="14" rx="2.2" />
          <path {...common} d="M8 3.8v3.4M16 3.8v3.4M4.5 9.5h15" />
          <path {...common} d="M8 13h3M8 16.5h6" />
        </svg>
      );
    case "source":
      return (
        <svg viewBox="0 0 24 24" className={className} {...props}>
          <path {...common} d="M5.5 18.5h13" />
          <path {...common} d="M8 15.5V8.8a2.2 2.2 0 0 1 2.2-2.3h3.6A2.2 2.2 0 0 1 16 8.8v6.7" />
          <path {...common} d="M9.7 10.5h4.6" />
          <path {...common} d="M11 3.8h2" />
          <path {...common} d="M7 18.5v1.7M17 18.5v1.7" />
        </svg>
      );
    default:
      return null;
  }
}
