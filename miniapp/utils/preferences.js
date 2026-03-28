const STORAGE_KEY = "antiFomoPreferencesV1";

const DEFAULT_PREFERENCES = {
  themeMode: "system", // light | dark | system
  fontFamily: "system", // system | serif | mono
  textSize: "md", // sm | md | lg
  language: "zh-CN" // zh-CN | zh-TW | en | ja | ko
};

function normalizePreferences(input) {
  const raw = input || {};
  const themeMode =
    raw.themeMode === "light" || raw.themeMode === "dark" || raw.themeMode === "system"
      ? raw.themeMode
      : DEFAULT_PREFERENCES.themeMode;
  const fontFamily =
    raw.fontFamily === "system" || raw.fontFamily === "serif" || raw.fontFamily === "mono"
      ? raw.fontFamily
      : DEFAULT_PREFERENCES.fontFamily;
  const textSize =
    raw.textSize === "sm" || raw.textSize === "md" || raw.textSize === "lg"
      ? raw.textSize
      : DEFAULT_PREFERENCES.textSize;
  const language =
    raw.language === "zh-CN" ||
    raw.language === "zh-TW" ||
    raw.language === "en" ||
    raw.language === "ja" ||
    raw.language === "ko"
      ? raw.language
      : DEFAULT_PREFERENCES.language;
  return { themeMode, fontFamily, textSize, language };
}

function loadPreferences() {
  try {
    const raw = wx.getStorageSync(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return normalizePreferences(raw);
  } catch (_) {
    return DEFAULT_PREFERENCES;
  }
}

function savePreferences(preferences) {
  const normalized = normalizePreferences(preferences);
  wx.setStorageSync(STORAGE_KEY, normalized);
  return normalized;
}

function resolveTheme(themeMode, systemTheme) {
  if (themeMode === "light" || themeMode === "dark") {
    return themeMode;
  }
  return systemTheme === "dark" ? "dark" : "light";
}

function getPreferenceClass(preferences, systemTheme) {
  const normalized = normalizePreferences(preferences);
  const resolvedTheme = resolveTheme(normalized.themeMode, systemTheme);
  return `pref-theme-${resolvedTheme} pref-size-${normalized.textSize} pref-font-${normalized.fontFamily}`;
}

module.exports = {
  DEFAULT_PREFERENCES,
  loadPreferences,
  normalizePreferences,
  savePreferences,
  resolveTheme,
  getPreferenceClass
};

