"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addDecisionSource,
  buildDecisionSemanticIndex,
  compileDecisionSections,
  createDecisionClaim,
  createDecisionContract,
  createDecisionNotebook,
  generateDecisionArtifact,
  getDecisionNotebook,
  getDecisionReadiness,
  getDecisionReleaseProgram,
  getDecisionStudioOverview,
  previewDecisionDataActivation,
  runDecisionDataActivation,
  searchDecisionNotebook,
  upsertDecisionSection,
  verifyDecisionSource,
} from "@/lib/api/decision-studio";
import type {
  DecisionArtifactType,
  DecisionActivationPreview,
  DecisionNotebookDetail,
  DecisionReadiness,
  DecisionReleaseProgram,
  DecisionSearchHit,
  DecisionSearchResult,
  DecisionStudioOverview,
} from "@/lib/api/type-contracts/decision-studio";
import { DecisionProgramPanel } from "@/components/decision-studio/decision-program-panel";


type StudioTab = "evidence" | "contract" | "claims" | "artifacts" | "governance" | "program" | "readiness";

const TABS: Array<{ key: StudioTab; label: string }> = [
  { key: "evidence", label: "证据检索" },
  { key: "contract", label: "正式文档" },
  { key: "claims", label: "Claim Graph" },
  { key: "artifacts", label: "多形态产物" },
  { key: "governance", label: "知识与 Skill" },
  { key: "program", label: "版本收口" },
  { key: "readiness", label: "发布门禁" },
];

const ARTIFACT_TYPES: Array<{ value: DecisionArtifactType; label: string }> = [
  { value: "executive_brief", label: "决策摘要" },
  { value: "mind_map", label: "思维导图" },
  { value: "data_table", label: "证据数据表" },
  { value: "slide_outline", label: "PPT 大纲" },
  { value: "infographic_spec", label: "信息图规格" },
  { value: "audio_script", label: "音频脚本" },
];

function statusClass(status: string): string {
  if (["pass", "ready", "accepted", "approved", "verified"].includes(status)) {
    return "border-[color-mix(in_srgb,var(--af-success)_38%,var(--af-border-subtle))] text-[var(--af-success)]";
  }
  if (["blocked", "stale", "rejected", "revoked", "expired"].includes(status)) {
    return "border-[color-mix(in_srgb,var(--af-danger)_38%,var(--af-border-subtle))] text-[var(--af-danger)]";
  }
  return "border-[color-mix(in_srgb,var(--af-warning)_38%,var(--af-border-subtle))] text-[var(--af-warning)]";
}

