import { APP_PREFERENCES_KEY, DEFAULT_PREFERENCES } from "@/lib/preferences";

export function buildPreferenceBootstrapScript(): string {
  const storageKey = JSON.stringify(APP_PREFERENCES_KEY);
  const defaults = JSON.stringify(DEFAULT_PREFERENCES);
  return `(() => {
    try {
      const defaults = ${defaults};
      const stored = JSON.parse(window.localStorage.getItem(${storageKey}) || "null") || {};
      const themeMode = ["light", "dark", "system"].includes(stored.themeMode) ? stored.themeMode : defaults.themeMode;
      const fontFamily = ["system", "serif", "mono"].includes(stored.fontFamily) ? stored.fontFamily : defaults.fontFamily;
      const textSize = ["sm", "md", "lg"].includes(stored.textSize) ? stored.textSize : defaults.textSize;
      const language = ["zh-CN", "zh-TW", "en", "ja", "ko"].includes(stored.language) ? stored.language : defaults.language;
      const resolvedTheme = themeMode === "system"
        ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
        : themeMode;
      const html = document.documentElement;
      html.dataset.afTheme = resolvedTheme;
      html.dataset.afThemeMode = themeMode;
      html.dataset.afFont = fontFamily;
      html.dataset.afTextSize = textSize;
      html.lang = language === "en" ? "en" : language;
    } catch {}
  })();`;
}
