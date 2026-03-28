"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { AppIcon } from "@/components/ui/app-icon";

const navItems = [
  { href: "/", labelKey: "nav.feed", fallback: "Feed", icon: "home" as const },
  { href: "/inbox", labelKey: "nav.inbox", fallback: "Solution Intelligence", icon: "inbox" as const },
  { href: "/research", labelKey: "nav.research", fallback: "研报中心", icon: "spark" as const },
  { href: "/saved", labelKey: "nav.saved", fallback: "Saved", icon: "bookmark" as const },
  { href: "/knowledge", labelKey: "nav.knowledge", fallback: "知识库", icon: "knowledge" as const },
  { href: "/focus", labelKey: "nav.focus", fallback: "Focus", icon: "focus" as const },
  { href: "/session-summary", labelKey: "nav.summary", fallback: "Session Summary", icon: "summary" as const },
  { href: "/collector", labelKey: "nav.collector", fallback: "Collector", icon: "collector" as const },
  { href: "/settings", labelKey: "nav.settings", fallback: "设置", icon: "settings" as const },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(href);
}

export function MainNav() {
  const pathname = usePathname();
  const { t } = useAppPreferences();

  return (
    <header className="sticky top-0 z-40 px-3 pt-3 md:px-6 md:pt-4">
      <div className="af-glass af-topbar-glass mx-auto flex w-full max-w-6xl items-center gap-3 rounded-[20px] px-3 py-2 md:px-4 md:py-2.5">
        <div className="shrink-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
            Anti-FOMO
          </p>
        </div>
        <nav className="flex flex-1 items-center justify-end gap-1.5 overflow-x-auto">
          {navItems.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`af-btn af-nav-chip shrink-0 px-3 py-1.5 text-[13px] ${
                  active ? "af-nav-chip-active" : "af-nav-chip-idle"
                }`}
              >
                <AppIcon name={item.icon} className="h-3.5 w-3.5 shrink-0" />
                {t(item.labelKey, item.fallback)}
              </Link>
            );
          })}

          <input
            type="search"
            placeholder={t("common.searchPlaceholder", "搜索")}
            className="af-input ml-1 hidden w-36 bg-white/65 py-1.5 text-[13px] md:block"
          />
          <Link
            href="/settings"
            aria-label={t("common.settings", "设置")}
            className="af-glass-orb-btn ml-1"
          >
            <AppIcon name="settings" className="h-4 w-4" />
          </Link>
          <div className="af-glass-orb-badge ml-1">
            AF
          </div>
        </nav>
      </div>
    </header>
  );
}
