#!/usr/bin/env node
/** Export a hash-verified, selected local diagnostic sample for review. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const argv = process.argv.slice(2);
function option(name, fallback) {
  const i = argv.indexOf(name);
  return i === -1 ? fallback : argv[i + 1];
}
const api = option("--api", "http://127.0.0.1:8000");
assert(["127.0.0.1", "localhost", "[::1]"].includes(new URL(api).hostname), "Only local evidence can be exported");
const receiptKey = option("--receipt", "");
assert(receiptKey, "Pass --receipt with an explicitly selected Office receipt key");
const output = path.resolve(option("--output", "output/office-evidence-bundle"));
const response = await fetch(`${api}/api/product-strategy/office-evidence-receipts`);
assert(response.ok, `Office API ${response.status}`);
const landscape = await response.json();
const receipt = landscape.receipts.find(row => row.receipt_key === receiptKey);
assert(receipt, "Selected receipt was not found");
const storageRoot = fs.realpathSync(path.resolve(option("--storage-root", ".storage/product-strategy")));
const source = path.resolve(storageRoot, receipt.storage_ref);
assert(source.startsWith(`${storageRoot}${path.sep}`), "Invalid storage reference");
const receiptDir = path.dirname(source);
const pdfCandidates = ["render/manual-office-export.pdf", "render/source.pdf"];
const sha = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const files = [];
const planned = [{ source, filename: `office-source${path.extname(source)}`, hash: receipt.file_sha256 }];
if (receipt.rendered_pdf_sha256) {
  const pdf = pdfCandidates.map(p => path.join(receiptDir, p)).find(p => fs.existsSync(p));
  assert(pdf, "Rendered PDF is missing");
  planned.push({ source: pdf, filename: "office-rendered.pdf", hash: receipt.rendered_pdf_sha256 });
}
for (const page of receipt.rendered_pages) {
  assert.equal(path.basename(page.file_name), page.file_name);
  planned.push({ source: path.join(receiptDir, "render", page.file_name), filename: `pages/${page.file_name}`, hash: page.sha256 });
}
// Verify every byte before exporting any part of the bundle.
for (const entry of planned) {
  assert(fs.realpathSync(entry.source).startsWith(`${storageRoot}${path.sep}`), "Evidence symlink escapes storage");
  assert.equal(sha(fs.readFileSync(entry.source)), entry.hash, `Digest mismatch: ${entry.filename}`);
}
fs.mkdirSync(output, { recursive: true });
for (const entry of planned) {
  const target = path.join(output, entry.filename);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(entry.source, target);
  files.push({ file: entry.filename, sha256: entry.hash, size_bytes: fs.statSync(target).size });
}
const manifest = {
  evidence_version: "2.10.6", exported_at: new Date().toISOString(),
  purpose: "Selected local Office evidence for review, not an accepted customer deliverable",
  source_kind: "selected_local_evidence", physical_device_test: false,
  office_export_provenance: "receipt_metadata_only; uploaded_pdf_is_not_independent_proof",
  visual_review_status: receipt.visual_evidence_status,
  named_human_review: receipt.human_review_status, acceptance_status: "hold",
  known_layout_findings: [],
  receipt, files,
};
fs.writeFileSync(path.join(output, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(JSON.stringify({ output, file_count: files.length, receipt_digest: receipt.receipt_digest, visual_review_status: manifest.visual_review_status }));
