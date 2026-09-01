import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getArtifactAcceptance,
  getArtifactAcceptancePreview,
  getDecisionContextPackets,
  getDecisionContextPacketsPreview,
  getIterationProgram,
  getIterationProgramPreview,
  initializeArtifactAcceptance,
  initializeDecisionContextPackets,
  initializeIterationProgram,
} from "@/lib/api/competitive-intelligence";

const requestMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  request: requestMock,
}));

describe("decision-context packet API client", () => {
  beforeEach(() => {
    requestMock.mockReset();
    requestMock.mockResolvedValue({});
  });

  it("uses the 2.10.1 preview, persisted, and explicit initialize endpoints", async () => {
    await getDecisionContextPacketsPreview();
    await getDecisionContextPackets();
    await initializeDecisionContextPackets();

    expect(requestMock).toHaveBeenNthCalledWith(1, "/api/product-strategy/decision-context-packets/preview");
    expect(requestMock).toHaveBeenNthCalledWith(2, "/api/product-strategy/decision-context-packets");
    expect(requestMock).toHaveBeenNthCalledWith(3, "/api/product-strategy/decision-context-packets/initialize", {
      method: "POST",
    });
  });

  it("uses the 2.10.2 artifact-acceptance preview, persisted, and explicit initialize endpoints", async () => {
    await getArtifactAcceptancePreview();
    await getArtifactAcceptance();
    await initializeArtifactAcceptance();

    expect(requestMock).toHaveBeenNthCalledWith(1, "/api/product-strategy/artifact-acceptance/preview");
    expect(requestMock).toHaveBeenNthCalledWith(2, "/api/product-strategy/artifact-acceptance");
    expect(requestMock).toHaveBeenNthCalledWith(3, "/api/product-strategy/artifact-acceptance/initialize", {
      method: "POST",
    });
  });

  it("uses the 2.10.3-2.11.7 iteration-program preview, persisted, and explicit initialize endpoints", async () => {
    await getIterationProgramPreview();
    await getIterationProgram();
    await initializeIterationProgram();

    expect(requestMock).toHaveBeenNthCalledWith(1, "/api/product-strategy/iteration-program/preview");
    expect(requestMock).toHaveBeenNthCalledWith(2, "/api/product-strategy/iteration-program");
    expect(requestMock).toHaveBeenNthCalledWith(3, "/api/product-strategy/iteration-program/initialize", {
      method: "POST",
    });
  });
});
