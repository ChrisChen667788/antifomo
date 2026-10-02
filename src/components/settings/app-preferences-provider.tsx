"use client";

import { createContext, startTransition, useContext, useEffect, useMemo, useSyncExternalStore } from "react";
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
const PREFERENCES_CHANGE_EVENT = "anti-fomo:preferences-change";
let cachedPreferencesRaw: string | null | undefined;
let cachedPreferences = DEFAULT_PREFERENCES;

function readBrowserPreferences(): AppPreferences {
  const raw = window.localStorage.getItem(APP_PREFERENCES_KEY);
  if (raw === cachedPreferencesRaw) return cachedPreferences;
  cachedPreferencesRaw = raw;
  if (!raw) return (cachedPreferences = DEFAULT_PREFERENCES);
  try {
    return (cachedPreferences = normalizePreferences(JSON.parse(raw) as Partial<AppPreferences>));
  } catch {
    return (cachedPreferences = DEFAULT_PREFERENCES);
  }
}

function subscribePreferences(onStoreChange: () => void) {
  const handleStorage = (event: StorageEvent) => {
    if (event.key && event.key !== APP_PREFERENCES_KEY) return;
    cachedPreferencesRaw = undefined;
    onStoreChange();
  };
  window.addEventListener("storage", handleStorage);
  window.addEventListener(PREFERENCES_CHANGE_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", handleStorage);
    window.removeEventListener(PREFERENCES_CHANGE_EVENT, onStoreChange);
  };
}

function persistPreferences(preferences: AppPreferences) {
  const normalized = normalizePreferences(preferences);
  const raw = JSON.stringify(normalized);
  window.localStorage.setItem(APP_PREFERENCES_KEY, raw);
  cachedPreferencesRaw = raw;
  cachedPreferences = normalized;
  window.dispatchEvent(new Event(PREFERENCES_CHANGE_EVENT));
}

function readSystemTheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribeSystemTheme(onStoreChange: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", onStoreChange);
  return () => media.removeEventListener("change", onStoreChange);
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
  const preferences = useSyncExternalStore(
    subscribePreferences,
    readBrowserPreferences,
    () => DEFAULT_PREFERENCES,
  );
  const systemTheme = useSyncExternalStore(
    subscribeSystemTheme,
    readSystemTheme,
    () => "light" as const,
  );
  const resolvedTheme =
    preferences.themeMode === "system" ? systemTheme : preferences.themeMode;

  useEffect(() => {
    applyPreferencesToDom(preferences, resolvedTheme);
  }, [preferences, resolvedTheme]);

  const updatePreferences = (patch: Partial<AppPreferences>) => {
    startTransition(() => {
      persistPreferences(normalizePreferences({ ...readBrowserPreferences(), ...patch }));
    });
  };

  const resetPreferences = () => {
    startTransition(() => {
      persistPreferences(DEFAULT_PREFERENCES);
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
