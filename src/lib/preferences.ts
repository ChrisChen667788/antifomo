export type ThemeMode = "light" | "dark" | "system";
export type FontFamily = "system" | "serif" | "mono";
export type TextSize = "sm" | "md" | "lg";
export type AppLanguage = "zh-CN" | "zh-TW" | "en" | "ja" | "ko";

export interface AppPreferences {
  themeMode: ThemeMode;
  fontFamily: FontFamily;
  textSize: TextSize;
  language: AppLanguage;
}

export const APP_PREFERENCES_KEY = "anti_fomo_app_preferences_v1";

export const DEFAULT_PREFERENCES: AppPreferences = {
  themeMode: "system",
  fontFamily: "system",
  textSize: "md",
  language: "zh-CN",
};

export function normalizePreferences(
  input: Partial<AppPreferences> | null | undefined,
): AppPreferences {
  const raw = input || {};
  const themeMode: ThemeMode =
    raw.themeMode === "light" || raw.themeMode === "dark" || raw.themeMode === "system"
      ? raw.themeMode
      : DEFAULT_PREFERENCES.themeMode;
  const fontFamily: FontFamily =
    raw.fontFamily === "system" || raw.fontFamily === "serif" || raw.fontFamily === "mono"
      ? raw.fontFamily
      : DEFAULT_PREFERENCES.fontFamily;
  const textSize: TextSize =
    raw.textSize === "sm" || raw.textSize === "md" || raw.textSize === "lg"
      ? raw.textSize
      : DEFAULT_PREFERENCES.textSize;
  const language: AppLanguage =
    raw.language === "zh-CN" ||
    raw.language === "zh-TW" ||
    raw.language === "en" ||
    raw.language === "ja" ||
    raw.language === "ko"
      ? raw.language
      : DEFAULT_PREFERENCES.language;

  return {
    themeMode,
    fontFamily,
    textSize,
    language,
  };
}

export function getLanguageHtmlTag(language: AppLanguage): string {
  if (language === "zh-CN") return "zh-CN";
  if (language === "zh-TW") return "zh-TW";
  if (language === "ja") return "ja";
  if (language === "ko") return "ko";
  return "en";
}

