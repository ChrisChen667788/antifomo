import { describe, expect, it } from "vitest";
import { buildPreferenceBootstrapScript } from "@/lib/preference-bootstrap";
import { APP_PREFERENCES_KEY } from "@/lib/preferences";

describe("preference bootstrap", () => {
  it("applies validated preferences before React hydration", () => {
    const script = buildPreferenceBootstrapScript();
    expect(script).toContain(APP_PREFERENCES_KEY);
    expect(script).toContain("html.dataset.afTheme = resolvedTheme");
    expect(script).toContain("prefers-color-scheme: dark");
    expect(script).not.toContain("</script>");
  });
});
