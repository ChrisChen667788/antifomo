import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppPreferencesProvider, useAppPreferences } from "@/components/settings/app-preferences-provider";
import { APP_PREFERENCES_KEY } from "@/lib/preferences";

function PreferenceProbe() {
  const { preferences, resolvedTheme, updatePreferences } = useAppPreferences();
  return (
    <button type="button" onClick={() => updatePreferences({ themeMode: "light", language: "en" })}>
      {preferences.themeMode}:{resolvedTheme}:{preferences.language}
    </button>
  );
}

describe("AppPreferencesProvider", () => {
  beforeEach(() => {
    const values = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        clear: () => values.clear(),
        getItem: (key: string) => values.get(key) ?? null,
        key: (index: number) => Array.from(values.keys())[index] ?? null,
        get length() {
          return values.size;
        },
        removeItem: (key: string) => values.delete(key),
        setItem: (key: string, value: string) => values.set(key, String(value)),
      },
    });
    document.documentElement.removeAttribute("data-af-theme");
    document.documentElement.removeAttribute("data-af-theme-mode");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("dark"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it("resolves the system theme and keeps DOM theme attributes in sync", async () => {
    window.localStorage.setItem(
      APP_PREFERENCES_KEY,
      JSON.stringify({ themeMode: "system", fontFamily: "serif", textSize: "lg", language: "zh-TW" }),
    );

    render(
      <AppPreferencesProvider>
        <PreferenceProbe />
      </AppPreferencesProvider>,
    );

    expect(await screen.findByRole("button")).toHaveTextContent("system:dark:zh-TW");
    await waitFor(() => expect(document.documentElement.dataset.afTheme).toBe("dark"));
    expect(document.documentElement.dataset.afThemeMode).toBe("system");
    expect(document.documentElement.dataset.afFont).toBe("serif");
    expect(document.documentElement.dataset.afTextSize).toBe("lg");
    expect(document.documentElement.lang).toBe("zh-TW");

    await act(async () => screen.getByRole("button").click());
    await waitFor(() => expect(screen.getByRole("button")).toHaveTextContent("light:light:en"));
    expect(document.documentElement.dataset.afTheme).toBe("light");
    expect(document.documentElement.lang).toBe("en");
  });
});
