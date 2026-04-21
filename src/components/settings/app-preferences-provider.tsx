"use client";

import { createContext, startTransition, useContext, useEffect, useMemo, useState } from "react";
import { getMessage } from "@/lib/i18n";
import {
  APP_PREFERENCES_KEY,
  DEFAULT_PREFERENCES,
  type AppPreferences,
  getLanguageHtmlTag,
  normalizePreferences,
} from "@/lib/preferences";

interface AppPreferencesContextValue {
  preferences: AppPreferences;
  resolvedTheme: "light" | "dark";
  updatePreferences: (patch: Partial<AppPreferences>) => void;
  resetPreferences: () => void;
  t: (key: string, fallback?: string) => string;
}

const AppPreferencesContext = createContext<AppPreferencesContextValue | null>(null);

function readInitialPreferences(): AppPreferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }
  const raw = window.localStorage.getItem(APP_PREFERENCES_KEY);
  if (!raw) {
    return DEFAULT_PREFERENCES;
  }
  try {
    return normalizePreferences(JSON.parse(raw) as Partial<AppPreferences>);
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function readInitialSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyPreferencesToDom(preferences: AppPreferences, resolvedTheme: "light" | "dark") {
  const html = document.documentElement;
  html.dataset.afTheme = resolvedTheme;
  html.dataset.afThemeMode = preferences.themeMode;
  html.dataset.afFont = preferences.fontFamily;
  html.dataset.afTextSize = preferences.textSize;
  html.lang = getLanguageHtmlTag(preferences.language);
}

export function AppPreferencesProvider({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [preferences, setPreferences] = useState<AppPreferences>(readInitialPreferences);
  const [systemTheme, setSystemTheme] = useState<"light" | "dark">(readInitialSystemTheme);
  const resolvedTheme =
    preferences.themeMode === "system" ? systemTheme : preferences.themeMode;

  useEffect(() => {
    window.localStorage.setItem(APP_PREFERENCES_KEY, JSON.stringify(preferences));
    applyPreferencesToDom(preferences, resolvedTheme);
  }, [preferences, resolvedTheme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const updatePreferences = (patch: Partial<AppPreferences>) => {
    startTransition(() => {
      setPreferences((prev) => normalizePreferences({ ...prev, ...patch }));
    });
  };

  const resetPreferences = () => {
    startTransition(() => {
      setPreferences(DEFAULT_PREFERENCES);
    });
  };

  const value = useMemo<AppPreferencesContextValue>(
    () => ({
      preferences,
      resolvedTheme,
      updatePreferences,
      resetPreferences,
      t: (key: string, fallback?: string) => getMessage(preferences.language, key, fallback),
    }),
    [preferences, resolvedTheme],
  );

  return (
    <AppPreferencesContext.Provider value={value}>
      {children}
    </AppPreferencesContext.Provider>
  );
}

export function useAppPreferences() {
  const context = useContext(AppPreferencesContext);
  if (!context) {
    if (typeof window === "undefined") {
      return {
        preferences: DEFAULT_PREFERENCES,
        resolvedTheme: "light" as const,
        updatePreferences: () => {},
        resetPreferences: () => {},
        t: (key: string, fallback?: string) =>
          getMessage(DEFAULT_PREFERENCES.language, key, fallback),
      };
    }
    throw new Error("useAppPreferences must be used inside AppPreferencesProvider");
  }
  return context;
}