function StatusPill({ status, label }: { status: string; label?: string }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(status)}`}>
      {label ?? status}
    </span>
  );
}

function locatorLabel(locator: Record<string, unknown>): string {
  const parts = [
    locator.page ? `第 ${locator.page} 页` : "",
    locator.paragraph ? `第 ${locator.paragraph} 段` : "",
    locator.start_seconds !== null && locator.start_seconds !== undefined
      ? `${locator.start_seconds}s`
      : "",
  ].filter(Boolean);
  return parts.join(" · ") || "段落定位可用";
}

function shortHash(value: string): string {
  return value ? `${value.slice(0, 8)}...${value.slice(-6)}` : "-";
}

export function DecisionStudioWorkspace() {
  const [overview, setOverview] = useState<DecisionStudioOverview | null>(null);
  const [detail, setDetail] = useState<DecisionNotebookDetail | null>(null);
  const [selectedNotebookId, setSelectedNotebookId] = useState("");
  const [tab, setTab] = useState<StudioTab>("evidence");
  const [readiness, setReadiness] = useState<DecisionReadiness | null>(null);
  const [releaseProgram, setReleaseProgram] = useState<DecisionReleaseProgram | null>(null);
  const [activationPreview, setActivationPreview] = useState<DecisionActivationPreview | null>(null);
  const [working, setWorking] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const [notebookName, setNotebookName] = useState("");
  const [activationNotebookName, setActivationNotebookName] = useState("现有知识与研报");
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourceContent, setSourceContent] = useState("");
  const [includedSourceIds, setIncludedSourceIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [strictSemantic, setStrictSemantic] = useState(true);
  const [retrievalMode, setRetrievalMode] = useState<"semantic" | "hybrid" | "lexical">("hybrid");
  const [searchResult, setSearchResult] = useState<DecisionSearchResult | null>(null);
  const [selectedHit, setSelectedHit] = useState<DecisionSearchHit | null>(null);

  const [claimKey, setClaimKey] = useState("");
  const [claimText, setClaimText] = useState("");
  const [claimCritical, setClaimCritical] = useState(false);
  const [policyPackId, setPolicyPackId] = useState("");
  const [contractTitle, setContractTitle] = useState("");
  const [artifactType, setArtifactType] = useState<DecisionArtifactType>("executive_brief");
  const [artifactTitle, setArtifactTitle] = useState("");

  const run = useCallback(async <T,>(label: string, action: () => Promise<T>): Promise<T | null> => {
    setWorking(label);
    setError("");
    setNotice("");
    try {
      return await action();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      return null;
    } finally {
      setWorking("");
    }
  }, []);

  const refreshOverview = useCallback(async () => {
    const payload = await run("加载工作台", getDecisionStudioOverview);
    if (!payload) return;
    setOverview(payload);
    if (!selectedNotebookId && payload.notebooks[0]) {
      setSelectedNotebookId(payload.notebooks[0].id);
    }
    if (!policyPackId && payload.policy_packs[0]) {
      setPolicyPackId(payload.policy_packs[0].id);
    }
  }, [policyPackId, run, selectedNotebookId]);

  const refreshDetail = useCallback(async () => {
    if (!selectedNotebookId) {
      setDetail(null);
      return;
    }
    const payload = await run("加载 Notebook", () => getDecisionNotebook(selectedNotebookId));
    if (!payload) return;
    setDetail(payload);
    setIncludedSourceIds((current) =>
      current.length ? current.filter((id) => payload.sources.some((source) => source.id === id)) : payload.sources.map((source) => source.id),
    );
  }, [run, selectedNotebookId]);

  const refreshReadiness = useCallback(async () => {
    const payload = await run("扫描发布门禁", () =>
      Promise.all([
        getDecisionReadiness(selectedNotebookId || undefined),
        getDecisionReleaseProgram(),
      ]),
    );
    if (!payload) return;
    setReadiness(payload[0]);
    setReleaseProgram(payload[1]);
  }, [run, selectedNotebookId]);

  useEffect(() => {
    void refreshOverview();
  }, [refreshOverview]);

  useEffect(() => {
    void refreshDetail();
    setSearchResult(null);
    setSelectedHit(null);
  }, [refreshDetail]);

  useEffect(() => {
    if (tab === "readiness") void refreshReadiness();
  }, [refreshReadiness, tab]);

  const selectedPolicyPack = useMemo(
    () => overview?.policy_packs.find((pack) => pack.id === policyPackId) ?? null,
    [overview, policyPackId],
  );
  const acceptedClaims = detail?.claims.filter((claim) => claim.status === "accepted") ?? [];

  async function handleCreateNotebook() {
    const name = notebookName.trim();
    if (!name) return;
    const created = await run("创建 Notebook", () => createDecisionNotebook({ name, description: "Decision Studio 工作台" }));
    if (!created) return;
    setNotebookName("");
    setSelectedNotebookId(created.id);
    setNotice("Notebook 已创建。");
    await refreshOverview();
  }

  async function handlePreviewActivation() {
    const payload = await run("扫描现有知识与研报", () =>
      previewDecisionDataActivation({
        notebook_name: activationNotebookName.trim() || "现有知识与研报",
        notebook_id: selectedNotebookId || null,
      }),
    );
    if (!payload) return;
    setActivationPreview(payload);
    setNotice(payload.candidate_count ? `发现 ${payload.candidate_count} 条可激活真实来源。` : "没有找到可激活来源。");
  }

  async function handleRunActivation() {
    if (!activationPreview?.candidate_count) return;
    const result = await run("激活现有数据", () =>
      runDecisionDataActivation({
        notebook_name: activationNotebookName.trim() || "现有知识与研报",
        notebook_id: selectedNotebookId || null,
      }),
    );
    if (!result) return;
    setSelectedNotebookId(result.notebook.id);
    setActivationPreview(null);
    setNotice(
      `激活完成：新增 ${result.metrics.created_source_count}，更新 ${result.metrics.updated_source_count}，复用 ${result.metrics.unchanged_source_count}。`,
    );
    await refreshOverview();
  }

  async function handleAddSource() {
    if (!selectedNotebookId || !sourceTitle.trim() || !sourceContent.trim()) return;
    const result = await run("解析来源", () =>
      addDecisionSource(selectedNotebookId, {
        title: sourceTitle.trim(),
        file_name: `${sourceTitle.trim()}.txt`,
        mime_type: "text/plain",
        content: sourceContent,
      }),
    );
    if (!result) return;
    setSourceTitle("");
    setSourceContent("");
    setNotice(`来源已解析为 ${result.source.current_passage_count} 个段落。`);
    await refreshDetail();
    await refreshOverview();
  }

  async function handleBuildIndex() {
    if (!selectedNotebookId) return;
    const result = await run("构建真实语义索引", () => buildDecisionSemanticIndex(selectedNotebookId));
    if (!result) return;
    setNotice(`已用 ${result.model} 索引 ${result.indexed_passage_count} 个段落，维度 ${result.dimension}。`);
    await refreshDetail();
  }

  async function handleVerifySource(sourceId: string) {
    const result = await run("验证可信来源", () => verifyDecisionSource(sourceId, "studio-user"));
    if (!result) return;
    setNotice("来源已验证，关键 Claim 可以引用其当前修订。");
    await refreshDetail();
  }

  async function handleSearch() {
    if (!selectedNotebookId || !query.trim()) return;
    const result = await run("检索证据", () =>
      searchDecisionNotebook(selectedNotebookId, {
        query: query.trim(),
        included_source_ids: includedSourceIds,
        limit: 12,
        require_semantic: strictSemantic && retrievalMode !== "lexical",
        retrieval_mode: retrievalMode,
      }),
    );
    if (result) setSearchResult(result);
  }

  function selectHit(hit: DecisionSearchHit) {
    setSelectedHit(hit);
    setClaimText(hit.text);
    setClaimKey(`claim_${Date.now().toString(36)}`);
  }

  async function handleCreateClaim() {
    if (!selectedNotebookId || !selectedHit || !claimKey.trim() || !claimText.trim()) return;
    const created = await run("登记 Claim", () =>
      createDecisionClaim(selectedNotebookId, {
        claim_key: claimKey.trim(),
        text: claimText.trim(),
        criticality: claimCritical ? "critical" : "normal",
        status: "accepted",
        passage_ids: [selectedHit.passage_id],
        facts: {},
        owner_label: "studio-user",
      }),
    );
    if (!created) return;
    setSelectedHit(null);
    setClaimKey("");
    setClaimText("");
    setClaimCritical(false);
    setNotice("Claim 已通过当前来源修订校验并登记。");
    await refreshDetail();
  }

  async function handleCreateContract() {
    if (!selectedNotebookId || !policyPackId || !contractTitle.trim()) return;
    const created = await run("创建正式文档合同", () =>
      createDecisionContract(selectedNotebookId, {
        policy_pack_id: policyPackId,
        title: contractTitle.trim(),
      }),
    );
    if (!created) return;
    setContractTitle("");
    setNotice(`合同已创建，当前有 ${created.gap_count} 项资料缺口。`);
    await refreshDetail();
  }

  async function handleCompile() {
    if (!selectedNotebookId || !acceptedClaims.length) return;
    const section = await run("登记章节依赖", () =>
      upsertDecisionSection(selectedNotebookId, {
        section_key: "studio_decision_summary",
        title: "决策摘要与关键依据",
        claim_ids: acceptedClaims.map((claim) => claim.id),
        contract_id: detail?.contracts[0]?.id,
      }),
    );
    if (!section) return;
    const compiled = await run("增量编译章节", () => compileDecisionSections(selectedNotebookId));
    if (!compiled) return;
    setNotice(
      compiled.status === "pass"
        ? `编译完成：新建 ${compiled.built_section_keys.length}，复用 ${compiled.skipped_section_keys.length}。`
        : `编译阻断：${compiled.blocked_section_keys.join("、") || "存在跨章冲突"}。`,
    );
    await refreshDetail();
  }

  async function handleGenerateArtifact() {
    if (!selectedNotebookId || !artifactTitle.trim()) return;
    const artifact = await run("生成证据绑定产物", () =>
      generateDecisionArtifact(selectedNotebookId, {
        artifact_type: artifactType,
        title: artifactTitle.trim(),
      }),
    );
    if (!artifact) return;
    setArtifactTitle("");
    setNotice(artifact.reused ? "依赖未变化，复用现有产物。" : "已生成新产物并记录 Claim/来源修订血缘。");
    await refreshDetail();
  }

  return (
    <div className="space-y-4">
      <section className="af-glass rounded-lg px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
            <strong className="text-[var(--af-text-primary)]">Decision Studio</strong>
            <StatusPill status={overview?.embedding.enabled ? "ready" : "blocked"} label={overview?.embedding.model ?? "模型未加载"} />
            <span className="text-xs text-[var(--af-text-tertiary)]">{overview?.version ?? "2.2.0-development"}</span>
          </div>
          <div className="flex items-center gap-2">
            {readiness ? <StatusPill status={readiness.overall_status} label={`${readiness.readiness_score}/100`} /> : null}
            <button className="af-btn af-btn-secondary px-3 py-1.5 text-xs" onClick={() => void refreshOverview()} disabled={Boolean(working)}>
              刷新
            </button>
          </div>
        </div>
        {working ? <p className="mt-2 text-xs text-[var(--af-info)]">{working}...</p> : null}
        {notice ? <p className="mt-2 text-xs text-[var(--af-success)]">{notice}</p> : null}
        {error ? <p className="mt-2 break-words text-xs text-[var(--af-danger)]">{error}</p> : null}
      </section>

      <div className="grid min-w-0 gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="af-glass self-start rounded-lg p-3 lg:sticky lg:top-24">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">Notebook</h2>
            <span className="text-xs text-[var(--af-text-tertiary)]">{overview?.notebooks.length ?? 0}</span>
          </div>
          <div className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
            {overview?.notebooks.map((notebook) => (
              <button
                key={notebook.id}
                type="button"
                onClick={() => setSelectedNotebookId(notebook.id)}
                className={`w-full rounded-md border px-3 py-2 text-left ${
                  selectedNotebookId === notebook.id
                    ? "border-[var(--af-border-strong)] bg-[var(--af-surface-selected)]"
                    : "border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)]"
                }`}
              >
                <span className="block truncate text-sm font-medium text-[var(--af-text-primary)]">{notebook.name}</span>
                <span className="mt-1 block text-[11px] text-[var(--af-text-tertiary)]">
                  {notebook.source_count} 来源 · {notebook.artifact_count} 产物
                </span>
              </button>
            ))}
            {!overview?.notebooks.length ? (
              <p className="rounded-md border border-dashed border-[var(--af-border-subtle)] px-3 py-5 text-center text-xs text-[var(--af-text-tertiary)]">
                暂无 Notebook
              </p>
            ) : null}
          </div>
          <div className="mt-3 space-y-2 border-t border-[var(--af-border-subtle)] pt-3">
            <input className="af-input py-2 text-sm" value={notebookName} onChange={(event) => setNotebookName(event.target.value)} placeholder="新 Notebook 名称" />
            <button className="af-btn af-btn-primary w-full py-2 text-sm" onClick={() => void handleCreateNotebook()} disabled={Boolean(working) || !notebookName.trim()}>
              创建 Notebook
            </button>
          </div>
          <div className="mt-3 space-y-2 border-t border-[var(--af-border-subtle)] pt-3">
            <div className="flex items-center justify-between gap-2">
              <strong className="text-xs text-[var(--af-text-secondary)]">真实数据激活</strong>
              {activationPreview ? <StatusPill status={activationPreview.status} label={`${activationPreview.candidate_count} 条`} /> : null}
            </div>
            <input
              className="af-input py-2 text-sm"
              value={activationNotebookName}
              onChange={(event) => setActivationNotebookName(event.target.value)}
              placeholder="激活 Notebook 名称"
            />
            <button className="af-btn af-btn-secondary w-full py-2 text-xs" onClick={() => void handlePreviewActivation()} disabled={Boolean(working)}>
              扫描可激活数据
            </button>
            {activationPreview?.candidate_count ? (
              <button className="af-btn af-btn-primary w-full py-2 text-xs" onClick={() => void handleRunActivation()} disabled={Boolean(working)}>
                {selectedNotebookId ? "激活到当前 Notebook" : "创建并激活"}
              </button>
            ) : null}
            {activationPreview ? (
              <p className="text-[11px] leading-5 text-[var(--af-text-tertiary)]">
                知识 {activationPreview.source_type_counts.knowledge_entry ?? 0} · 研报 {activationPreview.source_type_counts.research_job ?? 0} · 重复 {activationPreview.state_counts.duplicate_input ?? 0}
              </p>
            ) : null}
          </div>
        </aside>

        <main className="min-w-0 space-y-4">
          <div className="flex gap-1 overflow-x-auto rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-1">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={`shrink-0 rounded-md px-3 py-2 text-xs font-semibold ${
                  tab === item.key
                    ? "bg-[var(--af-accent)] text-[var(--af-text-inverse)]"
                    : "text-[var(--af-text-secondary)] hover:bg-[var(--af-surface-hover)]"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {!detail && tab !== "readiness" && tab !== "program" ? (
            <section className="af-glass rounded-lg px-5 py-14 text-center text-sm text-[var(--af-text-tertiary)]">
              创建或选择一个 Notebook
            </section>
          ) : null}

          {detail && tab === "evidence" ? (
            <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.35fr)]">
              <section className="af-glass rounded-lg p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">来源与修订</h2>
                  <button className="af-btn af-btn-secondary px-3 py-1.5 text-xs" onClick={() => void handleBuildIndex()} disabled={Boolean(working) || !detail.sources.length}>
                    构建语义索引
                  </button>
                </div>
                <div className="space-y-2">
                  {detail.sources.map((source) => (
                    <div key={source.id} className="flex items-start gap-2 rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                      <input
                        type="checkbox"
                        className="mt-1"
                        aria-label={`选择来源 ${source.title}`}
                        checked={includedSourceIds.includes(source.id)}
                        onChange={(event) =>
                          setIncludedSourceIds((current) =>
                            event.target.checked ? [...current, source.id] : current.filter((id) => id !== source.id),
                          )
                        }
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <strong className="truncate text-xs text-[var(--af-text-primary)]">{source.title}</strong>
                          <StatusPill status={source.trust_status} />
                        </span>
                        <span className="mt-1 block text-[11px] text-[var(--af-text-tertiary)]">
                          r{source.current_revision_number} · {source.current_parser} · {source.current_passage_count} 段 · {shortHash(source.current_content_hash)}
                        </span>
                      </span>
                      {source.trust_status !== "verified" ? (
                        <button type="button" className="af-btn af-btn-secondary shrink-0 px-2 py-1 text-[11px]" onClick={() => void handleVerifySource(source.id)} disabled={Boolean(working)}>
                          验证
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
                <div className="mt-4 space-y-2 border-t border-[var(--af-border-subtle)] pt-4">
                  <input className="af-input" value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} placeholder="来源标题" />
                  <textarea className="af-input min-h-28 resize-y" value={sourceContent} onChange={(event) => setSourceContent(event.target.value)} placeholder="粘贴文本资料" />
                  <button className="af-btn af-btn-primary w-full" onClick={() => void handleAddSource()} disabled={Boolean(working) || !sourceTitle.trim() || !sourceContent.trim()}>
                    解析并加入来源
                  </button>
                </div>
              </section>

              <section className="af-glass min-w-0 rounded-lg p-4">
                <div className="flex flex-col gap-2 sm:flex-row">
                  <input className="af-input flex-1" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void handleSearch(); }} placeholder="检索问题或关键事实" />
                  <button className="af-btn af-btn-primary shrink-0" onClick={() => void handleSearch()} disabled={Boolean(working) || !query.trim() || !includedSourceIds.length}>
                    检索
                  </button>
                </div>
                <label className="mt-2 flex items-center gap-2 text-xs text-[var(--af-text-secondary)]">
                  <input type="checkbox" checked={strictSemantic} onChange={(event) => setStrictSemantic(event.target.checked)} />
                  严格语义模式
                </label>
                <div className="mt-2 inline-flex rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] p-0.5">
                  {(["semantic", "hybrid", "lexical"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setRetrievalMode(mode)}
                      className={`rounded px-2.5 py-1 text-[11px] ${retrievalMode === mode ? "bg-[var(--af-accent)] text-[var(--af-text-inverse)]" : "text-[var(--af-text-secondary)]"}`}
                    >
                      {mode === "semantic" ? "语义" : mode === "hybrid" ? "混合 RRF" : "词法"}
                    </button>
                  ))}
                </div>
                {searchResult ? (
                  <div className="mt-3 flex items-center gap-2 text-xs">
                    <StatusPill status={searchResult.status} label={searchResult.mode} />
                    <span className="text-[var(--af-text-tertiary)]">{searchResult.model || "无真实向量，显式词法降级"}</span>
                  </div>
                ) : null}
                <div className="mt-3 space-y-2">
                  {searchResult?.hits.map((hit) => (
                    <button key={hit.passage_id} type="button" onClick={() => selectHit(hit)} className="w-full rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3 text-left hover:border-[var(--af-border-strong)]">
                      <span className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--af-text-tertiary)]">
                        <strong className="text-[var(--af-text-secondary)]">{hit.source_title} · r{hit.revision_number}</strong>
                        <span>{hit.score.toFixed(3)} · {locatorLabel(hit.locator)}</span>
                      </span>
                      <span className="mt-2 block text-sm leading-6 text-[var(--af-text-primary)]">{hit.text}</span>
                    </button>
                  ))}
                  {searchResult && !searchResult.hits.length ? <p className="py-8 text-center text-sm text-[var(--af-text-tertiary)]">当前来源范围内无命中</p> : null}
                </div>
                {selectedHit ? (
                  <div className="mt-4 space-y-2 border-t border-[var(--af-border-subtle)] pt-4">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">登记为 Claim</h3>
                      <span className="text-[11px] text-[var(--af-text-tertiary)]">{selectedHit.source_title} · {locatorLabel(selectedHit.locator)}</span>
                    </div>
                    <input className="af-input" value={claimKey} onChange={(event) => setClaimKey(event.target.value)} placeholder="Claim key" />
                    <textarea className="af-input min-h-20 resize-y" value={claimText} onChange={(event) => setClaimText(event.target.value)} />
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <label className="flex items-center gap-2 text-xs text-[var(--af-text-secondary)]">
                        <input type="checkbox" checked={claimCritical} onChange={(event) => setClaimCritical(event.target.checked)} />
                        关键 Claim
                      </label>
                      <button className="af-btn af-btn-primary px-4 py-2 text-xs" onClick={() => void handleCreateClaim()} disabled={Boolean(working)}>
                        绑定段落并接受
                      </button>
                    </div>
                  </div>
                ) : null}
              </section>
            </div>
          ) : null}

          {detail && tab === "contract" ? (
            <section className="af-glass rounded-lg p-4">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                <select className="af-input" value={policyPackId} onChange={(event) => setPolicyPackId(event.target.value)}>
                  {overview?.policy_packs.map((pack) => <option key={pack.id} value={pack.id}>{pack.title}</option>)}
                </select>
                <input className="af-input" value={contractTitle} onChange={(event) => setContractTitle(event.target.value)} placeholder="正式文档名称" />
                <button className="af-btn af-btn-primary" onClick={() => void handleCreateContract()} disabled={Boolean(working) || !contractTitle.trim()}>
                  创建合同
                </button>
              </div>
              {selectedPolicyPack ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--af-text-tertiary)]">
                  <span>{selectedPolicyPack.authority}</span>
                  <span>·</span>
                  <span>{selectedPolicyPack.schema.sections?.length ?? 0} 章</span>
                  <span>·</span>
                  <span>{selectedPolicyPack.schema.fields?.length ?? 0} 字段</span>
                  <span>·</span>
                  <span>v{selectedPolicyPack.version}</span>
                </div>
              ) : null}
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {detail.contracts.map((contract) => (
                  <article key={contract.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{contract.title}</h3>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{contract.document_kind} · r{contract.revision}</p>
                      </div>
                      <StatusPill status={contract.gap_count ? "blocked" : "pass"} label={`${contract.completion_percent}%`} />
                    </div>
                    <p className="mt-3 text-sm text-[var(--af-text-secondary)]">资料缺口 {contract.gap_count} · 假设 {contract.assumptions.length} · 公式 {contract.calculations.length}</p>
                    <div className="mt-3 max-h-36 space-y-1 overflow-y-auto text-xs text-[var(--af-text-tertiary)]">
                      {contract.gaps.slice(0, 12).map((gap, index) => <p key={`${String(gap.field_key)}-${index}`}>{String(gap.section)} · {String(gap.label)}</p>)}
                    </div>
                  </article>
                ))}
                {!detail.contracts.length ? <p className="col-span-full py-12 text-center text-sm text-[var(--af-text-tertiary)]">尚未创建正式文档合同</p> : null}
              </div>
            </section>
          ) : null}

          {detail && tab === "claims" ? (
            <section className="af-glass rounded-lg p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">Claim Graph 与章节编译</h2>
                  <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{acceptedClaims.length} accepted · {detail.sections.length} sections</p>
                </div>
                <button className="af-btn af-btn-primary" onClick={() => void handleCompile()} disabled={Boolean(working) || !acceptedClaims.length}>
                  增量编译
                </button>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {detail.claims.map((claim) => (
                  <article key={claim.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="text-xs text-[var(--af-text-primary)]">{claim.claim_key}</strong>
                      <StatusPill status={claim.status} />
                      {claim.criticality === "critical" ? <StatusPill status="watch" label="critical" /> : null}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{claim.text}</p>
                    <p className="mt-2 text-[11px] text-[var(--af-text-tertiary)]">{claim.citations.length} citations · {claim.depends_on_claim_ids.length} dependencies</p>
                  </article>
                ))}
              </div>
              <div className="mt-4 space-y-3 border-t border-[var(--af-border-subtle)] pt-4">
                {detail.sections.map((section) => (
                  <article key={section.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] p-4">
                    <div className="flex items-center justify-between gap-2">
                      <strong className="text-sm text-[var(--af-text-primary)]">{section.title}</strong>
                      <StatusPill status={section.status} label={`${section.status} · build ${section.build_version}`} />
                    </div>
                    {section.content ? <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-6 text-[var(--af-text-secondary)]">{section.content}</pre> : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {detail && tab === "artifacts" ? (
            <section className="af-glass rounded-lg p-4">
              <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)_auto]">
                <select className="af-input" value={artifactType} onChange={(event) => setArtifactType(event.target.value as DecisionArtifactType)}>
                  {ARTIFACT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
                <input className="af-input" value={artifactTitle} onChange={(event) => setArtifactTitle(event.target.value)} placeholder="产物名称" />
                <button className="af-btn af-btn-primary" onClick={() => void handleGenerateArtifact()} disabled={Boolean(working) || !artifactTitle.trim()}>
                  生成产物
                </button>
              </div>
              <div className="mt-4 space-y-3">
                {detail.artifacts.map((artifact) => (
                  <article key={artifact.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{artifact.title}</h3>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{artifact.artifact_type} · {artifact.claim_ids.length} Claims · {artifact.source_revision_ids.length} revisions</p>
                      </div>
                      <StatusPill status={artifact.stale ? "stale" : artifact.status} />
                    </div>
                    <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-[var(--af-surface-inset)] p-3 font-mono text-[11px] leading-5 text-[var(--af-text-secondary)]">{JSON.stringify(artifact.content, null, 2)}</pre>
                  </article>
                ))}
                {!detail.artifacts.length ? <p className="py-12 text-center text-sm text-[var(--af-text-tertiary)]">尚无证据绑定产物</p> : null}
              </div>
            </section>
          ) : null}

          {detail && tab === "governance" ? (
            <section className="af-glass rounded-lg p-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">Knowledge Space</h2>
                    <span className="text-xs text-[var(--af-text-tertiary)]">{overview?.spaces.length ?? 0}</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    {overview?.spaces.map((space, index) => (
                      <div key={String(space.id ?? index)} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                        <div className="flex items-center justify-between gap-2">
                          <strong className="text-sm text-[var(--af-text-primary)]">{String(space.name ?? "Knowledge Space")}</strong>
                          <StatusPill status={String(space.status ?? "watch")} label={String(space.actor_role ?? "viewer")} />
                        </div>
                        <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">{String(space.visibility ?? "private")} · {Array.isArray(space.members) ? space.members.length : 0} members</p>
                      </div>
                    ))}
                    {!overview?.spaces.length ? <p className="py-10 text-center text-sm text-[var(--af-text-tertiary)]">当前 Notebook 为私有空间</p> : null}
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">签名 Skill 注册表</h2>
                    <span className="text-xs text-[var(--af-text-tertiary)]">{overview?.skills.length ?? 0}</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    {overview?.skills.map((skill) => (
                      <div key={skill.id} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <strong className="text-sm text-[var(--af-text-primary)]">{skill.skill_key}</strong>
                          <StatusPill status={skill.status} />
                        </div>
                        <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">v{skill.version} · signature {skill.signature_valid ? "valid" : "pending"} · {skill.permissions.length} permissions</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          ) : null}

          {tab === "program" ? <DecisionProgramPanel /> : null}

          {tab === "readiness" ? (
            <div className="space-y-4">
              <section className="af-glass rounded-lg p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">{releaseProgram?.release_version ?? "2.0.7-development"}</h2>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">六个版本工程实现与验收证据分别判定</p>
                  </div>
                  {releaseProgram ? <StatusPill status={releaseProgram.overall_status} label={`${releaseProgram.implementation_status} · ${releaseProgram.readiness_score}/100`} /> : null}
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  {releaseProgram?.milestones.map((milestone) => (
                    <article key={milestone.version} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{milestone.version}</h3>
                          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">工程已实现 · 验收 {milestone.passed_suite_count}/{milestone.suite_count}</p>
                        </div>
                        <StatusPill status={milestone.acceptance_status} label={`${milestone.acceptance_status} · ${milestone.score}`} />
                      </div>
                      <div className="mt-3 divide-y divide-[var(--af-border-subtle)] border-t border-[var(--af-border-subtle)]">
                        {milestone.suites.map((suite) => (
                          <div key={suite.suite_key} className="py-3 first:pt-3 last:pb-0">
                            <div className="flex items-start justify-between gap-2">
                              <span className="min-w-0 text-xs font-medium text-[var(--af-text-secondary)]">{suite.label}</span>
                              <StatusPill status={suite.status} label={`${suite.score}`} />
                            </div>
                            <p className="mt-1 text-[11px] text-[var(--af-text-tertiary)]">{suite.evidence_class}</p>
                            {suite.blockers[0] ? <p className="mt-1 text-[11px] leading-5 text-[var(--af-warning)]">{suite.blockers[0]}</p> : null}
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="af-glass rounded-lg p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--af-text-primary)]">全局 Release Readiness</h2>
                  <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">继承健康、diagnostics、低质量、独立复核、专家校准和视觉门禁</p>
                </div>
                <div className="flex items-center gap-2">
                  {readiness ? <StatusPill status={readiness.overall_status} label={`${readiness.overall_status} · ${readiness.readiness_score}/100`} /> : null}
                  <button className="af-btn af-btn-secondary px-3 py-1.5 text-xs" onClick={() => void refreshReadiness()} disabled={Boolean(working)}>重新扫描</button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {readiness?.gates.map((gate) => (
                  <article key={gate.key} className="rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">{gate.label}</h3>
                        <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{gate.observed}</p>
                      </div>
                      <StatusPill status={gate.status} label={`${gate.score}`} />
                    </div>
                    {gate.status !== "pass" && gate.actions[0] ? <p className="mt-3 border-t border-[var(--af-border-subtle)] pt-3 text-xs text-[var(--af-warning)]">{gate.actions[0].action}</p> : null}
                  </article>
                ))}
              </div>
              </section>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
