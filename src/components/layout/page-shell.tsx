"use client";

import type { ReactNode } from "react";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

interface PageShellProps {
  title: string;
  description?: string;
  titleKey?: string;
  descriptionKey?: string;
  children: ReactNode;
}

export function PageShell({
  title,
  description,
  titleKey,
  descriptionKey,
  children,
}: PageShellProps) {
  const { t } = useAppPreferences();
  return (
    <section className="mx-auto w-full max-w-6xl px-4 pb-8 pt-6 md:px-8 md:pb-12 md:pt-8">
      <header className="af-fade-up mb-7 md:mb-9">
        <p className="af-kicker mb-2">{t("page.kicker", "Anti-fomo Experience")}</p>
        <h1 className="af-headline text-slate-900">{titleKey ? t(titleKey, title) : title}</h1>
        {description ? (
          <p className="af-subtext mt-2 max-w-3xl">
            {descriptionKey ? t(descriptionKey, description) : description}
          </p>
        ) : null}
      </header>
      <div className="af-fade-up">{children}</div>
    </section>
  );
}
