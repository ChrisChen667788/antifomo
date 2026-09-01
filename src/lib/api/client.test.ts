import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiRequestError,
  isApiRequestError,
  request,
} from "@/lib/api/client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API request errors", () => {
  it("preserves HTTP status so callers can distinguish not-found from unavailable", async () => {
    vi.stubGlobal("window", { localStorage: { getItem: () => null } });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"detail":"missing"}', { status: 404 })),
    );

    const error = await request("/api/items/missing").catch((value: unknown) => value);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect(isApiRequestError(error)).toBe(true);
    if (isApiRequestError(error)) {
      expect(error.status).toBe(404);
      expect(error.body).toContain("missing");
    }
  });

  it("does not classify arbitrary network errors as HTTP response errors", () => {
    expect(isApiRequestError(new TypeError("network unavailable"))).toBe(false);
  });
});
