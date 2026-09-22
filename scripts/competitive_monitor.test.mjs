import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { analyzeRegister, renderMarkdown } from "./competitive_monitor.mjs";

const baseRegister = {
  schema_version: "1.0",
  catalog_version: "2.11.4",
  observed_at: "2026-08-31T00:00:00Z",
  expires_at: "2026-09-14T00:00:00Z",
  cadence_days: 7,
  maximum_review_interval_days: 14,
  methodology: ["official_source_only", "human_semantic_review_required"],
  governance: {
    can_auto_update_roadmap: false,
    can_auto_execute: false,
    can_auto_approve_release: false,
    create_review_signal_only: true,
  },
  sources: [{
    product_key: "alpha",
    vendor: "Vendor",
    product_name: "Alpha",
    source_title: "Alpha official",
    source_url: "https://example.com/alpha",
    vendor_claim: "Vendor claim",
    core_capabilities: ["planning"],
    current_model_signal: "Alpha Model",
    anti_fomo_comparison: "Anti-FOMO comparison",
    decision: "build",
    next_step: "Review before building",
    risk: "Vendor claim only",
    baseline_content_sha256: null,
  }],
};

test("monitor reports a fetched official source as review-required when baseline is missing", async () => {
  const report = await analyzeRegister(baseRegister, {
    now: new Date("2026-09-01T00:00:00Z"),
    fetchImpl: async () => new Response("<html><title>Alpha</title><p>Agent capabilities</p></html>", { status: 200 }),
  });

  assert.equal(report.summary.source_count, 1);
  assert.equal(report.summary.fetched_count, 1);
  assert.equal(report.summary.baseline_missing_count, 1);
  assert.equal(report.sources[0].change_status, "baseline_missing");
  assert.equal(report.sources[0].evidence_status, "vendor_claim_unverified");
  assert.equal(report.sources[0].can_auto_update_roadmap, false);
  assert.equal(report.release_gate_mutated, false);
  assert.match(renderMarkdown(report), /Vendor claims are not independent verification/);
});

test("monitor distinguishes unchanged content from failed or stale observations", async () => {
  const normalizedDigest = createHash("sha256").update("Alpha Agent capabilities").digest("hex");
  const unchanged = await analyzeRegister({
    ...baseRegister,
    sources: [{ ...baseRegister.sources[0], baseline_content_sha256: normalizedDigest }],
  }, {
    now: new Date("2026-09-01T00:00:00Z"),
    fetchImpl: async () => new Response("<html><title>Alpha</title><p>Agent capabilities</p></html>", { status: 200 }),
  });
  assert.equal(unchanged.sources[0].change_status, "unchanged");
  assert.equal(unchanged.review_required, false);

  const unavailable = await analyzeRegister(baseRegister, {
    now: new Date("2026-09-20T00:00:00Z"),
    fetchImpl: async () => {
      throw new Error("network unavailable");
    },
  });
  assert.equal(unavailable.summary.failed_count, 1);
  assert.equal(unavailable.summary.stale_count, 1);
  assert.equal(unavailable.sources[0].change_status, "unknown");
  assert.deepEqual(unavailable.sources[0].review_reasons, ["source_observation_stale", "source_fetch_failed"]);
  assert.equal(unavailable.summary.baseline_unset_count, 1);
});

test("a fresh per-source observation cannot clear pending historical semantic review", async () => {
  const normalizedDigest = createHash("sha256").update("Alpha Agent capabilities").digest("hex");
  const register = {
    ...baseRegister,
    sources: [{
      ...baseRegister.sources[0],
      baseline_content_sha256: normalizedDigest,
      observed_at: "2026-09-22T00:00:00Z",
      expires_at: "2026-10-06T00:00:00Z",
      semantic_review: {
        status: "pending",
        claim_observed_at: baseRegister.observed_at,
        claim_expires_at: baseRegister.expires_at,
        reviewed_by: null,
        baseline_accepted: false,
      },
    }],
  };
  const before = JSON.stringify(register);
  const report = await analyzeRegister(register, {
    now: new Date("2026-09-22T01:00:00Z"),
    fetchImpl: async () => new Response("<html><title>Alpha</title><p>Agent capabilities</p></html>", { status: 200 }),
  });
  assert.equal(report.sources[0].observed_at, "2026-09-22T00:00:00Z");
  assert.equal(report.summary.stale_count, 0);
  assert.equal(report.summary.semantic_review_pending_count, 1);
  assert.equal(report.sources[0].change_status, "unchanged");
  assert.deepEqual(report.sources[0].review_reasons, ["human_semantic_review_pending"]);
  assert.equal(report.review_required, true);
  assert.equal(report.sources[0].semantic_review.claim_expires_at, baseRegister.expires_at);
  assert.equal(report.sources[0].semantic_review.reviewed_by, null);
  assert.equal(JSON.stringify(register), before);
});

test("fresh observation preserves changed baseline and unknown fetch failure", async () => {
  const register = {
    ...baseRegister,
    sources: [{
      ...baseRegister.sources[0],
      baseline_content_sha256: "historical-digest",
      observed_at: "2026-09-22T00:00:00Z",
      expires_at: "2026-10-06T00:00:00Z",
      semantic_review: { status: "pending", reviewed_by: null },
    }],
  };
  const changed = await analyzeRegister(register, {
    now: new Date("2026-09-22T01:00:00Z"),
    fetchImpl: async () => new Response("New capabilities", { status: 200 }),
  });
  assert.equal(changed.sources[0].baseline_content_sha256, "historical-digest");
  assert.equal(changed.sources[0].change_status, "content_changed");
  assert.deepEqual(changed.sources[0].review_reasons, ["official_source_content_changed", "human_semantic_review_pending"]);
  const failed = await analyzeRegister(register, {
    now: new Date("2026-09-22T01:00:00Z"),
    fetchImpl: async () => { throw new Error("network unavailable"); },
  });
  assert.equal(failed.sources[0].evidence_status, "unknown");
  assert.equal(failed.sources[0].change_status, "unknown");
  assert.deepEqual(failed.sources[0].review_reasons, ["source_fetch_failed", "human_semantic_review_pending"]);
});
