#!/usr/bin/env node

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_REGISTER = path.join(REPO_ROOT, "config", "competitive-source-register.json");
const DEFAULT_OUTPUT_DIR = path.join(REPO_ROOT, "output", "competitive-monitor");
const MAX_RESPONSE_BYTES = 5 * 1024 * 1024;

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]));
  }
  return value;
}

function canonicalDigest(value) {
  return sha256(JSON.stringify(canonicalize(value)));
}

function normalizeHtml(value) {
  return value
    .replace(/<!--[^]*?-->/g, " ")
    .replace(/<(script|style|svg|noscript)\b[^>]*>[^]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\s+/g, " ")
    .trim();
}

function extractTitle(value) {
  const match = value.match(/<title[^>]*>([^]*?)<\/title>/i);
  return match ? normalizeHtml(match[1]).slice(0, 240) : null;
}

async function fetchOfficialSource(source, fetchImpl) {
  const fetchUrl = source.monitor_url || source.source_url;
  const parsed = new URL(fetchUrl);
  if (parsed.protocol !== "https:") {
    throw new Error("Only HTTPS official sources are allowed");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20_000);
  try {
    const response = await fetchImpl(fetchUrl, {
      headers: {
        "accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
        "user-agent": "Anti-FOMO-Competitive-Monitor/1.0 (+https://github.com/ChrisChen667788/antifomo)",
      },
      redirect: "follow",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.text();
    const bytes = Buffer.byteLength(body);
    if (bytes > MAX_RESPONSE_BYTES) throw new Error(`response exceeds ${MAX_RESPONSE_BYTES} bytes`);
    const normalized = normalizeHtml(body);
    if (!normalized) throw new Error("official source produced no reviewable text");
    return {
      fetch_status: "fetched",
      final_url: response.url || fetchUrl,
      http_status: response.status,
      title: extractTitle(body),
      content_bytes: bytes,
      normalized_text_sha256: sha256(normalized),
      error: null,
    };
  } finally {
    clearTimeout(timer);
  }
}

function sourceAnalysis(source, observation, now) {
  const expiresAt = new Date(source.expires_at);
  const stale = Number.isNaN(expiresAt.getTime()) || now > expiresAt;
  const baseline = source.baseline_content_sha256;
  let changeStatus = "unchanged";
  if (observation.fetch_status !== "fetched") changeStatus = "unknown";
  else if (!baseline) changeStatus = "baseline_missing";
  else if (baseline !== observation.normalized_text_sha256) changeStatus = "content_changed";

  const reviewReasons = [];
  if (stale) reviewReasons.push("source_observation_stale");
  if (changeStatus === "unknown") reviewReasons.push("source_fetch_failed");
  if (changeStatus === "baseline_missing") reviewReasons.push("baseline_missing");
  if (changeStatus === "content_changed") reviewReasons.push("official_source_content_changed");

  return {
    product_key: source.product_key,
    vendor: source.vendor,
    product_name: source.product_name,
    source_title: source.source_title,
    source_url: source.source_url,
    evidence_tier: "vendor_claim",
    evidence_status: stale ? "stale" : observation.fetch_status === "fetched" ? "vendor_claim_unverified" : "unknown",
    vendor_claim_is_not_independent_verification: true,
    observed_at: source.observed_at,
    expires_at: source.expires_at,
    vendor_claim: source.vendor_claim,
    core_capabilities: source.core_capabilities,
    current_model_signal: source.current_model_signal,
    anti_fomo_comparison: source.anti_fomo_comparison,
    decision: source.decision,
    next_step: source.next_step,
    risk: source.risk,
    baseline_content_sha256: baseline,
    observation,
    change_status: changeStatus,
    review_required: reviewReasons.length > 0,
    review_reasons: reviewReasons,
    can_auto_update_roadmap: false,
    can_auto_execute: false,
    can_auto_approve_release: false,
  };
}

export async function analyzeRegister(register, { fetchImpl = fetch, now = new Date() } = {}) {
  const sources = [];
  for (const source of register.sources) {
    let observation;
    try {
      observation = await fetchOfficialSource({ ...source, observed_at: register.observed_at, expires_at: register.expires_at }, fetchImpl);
    } catch (error) {
      observation = {
        fetch_status: "failed",
        final_url: null,
        http_status: null,
        title: null,
        content_bytes: 0,
        normalized_text_sha256: null,
        error: error instanceof Error ? error.message : String(error),
      };
    }
    sources.push(sourceAnalysis({ ...source, observed_at: register.observed_at, expires_at: register.expires_at }, observation, now));
  }

  const summary = {
    source_count: sources.length,
    fetched_count: sources.filter((source) => source.observation.fetch_status === "fetched").length,
    failed_count: sources.filter((source) => source.observation.fetch_status !== "fetched").length,
    changed_count: sources.filter((source) => source.change_status === "content_changed").length,
    baseline_missing_count: sources.filter((source) => source.change_status === "baseline_missing").length,
    stale_count: sources.filter((source) => source.evidence_status === "stale").length,
    review_required_count: sources.filter((source) => source.review_required).length,
  };
  const reportPayload = {
    schema_version: register.schema_version,
    catalog_version: register.catalog_version,
    generated_at: now.toISOString(),
    observed_at: register.observed_at,
    expires_at: register.expires_at,
    cadence_days: register.cadence_days,
    maximum_review_interval_days: register.maximum_review_interval_days,
    methodology: register.methodology,
    governance: register.governance,
    summary,
    sources,
    review_required: summary.review_required_count > 0,
    release_gate_mutated: false,
    production_status: "not_authorized",
  };
  return { ...reportPayload, report_digest: canonicalDigest(reportPayload) };
}

function escapeCell(value) {
  return String(value ?? "-").replaceAll("|", "\\|").replaceAll("\n", " ");
}

export function renderMarkdown(report) {
  const lines = [
    "# Anti-FOMO Competitive Intelligence Monitor",
    "",
    `Generated: \`${report.generated_at}\``,
    `Catalog: \`${report.catalog_version}\` · Report digest: \`${report.report_digest}\``,
    "",
    "> This report records official-source availability and change signals. Vendor claims are not independent verification. It cannot change the roadmap, execute tools, or approve a release.",
    "",
    "## Summary",
    "",
    `- Sources: ${report.summary.source_count}`,
    `- Fetched: ${report.summary.fetched_count}`,
    `- Failed: ${report.summary.failed_count}`,
    `- Changed: ${report.summary.changed_count}`,
    `- Missing baseline: ${report.summary.baseline_missing_count}`,
    `- Stale: ${report.summary.stale_count}`,
    `- Human review required: ${report.summary.review_required_count}`,
    "",
    "## Source review matrix",
    "",
    "| Product | Evidence | Change | Decision | Core comparison | Review reasons |",
    "| --- | --- | --- | --- | --- | --- |",
  ];
  for (const source of report.sources) {
    lines.push(`| [${escapeCell(source.product_name)}](${source.source_url}) | ${escapeCell(source.evidence_status)} | ${escapeCell(source.change_status)} | ${escapeCell(source.decision)} | ${escapeCell(source.anti_fomo_comparison)} | ${escapeCell(source.review_reasons.join(", ") || "none")} |`);
  }
  lines.push(
    "",
    "## Governance",
    "",
    "- Human semantic review is required before changing a competitor claim or roadmap decision.",
    "- No source fetch can authorize execution, artifact acceptance, release approval, or production promotion.",
    "- Office, visual, identity, customer, performance, shadow, drift, rollback, and independent-audit evidence remain separate gates.",
    "",
  );
  return lines.join("\n");
}

function parseArgs(argv) {
  const options = { register: DEFAULT_REGISTER, outputDir: DEFAULT_OUTPUT_DIR, strict: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--register") options.register = path.resolve(argv[++index]);
    else if (arg === "--output-dir") options.outputDir = path.resolve(argv[++index]);
    else if (arg === "--strict") options.strict = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  return options;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const register = JSON.parse(await readFile(options.register, "utf8"));
  const report = await analyzeRegister(register);
  await mkdir(options.outputDir, { recursive: true });
  await writeFile(path.join(options.outputDir, "competitive-monitor-report.json"), `${JSON.stringify(report, null, 2)}\n`);
  await writeFile(path.join(options.outputDir, "competitive-monitor-report.md"), renderMarkdown(report));
  process.stdout.write(`${JSON.stringify({ report_digest: report.report_digest, summary: report.summary })}\n`);
  if (options.strict && report.summary.failed_count > 0) process.exitCode = 2;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
