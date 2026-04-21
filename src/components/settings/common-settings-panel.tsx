"use client";

import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import type { AppLanguage, FontFamily, TextSize, ThemeMode } from "@/lib/preferences";

const FONT_OPTIONS: FontFamily[] = ["system", "serif", "mono"];
const SIZE_OPTIONS: TextSize[] = ["sm", "md", "lg"];
const LANGUAGE_OPTIONS: AppLanguage[] = ["zh-CN", "zh-TW", "en", "ja", "ko"];
const THEME_OPTIONS: ThemeMode[] = ["light", "dark", "system"];

export function CommonSettingsPanel() {
  const { preferences, updatePreferences, resetPreferences, t } = useAppPreferences();

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <p className="af-kicker">{t("settings.common.title", "常用设置")}</p>
      <p className="mt-2 text-sm text-slate-500">
        {t("settings.common.description", "设置会实时生效并保存在本机。")}
      </p>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{t("settings.font", "字体")}</span>
          <select
            className="af-input mt-2"
            value={preferences.fontFamily}
            onChange={(event) => {
              updatePreferences({ fontFamily: event.target.value as FontFamily });
            }}
          >
            {FONT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`settings.font.${option}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{t("settings.textSize", "文字大小")}</span>
          <select
            className="af-input mt-2"
            value={preferences.textSize}
            onChange={(event) => {
              updatePreferences({ textSize: event.target.value as TextSize });
            }}
          >
            {SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`settings.textSize.${option}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{t("settings.language", "语言")}</span>
          <select
            className="af-input mt-2"
            value={preferences.language}
            onChange={(event) => {
              updatePreferences({ language: event.target.value as AppLanguage });
            }}
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`settings.language.${option}`)}
              </option>
            ))}
          </select>
        </label>

        <div className="rounded-2xl border border-white/85 bg-white/55 p-4">
          <span className="text-sm font-semibold text-slate-700">{t("settings.theme", "外观模式")}</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {THEME_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => updatePreferences({ themeMode: option })}
                className={`af-btn px-3 py-1.5 ${
                  preferences.themeMode === option ? "af-btn-primary" : "af-btn-secondary"
                }`}
              >
                {t(`settings.theme.${option}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={resetPreferences} className="af-btn af-btn-secondary">
          {t("settings.reset", "恢复默认")}
        </button>
        <p className="text-sm text-slate-500">{t("settings.preview")}</p>
      </div>
    </section>
  );
}

