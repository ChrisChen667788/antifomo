const { feedItems, savedItems, mockSession } = require("./mock");
const { trackEvent } = require("./analytics");
const { t } = require("./i18n");
const PENDING_QUEUE_KEY = "antiFomoPendingOpsQueueV1";

function getApiBase() {
  const app = getApp();
  return (app && app.globalData && app.globalData.apiBaseUrl) || "http://127.0.0.1:8000";
}

function isLoopbackApi(baseUrl) {
  return /^https?:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?/i.test(String(baseUrl || "").trim());
}

function request(path, options = {}) {
  const baseUrl = String(options.baseUrl || getApiBase()).trim().replace(/\/+$/, "");
  const url = `${baseUrl}${path}`;
  const method = options.method || "GET";
  const data = options.data || null;
  const app = getApp();
  const isDevtools = Boolean(app && app.globalData && app.globalData.isDevtools);

  if (!isDevtools && isLoopbackApi(baseUrl)) {
    return Promise.reject(
      new Error("REAL_DEVICE_LOOPBACK_API_BASE: 真机不能访问 127.0.0.1，请改成电脑局域网 IP")
    );
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method,
      data,
      timeout: options.timeout || 12000,
      header: {
        "content-type": "application/json",
        ...(options.header || {})
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const detail =
          res && res.data && typeof res.data === "object" && res.data.detail
            ? String(res.data.detail)
            : "";
        reject(new Error(detail ? `API ${res.statusCode}: ${detail}` : `API ${res.statusCode}`));
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

function getApiHealth(baseUrlOverride) {
  return request("/healthz", {
    baseUrl: baseUrlOverride
  }).then((res) => ({ ...res, _fromMock: false }));
}

function getCurrentFocusRuntimeFallback() {
  const app = getApp();
  const globalData = (app && app.globalData) || {};
  const duration = Math.max(1, Number(globalData.currentSessionDuration || mockSession.duration_minutes || 25));
  const goalText = String(globalData.currentSessionGoal || mockSession.goal_text || "").trim();
  const sessionId = String(globalData.currentSessionId || mockSession.id || "").trim();
  return {
    duration_minutes: duration,
    goal_text: goalText || mockSession.goal_text,
    session_id: sessionId || mockSession.id,
    is_active_session: !!sessionId
  };
}

function readPendingQueue() {
  try {
    const raw = wx.getStorageSync(PENDING_QUEUE_KEY);
    if (Array.isArray(raw)) return raw;
    if (typeof raw === "string" && raw) {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    }
  } catch (_) {
    // ignore parse/storage errors
  }
  return [];
}

function writePendingQueue(queue) {
  const safe = Array.isArray(queue) ? queue.slice(-80) : [];
  wx.setStorageSync(PENDING_QUEUE_KEY, safe);
}

function enqueuePendingOperation(op) {
  const queue = readPendingQueue();
  queue.push({
    ...op,
    queued_at: Date.now()
  });
  writePendingQueue(queue);
  trackEvent("offline_queue_enqueue", {
    type: op.type,
    queue_size: queue.length
  });
}

function runPendingOperation(op) {
  if (!op || !op.type) {
    return Promise.resolve();
  }
  if (op.type === "feedback") {
    return request(`/api/items/${op.item_id}/feedback`, {
      method: "POST",
      data: { feedback_type: op.feedback_type }
    });
  }
  if (op.type === "reprocess") {
    return request(`/api/items/${op.item_id}/reprocess`, {
      method: "POST",
      data: op.output_language
        ? { output_language: op.output_language }
        : {}
    });
  }
  if (op.type === "task") {
    return request("/api/tasks", {
      method: "POST",
      data: op.payload
    });
  }
  return Promise.resolve();
}

function flushPendingQueue(maxOps = 12) {
  const queue = readPendingQueue();
  if (!queue.length) {
    return Promise.resolve({
      flushed: 0,
      remaining: 0
    });
  }

  const pending = queue.slice(0, maxOps);
  const leftovers = queue.slice(maxOps);
  let flushed = 0;

  return pending
    .reduce((chain, op) => {
      return chain.then(() =>
        runPendingOperation(op)
          .then(() => {
            flushed += 1;
          })
          .catch(() => {
            leftovers.push(op);
          })
      );
    }, Promise.resolve())
    .then(() => {
      writePendingQueue(leftovers);
      if (flushed > 0) {
        trackEvent("offline_queue_flush", {
          flushed,
          remaining: leftovers.length
        });
      }
      return {
        flushed,
        remaining: leftovers.length
      };
    })
    .catch(() => {
      writePendingQueue(queue);
      return {
        flushed: 0,
        remaining: queue.length
      };
    });
}

function sanitizeTitleText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/^标题[:：]\s*/i, "")
    .replace(/^关键词[:：].*$/i, "")
    .replace(/^作者[:：].*$/i, "")
    .trim();
}

function deriveDisplayTitle(item) {
  const rawTitle = sanitizeTitleText(item.title || "");
  const isPlaceholderTitle =
    !rawTitle ||
    /^wechat\s+(auto|ocr)/i.test(rawTitle) ||
    /^untitled/i.test(rawTitle) ||
    /^未命名/.test(rawTitle);

  if (!isPlaceholderTitle) {
    return rawTitle;
  }

  const seeds = [item.short_summary, item.long_summary, item.raw_content];
  for (const seed of seeds) {
    const text = String(seed || "")
      .replace(/\s+/g, " ")
      .replace(/^短摘要[:：]\s*/i, "")
      .replace(/^长摘要[:：]\s*/i, "")
      .trim();
    if (!text) continue;

    const candidates = text
      .split(/[。！？!?；;\n]/)
      .map((part) =>
        part
          .replace(/^(这篇文章|本文|文章|这条内容|内容主要|文章主要|本文主要|文中主要|核心信息是|核心观点是|主要讲的是)/, "")
          .replace(/\s+/g, " ")
          .trim()
      )
      .filter(Boolean);

    for (const candidate of candidates) {
      if (candidate.length < 8) continue;
      return candidate.slice(0, 30).replace(/[，,、:：-]+$/, "");
    }
  }

  return rawTitle || "未命名内容";
}

function normalizeItem(item) {
  const resolvedTitle = deriveDisplayTitle(item);
  return {
    id: item.id,
    source_type: item.source_type || "text",
    source_url: item.source_url || "",
    source_domain: item.source_domain || "unknown",
    title: resolvedTitle,
    raw_content: item.raw_content || "",
    clean_content: item.clean_content || "",
    short_summary: item.short_summary || "暂无短摘要",
    long_summary: item.long_summary || "暂无长摘要",
    score_value: item.score_value,
    action_suggestion: item.action_suggestion || "skip",
    output_language: item.output_language || "zh-CN",
    ingest_route: item.ingest_route || "unknown",
    content_acquisition_status: item.content_acquisition_status || "pending",
    content_acquisition_note: item.content_acquisition_note || "",
    resolved_from_url: item.resolved_from_url || "",
    fallback_used: !!item.fallback_used,
    status: item.status || "pending",
    processing_error: item.processing_error || "",
    created_at: item.created_at || "",
    recommendation_score: item.recommendation_score,
    recommendation_bucket: item.recommendation_bucket || "",
    recommendation_reason: item.recommendation_reason || [],
    topic_match_score: item.topic_match_score,
    source_match_score: item.source_match_score,
    preference_version: item.preference_version || "",
    matched_preferences: item.matched_preferences || [],
    why_recommended: item.why_recommended || [],
    tags: item.tags || [],
    _fromMock: !!item._fromMock,
    _localReason: item._localReason || ""
  };
}

function normalizeExternalIngestResponse(response, fallbackMeta = {}) {
  const normalized = response || {};
  return {
    item: normalizeItem({ ...(normalized.item || {}), _fromMock: !!normalized._fromMock }),
    deduplicated: !!normalized.deduplicated,
    processing_deferred: !!normalized.processing_deferred,
    attempt_id: normalized.attempt_id || "",
    ingest_route: normalized.ingest_route || "",
    content_acquisition_status: normalized.content_acquisition_status || "pending",
    resolver: normalized.resolver || "",
    body_source: normalized.body_source || "",
    fallback_used: !!normalized.fallback_used,
    metadata: normalized.metadata || fallbackMeta,
    _fromMock: !!normalized._fromMock
  };
}

function normalizeResearchReport(report, payload = {}) {
  const normalized = report || {};
  const normalizeResearchText = (value) =>
    String(value || "")
      .replace(/\[Image\s*\d+\]/gi, " ")
      .replace(/!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/gi, "$1")
      .replace(/\s+/g, " ")
      .trim();
  const conciseEntityName = (value) => {
    const normalizedValue = normalizeResearchText(value);
    if (!normalizedValue) return "";
    const primary = normalizedValue.split(/[：:]/)[0] || normalizedValue;
    return (primary.split(/\s*[·•|｜]\s*/)[0] || primary).trim();
  };
  const scoreLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 75) return "高价值";
    if (numeric >= 55) return "普通价值";
    return "低价值";
  };
  const factorLabel = (score) => {
    const numeric = Number(score || 0);
    if (numeric >= 14) return "强支撑";
    if (numeric >= 6) return "中支撑";
    if (numeric > 0) return "弱支撑";
    if (numeric < 0) return "风险提示";
    return "待补证据";
  };
  const normalizeRankedEntities = (items) =>
    (Array.isArray(items) ? items : []).map((entity) => ({
      name: conciseEntityName(entity && entity.name),
      score: Number((entity && entity.score) || 0),
      score_label: scoreLabel(entity && entity.score),
      entity_mode: String((entity && entity.entity_mode) || "instance"),
      reasoning: normalizeResearchText(entity && entity.reasoning),
      score_breakdown: Array.isArray(entity && entity.score_breakdown)
        ? entity.score_breakdown
            .map((factor) => ({
              label: (factor && factor.label) || "",
              score: Number((factor && factor.score) || 0),
              note: (factor && factor.note) || "",
              score_label: factorLabel(factor && factor.score)
            }))
            .filter((factor) => factor.label)
        : [],
      evidence_links: Array.isArray(entity && entity.evidence_links)
        ? entity.evidence_links
            .map((link) => {
              const tier = String((link && link.source_tier) || "media");
              const tierLabel = tier === "official" ? "官方源" : tier === "aggregate" ? "聚合源" : "媒体源";
              return {
                title: (link && link.title) || (link && link.url) || "来源待确认",
                url: (link && link.url) || "",
                source_label: (link && link.source_label) || "",
                source_tier: tier,
                tier_label: tierLabel
              };
            })
            .filter((link) => link.url)
        : []
    }));
  const normalizeEntityGraph = (graph) => {
    const normalizeEntities = (items) =>
      (Array.isArray(items) ? items : [])
        .map((entity) => ({
          canonical_name: conciseEntityName(entity && entity.canonical_name),
          entity_type: String((entity && entity.entity_type) || "generic"),
          aliases: Array.isArray(entity && entity.aliases)
            ? entity.aliases.map(conciseEntityName).filter(Boolean)
            : [],
          source_count: Number((entity && entity.source_count) || 0),
          source_tier_counts:
            entity && entity.source_tier_counts && typeof entity.source_tier_counts === "object"
              ? entity.source_tier_counts
              : {},
          evidence_links: Array.isArray(entity && entity.evidence_links)
            ? entity.evidence_links
                .map((link) => ({
                  title: (link && link.title) || (link && link.url) || "来源待确认",
                  url: (link && link.url) || "",
                  source_label: (link && link.source_label) || "",
                  source_tier: (link && link.source_tier) || "media"
                }))
                .filter((link) => link.url)
            : []
        }))
        .filter((entity) => entity.canonical_name);
    return {
      entities: normalizeEntities(graph && graph.entities),
      target_entities: normalizeEntities(graph && graph.target_entities),
      competitor_entities: normalizeEntities(graph && graph.competitor_entities),
      partner_entities: normalizeEntities(graph && graph.partner_entities)
    };
  };
  return {
    keyword: normalized.keyword || payload.keyword || "",
    research_focus: normalized.research_focus || payload.research_focus || "",
    output_language: normalized.output_language || payload.output_language || "zh-CN",
    research_mode: normalized.research_mode || payload.research_mode || (payload.deep_research === false ? "fast" : "deep"),
    report_title: normalized.report_title || `${payload.keyword || "专题"}研报`,
    executive_summary:
      normalized.executive_summary || "当前为本地演示研报，可用于查看页面结构和咨询输出样式。",
    consulting_angle:
      normalized.consulting_angle || "适合作为行业判断、方案设计、销售推进和投标准备的初版工作底稿。",
    sections: Array.isArray(normalized.sections)
      ? normalized.sections.map((section) => ({
          title: section.title || "分析板块",
          items: Array.isArray(section.items) ? section.items : [],
          evidence_density: section.evidence_density || "low",
          source_quality: section.source_quality || "low",
          evidence_note: section.evidence_note || ""
        }))
      : [],
    target_accounts: Array.isArray(normalized.target_accounts)
      ? normalized.target_accounts.map(conciseEntityName).filter(Boolean)
      : [],
    top_target_accounts: normalizeRankedEntities(normalized.top_target_accounts),
    pending_target_candidates: normalizeRankedEntities(normalized.pending_target_candidates),
    target_departments: Array.isArray(normalized.target_departments) ? normalized.target_departments : [],
    public_contact_channels: Array.isArray(normalized.public_contact_channels) ? normalized.public_contact_channels : [],
    account_team_signals: Array.isArray(normalized.account_team_signals) ? normalized.account_team_signals : [],
    budget_signals: Array.isArray(normalized.budget_signals) ? normalized.budget_signals : [],
    project_distribution: Array.isArray(normalized.project_distribution) ? normalized.project_distribution : [],
    strategic_directions: Array.isArray(normalized.strategic_directions) ? normalized.strategic_directions : [],
    tender_timeline: Array.isArray(normalized.tender_timeline) ? normalized.tender_timeline : [],
    leadership_focus: Array.isArray(normalized.leadership_focus) ? normalized.leadership_focus : [],
    ecosystem_partners: Array.isArray(normalized.ecosystem_partners)
      ? normalized.ecosystem_partners.map(conciseEntityName).filter(Boolean)
      : [],
    top_ecosystem_partners: normalizeRankedEntities(normalized.top_ecosystem_partners),
    pending_partner_candidates: normalizeRankedEntities(normalized.pending_partner_candidates),
    competitor_profiles: Array.isArray(normalized.competitor_profiles)
      ? normalized.competitor_profiles.map(conciseEntityName).filter(Boolean)
      : [],
    top_competitors: normalizeRankedEntities(normalized.top_competitors),
    pending_competitor_candidates: normalizeRankedEntities(normalized.pending_competitor_candidates),
    benchmark_cases: Array.isArray(normalized.benchmark_cases) ? normalized.benchmark_cases : [],
    flagship_products: Array.isArray(normalized.flagship_products) ? normalized.flagship_products : [],
    key_people: Array.isArray(normalized.key_people) ? normalized.key_people : [],
    five_year_outlook: Array.isArray(normalized.five_year_outlook) ? normalized.five_year_outlook : [],
    client_peer_moves: Array.isArray(normalized.client_peer_moves)
      ? normalized.client_peer_moves.map(normalizeResearchText).filter(Boolean)
      : [],
    winner_peer_moves: Array.isArray(normalized.winner_peer_moves)
      ? normalized.winner_peer_moves.map(normalizeResearchText).filter(Boolean)
      : [],
    competition_analysis: Array.isArray(normalized.competition_analysis) ? normalized.competition_analysis : [],
    source_count: Number(normalized.source_count || 0),
    evidence_density: normalized.evidence_density || "low",
    source_quality: normalized.source_quality || "low",
    query_plan: Array.isArray(normalized.query_plan) ? normalized.query_plan : [payload.keyword || ""],
    sources: Array.isArray(normalized.sources)
      ? normalized.sources.map((source) => ({
          title: source.title || source.url || "来源待确认",
          url: source.url || "",
          domain: source.domain || "",
          snippet: source.snippet || "",
          search_query: source.search_query || "",
          source_type: source.source_type || "web",
          content_status: source.content_status || "snippet_only",
          source_label: source.source_label || "",
          source_tier: source.source_tier || "media"
        }))
      : [],
    source_diagnostics:
      normalized && normalized.source_diagnostics && typeof normalized.source_diagnostics === "object"
        ? {
            enabled_source_labels: Array.isArray(normalized.source_diagnostics.enabled_source_labels)
              ? normalized.source_diagnostics.enabled_source_labels
              : [],
            matched_source_labels: Array.isArray(normalized.source_diagnostics.matched_source_labels)
              ? normalized.source_diagnostics.matched_source_labels
              : [],
            scope_regions: Array.isArray(normalized.source_diagnostics.scope_regions)
              ? normalized.source_diagnostics.scope_regions
              : [],
            scope_industries: Array.isArray(normalized.source_diagnostics.scope_industries)
              ? normalized.source_diagnostics.scope_industries
              : [],
            scope_clients: Array.isArray(normalized.source_diagnostics.scope_clients)
              ? normalized.source_diagnostics.scope_clients
              : [],
            source_type_counts:
              normalized.source_diagnostics.source_type_counts &&
              typeof normalized.source_diagnostics.source_type_counts === "object"
                ? normalized.source_diagnostics.source_type_counts
                : {},
            source_tier_counts:
              normalized.source_diagnostics.source_tier_counts &&
              typeof normalized.source_diagnostics.source_tier_counts === "object"
                ? normalized.source_diagnostics.source_tier_counts
                : {},
            adapter_hit_count: Number(normalized.source_diagnostics.adapter_hit_count || 0),
            search_hit_count: Number(normalized.source_diagnostics.search_hit_count || 0),
            recency_window_years: Number(normalized.source_diagnostics.recency_window_years || 7),
            filtered_old_source_count: Number(normalized.source_diagnostics.filtered_old_source_count || 0),
            filtered_region_conflict_count: Number(normalized.source_diagnostics.filtered_region_conflict_count || 0),
            retained_source_count: Number(normalized.source_diagnostics.retained_source_count || 0),
            strict_topic_source_count: Number(normalized.source_diagnostics.strict_topic_source_count || 0),
            topic_anchor_terms: Array.isArray(normalized.source_diagnostics.topic_anchor_terms)
              ? normalized.source_diagnostics.topic_anchor_terms
              : [],
            matched_theme_labels: Array.isArray(normalized.source_diagnostics.matched_theme_labels)
              ? normalized.source_diagnostics.matched_theme_labels
              : []
            ,
            retrieval_quality: ["low", "medium", "high"].includes(String(normalized.source_diagnostics.retrieval_quality || ""))
              ? normalized.source_diagnostics.retrieval_quality
              : "low",
            evidence_mode: ["strong", "provisional", "fallback"].includes(String(normalized.source_diagnostics.evidence_mode || ""))
              ? normalized.source_diagnostics.evidence_mode
              : "fallback",
            evidence_mode_label:
              typeof normalized.source_diagnostics.evidence_mode_label === "string" && normalized.source_diagnostics.evidence_mode_label
                ? normalized.source_diagnostics.evidence_mode_label
                : "兜底候选",
            strict_match_ratio: Number(normalized.source_diagnostics.strict_match_ratio || 0),
            strict_match_percent: Math.round(Number(normalized.source_diagnostics.strict_match_ratio || 0) * 100),
            official_source_ratio: Number(normalized.source_diagnostics.official_source_ratio || 0),
            official_source_percent: Math.round(Number(normalized.source_diagnostics.official_source_ratio || 0) * 100),
            unique_domain_count: Number(normalized.source_diagnostics.unique_domain_count || 0),
            normalized_entity_count: Number(normalized.source_diagnostics.normalized_entity_count || 0),
            normalized_target_count: Number(normalized.source_diagnostics.normalized_target_count || 0),
            normalized_competitor_count: Number(normalized.source_diagnostics.normalized_competitor_count || 0),
            normalized_partner_count: Number(normalized.source_diagnostics.normalized_partner_count || 0),
            expansion_triggered: Boolean(normalized.source_diagnostics.expansion_triggered),
            corrective_triggered: Boolean(normalized.source_diagnostics.corrective_triggered),
            candidate_profile_companies: Array.isArray(normalized.source_diagnostics.candidate_profile_companies)
              ? normalized.source_diagnostics.candidate_profile_companies
              : [],
            candidate_profile_hit_count: Number(normalized.source_diagnostics.candidate_profile_hit_count || 0),
            candidate_profile_official_hit_count: Number(normalized.source_diagnostics.candidate_profile_official_hit_count || 0),
            candidate_profile_source_labels: Array.isArray(normalized.source_diagnostics.candidate_profile_source_labels)
              ? normalized.source_diagnostics.candidate_profile_source_labels
              : [],
            strategy_model_used: Boolean(normalized.source_diagnostics.strategy_model_used),
            strategy_scope_summary:
              typeof normalized.source_diagnostics.strategy_scope_summary === "string"
                ? normalized.source_diagnostics.strategy_scope_summary
                : "",
            strategy_query_expansion_count: Number(normalized.source_diagnostics.strategy_query_expansion_count || 0),
            strategy_exclusion_terms: Array.isArray(normalized.source_diagnostics.strategy_exclusion_terms)
              ? normalized.source_diagnostics.strategy_exclusion_terms
              : []
          }
        : {
            enabled_source_labels: [],
            matched_source_labels: [],
            scope_regions: [],
            scope_industries: [],
            scope_clients: [],
            source_type_counts: {},
            source_tier_counts: {},
            adapter_hit_count: 0,
            search_hit_count: 0,
            recency_window_years: 7,
            filtered_old_source_count: 0,
            filtered_region_conflict_count: 0,
            retained_source_count: 0,
            strict_topic_source_count: 0,
            topic_anchor_terms: [],
            matched_theme_labels: [],
            retrieval_quality: "low",
            evidence_mode: "fallback",
            evidence_mode_label: "兜底候选",
            strict_match_ratio: 0,
            strict_match_percent: 0,
            official_source_ratio: 0,
            official_source_percent: 0,
            unique_domain_count: 0,
            normalized_entity_count: 0,
            normalized_target_count: 0,
            normalized_competitor_count: 0,
            normalized_partner_count: 0,
            expansion_triggered: false,
            corrective_triggered: false,
            candidate_profile_companies: [],
            candidate_profile_hit_count: 0,
            candidate_profile_official_hit_count: 0,
            candidate_profile_source_labels: [],
            strategy_model_used: false,
            strategy_scope_summary: "",
            strategy_query_expansion_count: 0,
            strategy_exclusion_terms: []
          },
    entity_graph: normalizeEntityGraph(normalized.entity_graph),
    generated_at: normalized.generated_at || new Date().toISOString()
  };
}

function normalizeResearchActionPlan(plan, payload = {}) {
  const normalized = plan || {};
  const normalizeActionText = (value) =>
    String(value || "")
      .replace(/\[Image\s*\d+\]/gi, " ")
      .replace(/!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/gi, "$1")
      .replace(/\s+/g, " ")
      .trim();
  const priorityLabel = (priority) => {
    const normalizedPriority = String(priority || "").toLowerCase();
    if (normalizedPriority === "high") return "高价值";
    if (normalizedPriority === "low") return "低价值";
    return "普通价值";
  };
  const parsePhases = (steps) =>
    (Array.isArray(steps) ? steps : [])
      .map((step) => normalizeActionText(step))
      .filter(Boolean)
      .map((step) => {
        const match = step.match(/^(短期|中期|长期|Short term|Mid term|Long term)(?:（([^）]+)）|\(([^)]+)\))?[:：]\s*(.+)$/i);
        if (!match) {
          return {
            label: "关键动作",
            horizon: "",
            content: step
          };
        }
        return {
          label: match[1],
          horizon: match[2] || match[3] || "",
          content: match[4]
        };
      })
      .slice(0, 3);
  const evidenceCards = (evidence) =>
    (Array.isArray(evidence) ? evidence : [])
      .map((row) => normalizeActionText(row))
      .filter(Boolean)
      .map((text) => {
        const match = text.match(/https?:\/\/[^\s)]+/);
        const url = match ? match[0] : "";
        const label = text.replace(/https?:\/\/[^\s)]+/g, "").replace(/[()]/g, " ").replace(/\s+/g, " ").trim();
        return {
          label: label || "打开公开来源",
          url
        };
      })
      .slice(0, 3);
  return {
    keyword: normalized.keyword || payload.keyword || "",
    generated_at: normalized.generated_at || new Date().toISOString(),
    cards: Array.isArray(normalized.cards)
      ? normalized.cards.map((card, index) => ({
          action_type: card.action_type || `action_${index + 1}`,
          priority: card.priority || "medium",
          priority_label: priorityLabel(card.priority),
          title: card.title || `行动卡 ${index + 1}`,
          summary: normalizeActionText(card.summary),
          recommended_steps: Array.isArray(card.recommended_steps)
            ? card.recommended_steps.map((step) => normalizeActionText(step)).filter(Boolean)
            : [],
          phases: parsePhases(card.recommended_steps),
          evidence: Array.isArray(card.evidence)
            ? card.evidence.map((row) => normalizeActionText(row)).filter(Boolean)
            : [],
          evidence_cards: evidenceCards(card.evidence),
          target_persona: card.target_persona || "",
          execution_window: card.execution_window || "",
          deliverable: card.deliverable || "",
        }))
      : [],
  };
}

function listItems(limit = 30, options = {}) {
  const mode = options.mode === "focus" ? "focus" : "normal";
  const goalText = options.goalText ? String(options.goalText).trim() : "";
  const includePending = options.includePending !== undefined ? !!options.includePending : true;
  const query = [`limit=${limit}`, `mode=${mode}`, `include_pending=${includePending ? "true" : "false"}`];
  if (goalText) {
    query.push(`goal_text=${encodeURIComponent(goalText)}`);
  }

  return request(`/api/items?${query.join("&")}`)
    .then((res) => ({
      items: (res.items || []).map(normalizeItem),
      fromMock: false
    }))
    .catch(() => ({ items: feedItems.map(normalizeItem), fromMock: true }));
}

function listSavedItems(limit = 30) {
  return request(`/api/items/saved?limit=${limit}`)
    .then((res) => ({
      items: (res.items || []).map(normalizeItem),
      fromMock: false
    }))
    .catch(() => ({ items: savedItems.map(normalizeItem).slice(0, limit), fromMock: true }));
}

function getItem(itemId) {
  return request(`/api/items/${itemId}`)
    .then((res) => {
      void flushPendingQueue(6);
      return normalizeItem({ ...res, _fromMock: false });
    })
    .catch(() => {
      const fallback = feedItems.find((item) => item.id === itemId) || feedItems[0];
      return normalizeItem({
        ...fallback,
        _fromMock: true,
        _localReason: "api_unavailable"
      });
    });
}

function getPreferenceSummary() {
  return request("/api/preferences/summary", {
    method: "GET"
  }).then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      user_id: "demo-user",
      generated_at: new Date().toISOString(),
      preference_version: "mock",
      feedback_total: 0,
      last_feedback_at: null,
      recent_feedback_counts: {},
      top_tags: [],
      top_domains: [],
      snapshot_id: null,
      _fromMock: true
    }));
}

function resetPreferences(scope = "all") {
  return request("/api/preferences/reset", {
    method: "POST",
    data: { scope }
  }).then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      user_id: "demo-user",
      generated_at: new Date().toISOString(),
      preference_version: "mock",
      feedback_total: 0,
      last_feedback_at: null,
      recent_feedback_counts: {},
      top_tags: [],
      top_domains: [],
      snapshot_id: null,
      _fromMock: true
    }));
}

function boostPreference(payload) {
  return request("/api/preferences/boost", {
    method: "POST",
    data: payload || {}
  }).then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      dimension: payload && payload.dimension ? payload.dimension : "topic",
      key: payload && payload.key ? payload.key : "",
      delta: Number((payload && payload.delta) || 1),
      updated_score: Number((payload && payload.delta) || 1),
      summary: {
        user_id: "demo-user",
        generated_at: new Date().toISOString(),
        preference_version: "mock",
        feedback_total: 0,
        last_feedback_at: null,
        recent_feedback_counts: {},
        top_tags: [],
        top_domains: [],
        snapshot_id: null
      },
      _fromMock: true
    }));
}

function getItemDiagnostics(itemId) {
  return request(`/api/items/${itemId}/diagnostics`, {
    method: "GET"
  })
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => {
      const fallback = feedItems.find((item) => item.id === itemId) || feedItems[0] || {};
      const normalized = normalizeItem({
        ...fallback,
        _fromMock: true,
        _localReason: "api_unavailable"
      });
      return {
        item_id: normalized.id || itemId,
        source_type: normalized.source_type || "text",
        source_url: normalized.source_url || "",
        ingest_route: normalized.ingest_route || "mock",
        resolved_from_url: normalized.resolved_from_url || normalized.source_url || "",
        content_acquisition_status: normalized.content_acquisition_status || "mock_only",
        content_acquisition_note: "当前为本地演示数据，采集诊断不可用。",
        fallback_used: true,
        body_source: normalized.clean_content || normalized.raw_content ? "local_mock" : null,
        processing_status: normalized.status || "pending",
        processing_error: normalized.processing_error || "",
        latest_attempt: null,
        attempt_count: 0,
        _fromMock: true
      };
    });
}

function getCollectorItemAttempts(itemId) {
  return request(`/api/collector/items/${itemId}/attempts`, {
    method: "GET"
  })
    .then((res) => {
      const attempts = Array.isArray(res) ? res : [];
      return { attempts, _fromMock: false };
    })
    .catch(() => ({
      attempts: [],
      _fromMock: true
    }));
}

function interpretItem(itemId, payload = {}) {
  return request(`/api/items/${itemId}/interpret`, {
    method: "POST",
    data: payload.output_language ? { output_language: payload.output_language } : {}
  }).then((res) => {
    trackEvent("item_interpret_submit", {
      item_id: itemId,
      status: "ok"
    });
    return res;
  }).catch(() => {
    const preview = payload.preview || {};
    const title = preview.title || t((payload.output_language || "zh-CN"), "common.untitled", "未命名内容");
    const summary = preview.short_summary || preview.long_summary || t((payload.output_language || "zh-CN"), "common.noSummary", "暂无摘要");
    trackEvent("item_interpret_submit", {
      item_id: itemId,
      status: "mock"
    });
    return {
      item_id: itemId,
      output_language: payload.output_language || "zh-CN",
      insight_title: title,
      expert_take: `这条内容更值得关注的是“${title}”背后的实际变化。结合当前摘要，它适合作为后续持续观察的信号，而不是只看原标题。`,
      key_signals: [summary.slice(0, 24) || "信息信号待补充"],
      knowledge_note: `知识库笔记：${title}。${summary}`
    };
  });
}

function addItemToKnowledge(itemId, payload = {}) {
  return request(`/api/items/${itemId}/knowledge`, {
    method: "POST",
    data: payload
  }).then((res) => {
    trackEvent("knowledge_save_submit", {
      item_id: itemId,
      status: "ok"
    });
    return res;
  }).catch(() => {
    trackEvent("knowledge_save_submit", {
      item_id: itemId,
      status: "mock"
    });
    return {
      entry_id: `mock-knowledge-${Date.now()}`,
      item_id: itemId,
      title: payload.title || "知识卡片",
      content: payload.content || "本地已加入知识库（模拟）",
      source_domain: payload.source_domain || "",
      created_at: new Date().toISOString()
    };
  });
}

function listKnowledgeEntries(limit = 30, options = {}) {
  const query = [`limit=${limit}`];
  if (options.itemId) {
    query.push(`item_id=${encodeURIComponent(options.itemId)}`);
  }
  if (options.focusReferenceOnly) {
    query.push("focus_reference_only=true");
  }
  if (options.sourceDomain) {
    query.push(`source_domain=${encodeURIComponent(options.sourceDomain)}`);
  }
  if (options.collectionName) {
    query.push(`collection_name=${encodeURIComponent(options.collectionName)}`);
  }
  if (options.query) {
    query.push(`query=${encodeURIComponent(options.query)}`);
  }
  return request(`/api/knowledge?${query.join("&")}`)
    .then((res) => ({
      items: Array.isArray(res.items) ? res.items : [],
      fromMock: false
    }))
    .catch(() => ({
      items: [],
      fromMock: true
    }));
}

function getKnowledgeEntry(entryId) {
  return request(`/api/knowledge/${entryId}`)
    .then((res) => res)
    .catch(() => ({
      id: entryId,
      item_id: null,
      title: "知识卡片",
      content: "当前为本地回退展示，后端知识库接口未连接。",
      source_domain: "",
      metadata_payload: null,
      collection_name: "",
      is_pinned: false,
      is_focus_reference: false,
      created_at: new Date().toISOString(),
      _fromMock: true
    }));
}

function getKnowledgeMarkdown(entryId) {
  return request(`/api/knowledge/${entryId}/markdown`)
    .then((res) => res)
    .catch(() => ({
      filename: `knowledge-${Date.now()}.md`,
      content: "# 知识卡片\n\n当前为本地 Markdown 回退结果。",
      _fromMock: true
    }));
}

function listRelatedKnowledgeEntries(entryId, limit = 4) {
  return request(`/api/knowledge/${entryId}/related?limit=${limit}`)
    .then((res) => ({
      items: Array.isArray(res.items) ? res.items : [],
      fromMock: false
    }))
    .catch(() => ({
      items: [],
      fromMock: true
    }));
}

function updateKnowledgeEntry(entryId, payload = {}) {
  return request(`/api/knowledge/${entryId}`, {
    method: "PATCH",
    data: payload
  }).catch(() => ({
    id: entryId,
    item_id: null,
    title: payload.title || "知识卡片",
    content: payload.content || "当前为本地编辑回退结果。",
    source_domain: "",
    metadata_payload: payload.metadata_payload || null,
    collection_name: payload.collection_name || "",
    is_pinned: payload.is_pinned !== undefined ? !!payload.is_pinned : false,
    is_focus_reference: payload.is_focus_reference !== undefined ? !!payload.is_focus_reference : false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function updateKnowledgeEntriesBatch(payload = {}) {
  return request("/api/knowledge/batch-update", {
    method: "POST",
    data: payload
  }).then((res) => ({
    items: Array.isArray(res.items) ? res.items : [],
    fromMock: false
  })).catch(() => ({
    items: (payload.entry_ids || []).map((entryId) => ({
      id: entryId,
      item_id: null,
      title: "知识卡片",
      content: "当前为本地批量更新回退结果。",
      source_domain: "",
      collection_name: payload.collection_name || "",
      is_pinned: payload.is_pinned !== undefined ? !!payload.is_pinned : false,
      is_focus_reference: payload.is_focus_reference !== undefined ? !!payload.is_focus_reference : false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      _fromMock: true
    })),
    fromMock: true
  }));
}

function getKnowledgeBatchMarkdown(payload = {}) {
  return request("/api/knowledge/batch-markdown", {
    method: "POST",
    data: payload
  }).then((res) => res).catch(() => ({
    filename: `knowledge-batch-${Date.now()}.md`,
    content: "# 知识库批量导出\n\n当前为本地 Markdown 回退结果。",
    entry_count: Array.isArray(payload.entry_ids) ? payload.entry_ids.length : 0,
    _fromMock: true
  }));
}

function mergeKnowledgeEntries(payload = {}) {
  return request("/api/knowledge/merge", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: `merged-knowledge-${Date.now()}`,
    item_id: null,
    title: payload.title || "合并知识卡片",
    content: payload.content || "当前为本地合并回退结果。",
    source_domain: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function getKnowledgeMergePreview(payload = {}) {
  return request("/api/knowledge/merge/preview", {
    method: "POST",
    data: payload
  }).catch(() => {
    const previewEntries = Array.isArray(payload.preview_entries) ? payload.preview_entries : [];
    const titles = previewEntries
      .map((entry) => String(entry && entry.title || "").trim())
      .filter(Boolean);
    const uniqueTitles = Array.from(new Set(titles));
    const collectionNames = Array.from(
      new Set(
        previewEntries
          .map((entry) => String(entry && entry.collection_name || "").trim())
          .filter(Boolean)
      )
    );
    return {
      title:
        String(payload.title || "").trim() ||
        (uniqueTitles.length <= 1
          ? `${uniqueTitles[0] || "知识卡片"} / 综合卡片`
          : `${uniqueTitles[0]} + ${Math.max(0, uniqueTitles.length - 1)} 条延展`),
      count: previewEntries.length,
      titles: titles.slice(0, 3),
      more_count: Math.max(0, previewEntries.length - 3),
      inherit_pinned: previewEntries.some((entry) => !!(entry && entry.is_pinned)),
      inherit_focus_reference: previewEntries.some((entry) => !!(entry && entry.is_focus_reference)),
      inherit_collection: collectionNames.length === 1 ? collectionNames[0] : null,
      ready: previewEntries.length >= 2,
      _fromMock: true
    };
  });
}

function getKnowledgeRule() {
  return request("/api/knowledge/rules").catch(() => ({
    enabled: true,
    min_score_value: 4.0,
    archive_on_like: true,
    archive_on_save: true,
    _fromMock: true
  }));
}

function updateKnowledgeRule(payload = {}) {
  return request("/api/knowledge/rules", {
    method: "PUT",
    data: payload
  }).catch(() => ({
    enabled: payload.enabled !== undefined ? !!payload.enabled : true,
    min_score_value: payload.min_score_value !== undefined ? Number(payload.min_score_value) : 4.0,
    archive_on_like: payload.archive_on_like !== undefined ? !!payload.archive_on_like : true,
    archive_on_save: payload.archive_on_save !== undefined ? !!payload.archive_on_save : true,
    _fromMock: true
  }));
}

function createFocusAssistantPlan(payload = {}) {
  return request("/api/focus-assistant/plan", {
    method: "POST",
    data: payload
  }).catch(() => {
    const outputLanguage = payload.output_language || "zh-CN";
    const goalText = String(payload.goal_text || "").trim();
    const duration = Number(payload.duration_minutes || 25);
    return {
      goal_text: goalText || null,
      duration_minutes: duration,
      output_language: outputLanguage,
      latest_session_id: null,
      latest_session_status: null,
      focus_reference_count: 0,
      focus_reference_ids: [],
      focus_reference_titles: [],
      summary: `围绕“${goalText || "当前主任务"}”安排一轮 ${duration} 分钟的专注支持，优先整理阅读清单与专注后续动作。`,
      actions: [
        {
          key: "reading_digest",
          title: "整理稍后读清单",
          description: "把最近内容压成一份便于回看的阅读清单。",
          available: true,
          task_type: "export_reading_list",
          session_required: false,
          steps: ["汇总最近内容", "整理成阅读清单", "返回 Markdown 结果"],
          handoff_prompt: "请整理最近内容为一份可快速扫读的阅读清单。"
        },
        {
          key: "session_markdown_summary",
          title: "生成专注总结",
          description: "基于最近一次 Focus Session 输出 Markdown 总结。",
          available: false,
          task_type: "export_markdown_summary",
          session_required: true,
          reason: "需要先完成至少一轮 Focus Session。",
          steps: ["读取最近一次专注会话", "汇总重点内容", "生成 Markdown 总结"],
          handoff_prompt: "请基于最近一次专注会话生成 Markdown 总结。"
        }
      ],
      blocked_actions: [
        {
          key: "personal_wechat_auto_send",
          title: "个人微信自动代发",
          description: "自动读取并回复个人微信好友消息。",
          available: false,
          reason: "当前版本不支持个人微信私聊自动代发，这属于高风险能力。",
          steps: []
        }
      ],
      guardrails: [
        "仅执行导出、整理、摘要和参考材料打包，不自动代发个人微信私聊消息。",
        "所有执行动作默认生成结果草稿或文件，由用户确认后继续使用。"
      ],
      _fromMock: true
    };
  });
}

function executeFocusAssistantAction(payload = {}) {
  return request("/api/focus-assistant/execute", {
    method: "POST",
    data: payload
  }).catch(() => ({
    accepted: true,
    action_key: payload.action_key || "reading_digest",
    channel_used: payload.channel || "workbuddy",
    message: "已通过本地 Demo 通道执行",
    task: {
      id: `focus-assistant-${Date.now()}`,
      task_type:
        payload.action_key === "session_markdown_summary"
          ? "export_markdown_summary"
          : payload.action_key === "todo_draft"
            ? "export_todo_draft"
            : payload.action_key === "focus_reference_bundle"
              ? "export_knowledge_bundle_markdown"
              : "export_reading_list",
      status: "done",
      output_payload: {
        content: "# Focus Assistant\n\n当前为本地回退结果。",
        filename: `focus-assistant-${Date.now()}.md`
      }
    },
    _fromMock: true
  }));
}

function createItem(payload) {
  return request("/api/items", { method: "POST", data: payload })
    .then((res) => normalizeItem(res))
    .catch(() => {
      const now = new Date().toISOString();
      return normalizeItem({
        id: `mock-${Date.now()}`,
        source_type: payload.source_type,
        source_url: payload.source_url || "",
        source_domain: payload.source_url ? "mock.local" : "local-note",
        title: payload.title || "新输入内容",
        short_summary: payload.raw_content || payload.source_url || "本地回退摘要",
        long_summary: "API 未连接，当前显示本地回退结果。",
        score_value: 3,
        action_suggestion: "later",
        output_language: payload.output_language || "zh-CN",
        status: "ready",
        created_at: now,
        tags: [{ tag_name: "本地回退" }]
      });
    });
}

function createResearchReport(payload) {
  return request("/api/research/report", {
    method: "POST",
    data: payload,
    timeout: 45000
  })
    .then((res) => normalizeResearchReport(res, payload));
}

function createResearchJob(payload) {
  return request("/api/research/jobs", {
    method: "POST",
    data: payload,
    timeout: 15000
  });
}

function getResearchJob(jobId) {
  return request(`/api/research/jobs/${jobId}`, {
    method: "GET",
    timeout: 15000
  }).then((res) => {
    const normalized = { ...(res || {}) };
    if (normalized.report) {
      normalized.report = normalizeResearchReport(normalized.report, {
        keyword: normalized.keyword,
        research_focus: normalized.research_focus,
        output_language: normalized.output_language
      });
    }
    return normalized;
  });
}

function getResearchJobTimeline(jobId) {
  return request(`/api/research/jobs/${jobId}/timeline`, {
    method: "GET",
    timeout: 15000
  }).catch(() => []);
}

function buildMockConversation(payload = {}) {
  const title = (payload && payload.title) || "研究对话";
  const topicId = payload && payload.topic_id ? payload.topic_id : null;
  const jobId = payload && payload.job_id ? payload.job_id : null;
  const now = new Date().toISOString();
  return {
    id: `mock-conversation-${Date.now()}`,
    topic_id: topicId,
    job_id: jobId,
    title,
    status: "active",
    context_payload: {
      topic_name: title
    },
    created_at: now,
    updated_at: now,
    messages: [
      {
        id: `mock-conversation-message-${Date.now()}`,
        conversation_id: `mock-conversation-${Date.now()}`,
        role: "assistant",
        message_type: "summary",
        content: "当前为本地研究对话演示结果。你可以继续追问预算节点、甲方、竞品或伙伴变化。",
        payload: {
          suggested_followups: [
            "最近的预算节点是什么？",
            "有哪些甲方值得优先跟进？",
            "竞品最近有什么动作？"
          ]
        },
        created_at: now
      }
    ],
    _fromMock: true
  };
}

function listResearchConversations() {
  return request("/api/research/conversations", {
    method: "GET",
    timeout: 15000
  }).catch(() => []);
}

function createResearchConversation(payload) {
  return request("/api/research/conversations", {
    method: "POST",
    data: payload || {},
    timeout: 15000
  }).catch(() => buildMockConversation(payload));
}

function getResearchConversation(conversationId) {
  return request(`/api/research/conversations/${conversationId}`, {
    method: "GET",
    timeout: 15000
  }).catch(() => buildMockConversation({ title: "研究对话" }));
}

function sendResearchConversationMessage(conversationId, payload) {
  return request(`/api/research/conversations/${conversationId}/messages`, {
    method: "POST",
    data: payload || {},
    timeout: 20000
  }).catch(() => {
    const content = String((payload && payload.content) || "").trim() || "请继续追问";
    const mock = buildMockConversation({ title: "研究对话" });
    const now = new Date().toISOString();
    return {
      ...mock,
      id: conversationId || mock.id,
      messages: [
        {
          id: `mock-user-${Date.now()}`,
          conversation_id: conversationId || mock.id,
          role: "user",
          message_type: "question",
          content,
          payload: {},
          created_at: now
        },
        {
          id: `mock-assistant-${Date.now()}`,
          conversation_id: conversationId || mock.id,
          role: "assistant",
          message_type: "answer",
          content: `当前为本地演示回复：已收到你的追问“${content}”，建议回到真实 API 后继续查看证据与时间线。`,
          payload: {
            suggested_followups: [
              "继续补充公开证据",
              "整理甲方名单",
              "输出下一步行动"
            ]
          },
          created_at: now
        }
      ],
      updated_at: now,
      _fromMock: true
    };
  });
}

function getMobileDailyBrief(forceRefresh = false) {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return request(`/api/mobile/daily-brief${suffix}`, {
    method: "GET",
    timeout: 15000
  }).catch(() => {
    const now = new Date().toISOString();
    return {
      snapshot_id: `mock-brief-${Date.now()}`,
      brief_date: now.slice(0, 10),
      headline: "当前显示本地 Daily Brief 演示结果",
      summary: "API 未连接，建议回到真实后端后查看最新高价值内容和 watchlist 变化。",
      top_items: (Array.isArray(feedItems) ? feedItems : []).slice(0, 3).map((item) => ({
        id: item.id,
        title: item.title,
        source_domain: item.source_domain,
        summary: item.short_summary || item.long_summary || item.source_url || "",
        action_suggestion: item.action_suggestion || "later",
        score_value: item.score_value,
        source_url: item.source_url
      })),
      watchlist_changes: [
        {
          id: "mock-watchlist-change",
          change_type: "rewritten",
          summary: "当前为本地摘要，真实 watchlist 变化需连接 API 后生成。",
          severity: "medium",
          created_at: now
        }
      ],
      generated_at: now,
      audio_status: "unavailable",
      audio_url: "",
      audio_script: "",
      _fromMock: true
    };
  });
}

function getResearchSourceSettings() {
  return request("/api/research/source-settings", {
    method: "GET"
  }).catch(() => ({
    enable_jianyu_tender_feed: true,
    enable_yuntoutiao_feed: true,
    enable_ggzy_feed: true,
    enable_cecbid_feed: true,
    enable_ccgp_feed: true,
    enable_gov_policy_feed: true,
    enable_local_ggzy_feed: true,
    enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台"],
    connector_statuses: [
      {
        key: "public_open_source_adapters",
        label: "公开招采与行业源适配器",
        status: "active",
        detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
        requires_authorization: false
      },
      {
        key: "official_policy_procurement_connectors",
        label: "官方政策与采购公开源",
        status: "active",
        detail: "优先走政府、公共资源交易、上市披露等官方公开站点。",
        requires_authorization: false
      },
      {
        key: "authorized_enterprise_procurement_api",
        label: "企业采购授权接口",
        status: "authorization_required",
        detail: "如需更高命中率，可接入你合法持有的采购/招采 SaaS 授权接口或令牌型数据源。",
        requires_authorization: true
      },
      {
        key: "authorized_wechat_archive_connector",
        label: "授权微信/企业归档连接器",
        status: "authorization_required",
        detail: "如需把合规归档内容并入研报，请通过企业微信、会话存档或其他合法归档能力接入。",
        requires_authorization: true
      }
    ],
    updated_at: null,
    _fromMock: true
  }));
}

function updateResearchSourceSettings(payload) {
  return request("/api/research/source-settings", {
    method: "PUT",
    data: payload
  }).catch(() => ({
    enable_jianyu_tender_feed: !!(payload && payload.enable_jianyu_tender_feed),
    enable_yuntoutiao_feed: !!(payload && payload.enable_yuntoutiao_feed),
    enable_ggzy_feed: !!(payload && payload.enable_ggzy_feed),
    enable_cecbid_feed: !!(payload && payload.enable_cecbid_feed),
    enable_ccgp_feed: !!(payload && payload.enable_ccgp_feed),
    enable_gov_policy_feed: !!(payload && payload.enable_gov_policy_feed),
    enable_local_ggzy_feed: !!(payload && payload.enable_local_ggzy_feed),
    enabled_source_labels: [
      !!(payload && payload.enable_jianyu_tender_feed) ? "剑鱼标讯" : "",
      !!(payload && payload.enable_yuntoutiao_feed) ? "云头条" : "",
      !!(payload && payload.enable_ggzy_feed) ? "全国公共资源交易平台" : "",
      !!(payload && payload.enable_cecbid_feed) ? "中国招标投标网" : "",
      !!(payload && payload.enable_ccgp_feed) ? "政府采购合规聚合" : "",
      !!(payload && payload.enable_gov_policy_feed) ? "中国政府网政策/讲话" : "",
      !!(payload && payload.enable_local_ggzy_feed) ? "地方公共资源交易平台" : ""
    ].filter(Boolean),
    connector_statuses: [
      {
        key: "public_open_source_adapters",
        label: "公开招采与行业源适配器",
        status: "active",
        detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
        requires_authorization: false
      }
    ],
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function getResearchWorkspace() {
  return request("/api/research/workspace", {
    method: "GET"
  }).catch(() => ({
    saved_views: [],
    tracking_topics: [],
    _fromMock: true
  }));
}

function listResearchWatchlists() {
  return request("/api/research/watchlists", {
    method: "GET"
  }).catch(() => []);
}

function createResearchWatchlist(payload) {
  return request("/api/research/watchlists", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: `mock-watchlist-${Date.now()}`,
    tracking_topic_id: payload && payload.tracking_topic_id ? payload.tracking_topic_id : null,
    name: (payload && payload.name) || "未命名 Watchlist",
    watch_type: (payload && payload.watch_type) || "topic",
    query: (payload && payload.query) || "",
    research_focus: (payload && payload.research_focus) || "",
    perspective: (payload && payload.perspective) || "all",
    region_filter: (payload && payload.region_filter) || "",
    industry_filter: (payload && payload.industry_filter) || "",
    alert_level: (payload && payload.alert_level) || "medium",
    schedule: (payload && payload.schedule) || "manual",
    status: "active",
    last_checked_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    latest_changes: [],
    _fromMock: true
  }));
}

function getResearchWatchlistChanges(watchlistId) {
  return request(`/api/research/watchlists/${watchlistId}/changes`, {
    method: "GET"
  }).catch(() => []);
}

function refreshResearchWatchlist(watchlistId, payload) {
  return request(`/api/research/watchlists/${watchlistId}/refresh`, {
    method: "POST",
    data: payload || {}
  }).catch(() => ({
    watchlist: {
      id: watchlistId,
      tracking_topic_id: null,
      name: "本地 Watchlist",
      watch_type: "topic",
      query: "",
      research_focus: "",
      perspective: "all",
      region_filter: "",
      industry_filter: "",
      alert_level: "medium",
      schedule: "manual",
      status: "active",
      last_checked_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_changes: [],
    },
    topic: null,
    report: null,
    changes: [],
    _fromMock: true
  }));
}

function getResearchEntityDetail(entityId) {
  return request(`/api/research/entities/${entityId}`, {
    method: "GET"
  }).catch(() => ({
    id: entityId,
    canonical_name: "",
    entity_type: "generic",
    region_hint: "",
    industry_hint: "",
    aliases: [],
    evidence_links: [],
    linked_topic_ids: [],
    relations: [],
    profile_payload: {},
    last_seen_at: null,
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function saveResearchView(payload) {
  return request("/api/research/workspace/views", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: (payload && payload.id) || `mock-view-${Date.now()}`,
    name: (payload && payload.name) || "未命名视图",
    query: (payload && payload.query) || "",
    filter_mode: (payload && payload.filter_mode) || "all",
    perspective: (payload && payload.perspective) || "all",
    region_filter: (payload && payload.region_filter) || "",
    industry_filter: (payload && payload.industry_filter) || "",
    action_type_filter: (payload && payload.action_type_filter) || "",
    focus_only: !!(payload && payload.focus_only),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function deleteResearchView(viewId) {
  return request(`/api/research/workspace/views/${viewId}`, {
    method: "DELETE"
  }).catch(() => ({
    ok: true,
    _fromMock: true
  }));
}

function saveResearchTrackingTopic(payload) {
  return request("/api/research/workspace/topics", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: (payload && payload.id) || `mock-topic-${Date.now()}`,
    name: (payload && payload.name) || "未命名专题",
    keyword: (payload && payload.keyword) || "",
    research_focus: (payload && payload.research_focus) || "",
    perspective: (payload && payload.perspective) || "all",
    region_filter: (payload && payload.region_filter) || "",
    industry_filter: (payload && payload.industry_filter) || "",
    notes: (payload && payload.notes) || "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function deleteResearchTrackingTopic(topicId) {
  return request(`/api/research/workspace/topics/${topicId}`, {
    method: "DELETE"
  }).catch(() => ({
    ok: true,
    _fromMock: true
  }));
}

function refreshResearchTrackingTopic(topicId, payload = {}) {
  return request(`/api/research/workspace/topics/${topicId}/refresh`, {
    method: "POST",
    data: payload
  }).catch(() => ({
    topic: {
      id: topicId,
      name: "长期专题",
      keyword: "",
      research_focus: "",
      perspective: "all",
      region_filter: "",
      industry_filter: "",
      notes: "",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_refreshed_at: new Date().toISOString(),
      last_report_entry_id: null,
      last_report_title: "本地研报回退结果"
    },
    report: normalizeResearchReport({}, {
      keyword: "",
      research_focus: "",
      output_language: payload.output_language || "zh-CN",
      generated_at: new Date().toISOString()
    }),
    saved_entry_id: null,
    saved_entry_title: "本地研报回退结果",
    _fromMock: true
  }));
}

function getResearchTrackingTopicVersions(topicId) {
  return request(`/api/research/workspace/topics/${topicId}/versions`, {
    method: "GET"
  }).catch(() => []);
}

function getResearchTrackingTopicVersion(topicId, versionId) {
  return request(`/api/research/workspace/topics/${topicId}/versions/${versionId}`, {
    method: "GET"
  }).catch(() => null);
}

function saveResearchReport(payload) {
  return request("/api/research/report/save", {
    method: "POST",
    data: payload
  }).catch(() => ({
    entry_id: `mock-research-${Date.now()}`,
    title: (payload && payload.report && payload.report.report_title) || "研究报告",
    created_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function createResearchActionPlan(payload) {
  return request("/api/research/action-plan", {
    method: "POST",
    data: payload
  })
    .then((res) => normalizeResearchActionPlan(res, {
      keyword: payload && payload.report && payload.report.keyword
    }))
    .catch(() => normalizeResearchActionPlan({
      keyword: payload && payload.report && payload.report.keyword,
      cards: []
    }, {
      keyword: payload && payload.report && payload.report.keyword
    }));
}

function saveResearchActionCards(payload) {
  return request("/api/research/action-plan/save", {
    method: "POST",
    data: payload
  }).catch(() => ({
    created_count: Array.isArray(payload && payload.cards) ? payload.cards.length : 0,
    items: (Array.isArray(payload && payload.cards) ? payload.cards : []).map((card, index) => ({
      entry_id: `mock-research-action-${Date.now()}-${index}`,
      title: card.title || `行动卡 ${index + 1}`,
      created_at: new Date().toISOString()
    })),
    _fromMock: true
  }));
}

function reprocessItem(itemId, outputLanguage) {
  return request(`/api/items/${itemId}/reprocess`, {
    method: "POST",
    data: outputLanguage ? { output_language: outputLanguage } : {}
  }).then((res) => {
    trackEvent("item_reprocess_submit", { item_id: itemId, status: "ok" });
    return res;
  }).catch(() => {
    enqueuePendingOperation({
      type: "reprocess",
      item_id: itemId,
      output_language: outputLanguage || undefined
    });
    trackEvent("item_reprocess_submit", { item_id: itemId, status: "queued" });
    return {
      item_id: itemId,
      status: "queued"
    };
  });
}

function submitFeedback(itemId, feedbackType) {
  return request(`/api/items/${itemId}/feedback`, {
    method: "POST",
    data: { feedback_type: feedbackType }
  }).then((res) => {
    trackEvent("item_feedback_submit", {
      item_id: itemId,
      feedback_type: feedbackType,
      status: "ok"
    });
    return res;
  }).catch(() => {
    enqueuePendingOperation({
      type: "feedback",
      item_id: itemId,
      feedback_type: feedbackType
    });
    trackEvent("item_feedback_submit", {
      item_id: itemId,
      feedback_type: feedbackType,
      status: "queued"
    });
    return {
      item_id: itemId,
      feedback_type: feedbackType,
      status: "queued"
    };
  });
}

function startSession(payload) {
  return request("/api/sessions/start", {
    method: "POST",
    data: payload
  }).catch(() => ({
    ...mockSession,
    id: `mock-session-${Date.now()}`,
    goal_text: payload.goal_text || "",
    output_language: payload.output_language || "zh-CN",
    duration_minutes: payload.duration_minutes,
    status: "running"
  }));
}

function finishSession(sessionId, payload = {}) {
  return request(`/api/sessions/${sessionId}/finish`, {
    method: "POST",
    data: payload
  }).catch(() => ({
    session: {
      ...mockSession,
      ...getCurrentFocusRuntimeFallback(),
      id: sessionId,
      status: "finished"
    }
  }));
}

function getSession(sessionId) {
  return request(`/api/sessions/${sessionId}`)
    .then((res) => {
      void flushPendingQueue(8);
      return { ...res, _fromMock: false };
    })
    .catch(() => {
      const fallback = getCurrentFocusRuntimeFallback();
      return {
        ...mockSession,
        id: sessionId || fallback.session_id,
        goal_text: fallback.goal_text,
        duration_minutes: fallback.duration_minutes,
        status: fallback.is_active_session ? "running" : mockSession.status,
        _fromMock: true
      };
    });
}

function getLatestSession() {
  return request("/api/sessions/latest")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => {
      const fallback = getCurrentFocusRuntimeFallback();
      return {
        ...mockSession,
        id: fallback.session_id,
        goal_text: fallback.goal_text,
        duration_minutes: fallback.duration_minutes,
        status: fallback.is_active_session ? "running" : mockSession.status,
        _fromMock: true
      };
    });
}

function previewTodoCalendarImport(sessionId, payload = {}) {
  return request(`/api/sessions/${sessionId}/todo-calendar-preview`, {
    method: "POST",
    data: payload
  });
}

function importTodoCalendar(sessionId, payload = {}) {
  return request(`/api/sessions/${sessionId}/todo-calendar-import`, {
    method: "POST",
    data: payload
  });
}

function createTask(payload) {
  return request("/api/tasks", {
    method: "POST",
    data: payload
  }).then((res) => {
    trackEvent("task_submit", {
      task_type: payload.task_type,
      status: "ok"
    });
    return res;
  }).catch(() => {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    enqueuePendingOperation({
      type: "task",
      payload
    });
    trackEvent("task_submit", {
      task_type: payload.task_type,
      status: "queued"
    });
    const contentMap = {
      export_markdown_summary:
        `# ${t(language, "summary.markdownTitle", "Markdown 总结")}\n\n- ${t(language, "summary.localSession", "后端未连接，当前为本地演示 session")}\n- ${t(language, "summary.placeholder", "点击上方按钮后展示结果")}`,
      export_reading_list: `# ${t(language, "summary.readingListTitle", "稍后读清单")}\n\n1. ${t(language, "summary.sample.readA", "示例内容 A")}\n2. ${t(language, "summary.sample.readB", "示例内容 B")}`,
      export_todo_draft: `# ${t(language, "summary.todoDraftTitle", "待办草稿")}\n\n- [ ] ${t(language, "summary.sample.todo1", "示例任务 A")}\n- [ ] ${t(language, "summary.sample.todo2", "示例任务 B")}`,
      export_exec_brief: "# 老板简报\n\n- 当前为本地演示结果，建议优先同步高价值内容与风险变化。",
      export_sales_brief: "# 销售 Brief\n\n- 当前为本地演示结果，建议整理下一步拜访重点。",
      export_outreach_draft: "# 外联草稿\n\n您好，结合最近的公开动态，我们整理了几条适合继续沟通的观察。",
      export_watchlist_digest: "# Watchlist Digest\n\n- 当前为本地演示结果，建议连接 API 后查看真实 watchlist 变化。",
      export_knowledge_markdown: `# ${t(language, "knowledge.title", "知识卡片")}\n\n${t(language, "knowledge.content", "卡片内容")}`,
      export_knowledge_bundle_markdown: `# ${t(language, "knowledge.batchExportTitle", "知识库批量导出")}\n\n- ${t(language, "knowledge.batchExportCount", "卡片数量")}: ${(payload.input_payload && payload.input_payload.entry_ids && payload.input_payload.entry_ids.length) || 0}`,
      export_research_report_markdown:
        `# ${((payload.input_payload && payload.input_payload.report && payload.input_payload.report.report_title) || t(language, "inbox.researchTitle", "关键词研究报告"))}\n\n${((payload.input_payload && payload.input_payload.report && payload.input_payload.report.executive_summary) || "本地研究导出内容")}`
    };
    return {
      id: `mock-task-${Date.now()}`,
      task_type: payload.task_type,
      status: "done",
      queued: true,
      output_payload: {
        content: contentMap[payload.task_type] || "本地输出",
        filename: /export_knowledge/.test(payload.task_type) ? `knowledge-${Date.now()}.md` : undefined
      }
    };
  });
}

function getWorkBuddyHealth() {
  return request("/api/workbuddy/health")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      status: "ok",
      signature_required: false,
      integration_mode: "local_webhook_adapter",
      official_tencent_connected: false,
      provider_label: "WorkBuddy-compatible local webhook adapter",
      requested_mode: "auto",
      official_cli_detected: false,
      official_cli_authenticated: false,
      official_cli_auth_detail: "API unavailable, fallback to local adapter",
      official_gateway_configured: false,
      official_gateway_reachable: false,
      active_roles: [
        "session summary export",
        "reading list export",
        "todo draft export",
        "knowledge markdown export",
        "research report export",
        "focus assistant delegation",
      ],
      _fromMock: true
    }));
}

function sendWorkBuddyWebhook(payload) {
  return request("/api/workbuddy/webhook", {
    method: "POST",
    data: payload
  }).catch(() => {
    const language = (getApp().globalData.preferences || {}).language || "zh-CN";
    return ({
    accepted: true,
    event_type: payload.event_type || "ping",
    request_id: payload.request_id || "",
    message: "mock fallback",
    signature_check: "mock_fallback",
    task: payload.task_type
      ? {
          id: `mock-workbuddy-task-${Date.now()}`,
          task_type: payload.task_type,
          session_id: payload.session_id || null,
          status: "done",
          output_payload: {
            content:
              payload.task_type === "export_markdown_summary"
                ? `# ${t(language, "summary.markdownTitle", "Markdown 总结")}\n\n- WorkBuddy mock fallback`
                : payload.task_type === "export_todo_draft"
                  ? `# ${t(language, "summary.todoDraftTitle", "待办草稿")}\n\n- [ ] WorkBuddy mock fallback`
                  : payload.task_type === "export_knowledge_markdown"
                    ? `# ${t(language, "knowledge.title", "知识卡片")}\n\n${t(language, "knowledge.content", "卡片内容")}`
                    : payload.task_type === "export_knowledge_bundle_markdown"
                      ? `# ${t(language, "knowledge.batchExportTitle", "知识库批量导出")}\n\n- ${t(language, "knowledge.batchExportCount", "卡片数量")}: ${(payload.input_payload && payload.input_payload.entry_ids && payload.input_payload.entry_ids.length) || 0}`
                : `# ${t(language, "summary.readingListTitle", "稍后读清单")}\n\n1. WorkBuddy mock fallback`
            ,
            filename: /export_knowledge/.test(payload.task_type || "") ? `knowledge-${Date.now()}.md` : undefined
          }
        }
      : null,
    callback: {
      attempted: false,
      ok: null,
      status_code: null,
      detail: null
    },
    _fromMock: true
  });
  });
}

function detectMimeType(filePath) {
  const lower = String(filePath || "").toLowerCase();
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".jpeg") || lower.endsWith(".jpg")) return "image/jpeg";
  return "image/jpeg";
}

function readFileAsBase64(filePath) {
  return new Promise((resolve, reject) => {
    wx.getFileSystemManager().readFile({
      filePath,
      encoding: "base64",
      success(res) {
        resolve(String(res.data || ""));
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

function ingestOCRImage(payload) {
  const filePath = payload && payload.filePath;
  if (!filePath) {
    return Promise.reject(new Error("filePath is required"));
  }
  const mimeType = (payload && payload.mime_type) || detectMimeType(filePath);
  return readFileAsBase64(filePath).then((imageBase64) => {
    return request("/api/collector/ocr/ingest", {
      method: "POST",
      data: {
        image_base64: imageBase64,
        mime_type: mimeType,
        source_url: (payload && payload.source_url) || undefined,
        title_hint: (payload && payload.title_hint) || undefined,
        output_language: (payload && payload.output_language) || "zh-CN",
        deduplicate: payload && payload.deduplicate !== false
      }
    }).then((res) => {
      trackEvent("collector_ocr_ingest", { status: "ok" });
      return res;
    });
  }).catch((err) => {
    trackEvent("collector_ocr_ingest", { status: "failed" });
    throw err;
  });
}

function getCollectorStatus() {
  return request("/api/collector/status")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      user_id: "00000000-0000-0000-0000-000000000001",
      now: new Date().toISOString(),
      last_24h_total: 0,
      last_24h_ready: 0,
      last_24h_processing: 0,
      last_24h_failed: 0,
      last_24h_ocr_items: 0,
      latest_item_at: null,
      _fromMock: true
    }));
}

function getCollectorDaemonStatus() {
  return request("/api/collector/daemon/status")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      uptime_seconds: null,
      last_report_at: null,
      last_daily_summary_at: null,
      log_file: "",
      log_size_bytes: 0,
      source_file_count: 0,
      log_tail: [],
      _fromMock: true
    }));
}

function startCollectorDaemon() {
  return request("/api/collector/daemon/start", {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "start",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      uptime_seconds: null,
      last_report_at: null,
      last_daily_summary_at: null,
      log_file: "",
      log_size_bytes: 0,
      source_file_count: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function stopCollectorDaemon() {
  return request("/api/collector/daemon/stop", {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "stop",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      uptime_seconds: null,
      last_report_at: null,
      last_daily_summary_at: null,
      log_file: "",
      log_size_bytes: 0,
      source_file_count: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function runCollectorDaemonOnce(payload) {
  const query = [];
  if (payload && payload.output_language) {
    query.push(`output_language=${encodeURIComponent(payload.output_language)}`);
  }
  if (payload && payload.max_collect_per_cycle) {
    query.push(`max_collect_per_cycle=${encodeURIComponent(String(payload.max_collect_per_cycle))}`);
  }
  const path = `/api/collector/daemon/run-once${query.length ? `?${query.join("&")}` : ""}`;
  return request(path, {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "run_once",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      uptime_seconds: null,
      last_report_at: null,
      last_daily_summary_at: null,
      log_file: "",
      log_size_bytes: 0,
      source_file_count: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function getWechatAgentStatus() {
  return request("/api/collector/wechat-agent/status")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      run_once_running: false,
      run_once_pid: null,
      uptime_seconds: null,
      config_file: "",
      config_file_present: false,
      state_file: "",
      state_file_present: false,
      report_file: "",
      report_file_present: false,
      processed_hashes: 0,
      last_cycle_at: null,
      last_cycle_submitted: 0,
      last_cycle_submitted_new: 0,
      last_cycle_deduplicated_existing: 0,
      last_cycle_failed: 0,
      last_cycle_skipped_seen: 0,
      last_cycle_skipped_low_quality: 0,
      last_cycle_error: null,
      last_cycle_new_item_ids: [],
      log_file: "",
      log_size_bytes: 0,
      log_tail: [],
      _fromMock: true
    }));
}

function startWechatAgent() {
  return request("/api/collector/wechat-agent/start", {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "start",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      run_once_running: false,
      run_once_pid: null,
      uptime_seconds: null,
      config_file: "",
      config_file_present: false,
      state_file: "",
      state_file_present: false,
      report_file: "",
      report_file_present: false,
      processed_hashes: 0,
      last_cycle_at: null,
      last_cycle_submitted: 0,
      last_cycle_failed: 0,
      last_cycle_skipped_seen: 0,
      last_cycle_skipped_low_quality: 0,
      last_cycle_error: null,
      log_file: "",
      log_size_bytes: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function stopWechatAgent() {
  return request("/api/collector/wechat-agent/stop", {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "stop",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      run_once_running: false,
      run_once_pid: null,
      uptime_seconds: null,
      config_file: "",
      config_file_present: false,
      state_file: "",
      state_file_present: false,
      report_file: "",
      report_file_present: false,
      processed_hashes: 0,
      last_cycle_at: null,
      last_cycle_submitted: 0,
      last_cycle_failed: 0,
      last_cycle_skipped_seen: 0,
      last_cycle_skipped_low_quality: 0,
      last_cycle_error: null,
      log_file: "",
      log_size_bytes: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function runWechatAgentOnce(payload) {
  const query = [];
  if (payload && payload.output_language) {
    query.push(`output_language=${encodeURIComponent(payload.output_language)}`);
  }
  if (payload && payload.max_items) {
    query.push(`max_items=${encodeURIComponent(String(payload.max_items))}`);
  }
  if (payload && payload.start_batch_index) {
    query.push(`start_batch_index=${encodeURIComponent(String(payload.start_batch_index))}`);
  }
  if (payload && payload.wait) {
    query.push("wait=true");
  }
  const path = `/api/collector/wechat-agent/run-once${query.length ? `?${query.join("&")}` : ""}`;
  return request(path, {
    method: "POST",
    data: {}
  }).catch(() => ({
    action: "run_once",
    ok: false,
    message: "mock fallback",
    status: {
      running: false,
      pid: null,
      pid_from_file: null,
      pid_file_present: false,
      run_once_running: false,
      run_once_pid: null,
      uptime_seconds: null,
      config_file: "",
      config_file_present: false,
      state_file: "",
      state_file_present: false,
      report_file: "",
      report_file_present: false,
      processed_hashes: 0,
      last_cycle_at: null,
      last_cycle_submitted: 0,
      last_cycle_failed: 0,
      last_cycle_skipped_seen: 0,
      last_cycle_skipped_low_quality: 0,
      last_cycle_error: null,
      log_file: "",
      log_size_bytes: 0,
      log_tail: []
    },
    output: "",
    _fromMock: true
  }));
}

function getWechatAgentBatchStatus() {
  return request("/api/collector/wechat-agent/batch-status")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      running: false,
      total_items: 0,
      segment_items: 0,
      start_batch_index: 0,
      current_segment_index: 0,
      total_segments: 0,
      current_batch_index: 0,
      started_at: null,
      finished_at: null,
      submitted: 0,
      submitted_new: 0,
      submitted_url: 0,
      submitted_url_direct: 0,
      submitted_url_share_copy: 0,
      submitted_url_resolved: 0,
      submitted_ocr: 0,
      deduplicated_existing: 0,
      deduplicated_existing_url: 0,
      deduplicated_existing_url_direct: 0,
      deduplicated_existing_url_share_copy: 0,
      deduplicated_existing_url_resolved: 0,
      deduplicated_existing_ocr: 0,
      skipped_invalid_article: 0,
      skipped_seen: 0,
      failed: 0,
      validation_retries: 0,
      new_item_ids: [],
      last_message: null,
      last_error: null,
      live_report_running: false,
      live_report_batch: null,
      live_report_row: null,
      live_report_stage: null,
      live_report_detail: null,
      live_report_clicked: 0,
      live_report_submitted: 0,
      live_report_submitted_url: 0,
      live_report_submitted_url_direct: 0,
      live_report_submitted_url_share_copy: 0,
      live_report_submitted_url_resolved: 0,
      live_report_submitted_ocr: 0,
      live_report_skipped_seen: 0,
      live_report_skipped_invalid_article: 0,
      live_report_failed: 0,
      live_report_checkpoint_at: null,
      _fromMock: true
    }));
}

function runWechatAgentBatch(payload) {
  const query = [];
  if (payload && payload.output_language) {
    query.push(`output_language=${encodeURIComponent(payload.output_language)}`);
  }
  if (payload && payload.total_items) {
    query.push(`total_items=${encodeURIComponent(String(payload.total_items))}`);
  }
  if (payload && payload.segment_items) {
    query.push(`segment_items=${encodeURIComponent(String(payload.segment_items))}`);
  }
  if (payload && payload.start_batch_index) {
    query.push(`start_batch_index=${encodeURIComponent(String(payload.start_batch_index))}`);
  }
  const path = `/api/collector/wechat-agent/run-batch${query.length ? `?${query.join("&")}` : ""}`;
  return request(path, {
    method: "POST",
    data: {}
  }).catch(() => ({
    ok: false,
    message: "mock fallback",
    batch_status: {
      running: false,
      total_items: (payload && payload.total_items) || 0,
      segment_items: (payload && payload.segment_items) || 0,
      start_batch_index: (payload && payload.start_batch_index) || 0,
      current_segment_index: 0,
      total_segments: 0,
      current_batch_index: (payload && payload.start_batch_index) || 0,
      started_at: null,
      finished_at: null,
      submitted: 0,
      submitted_new: 0,
      deduplicated_existing: 0,
      skipped_invalid_article: 0,
      skipped_seen: 0,
      failed: 0,
      validation_retries: 0,
      new_item_ids: [],
      last_message: "mock fallback",
      last_error: null
    },
    _fromMock: true
  }));
}

function getWechatAgentConfig() {
  return request("/api/collector/wechat-agent/config")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      api_base: "http://127.0.0.1:8000",
      output_language: "zh-CN",
      wechat_bundle_id: "com.tencent.xinWeChat",
      wechat_app_name: "WeChat",
      list_origin: { x: 256, y: 258 },
      article_row_height: 92,
      rows_per_batch: 7,
      batches_per_cycle: 2,
      article_open_wait_sec: 1.4,
      article_capture_region: { x: 360, y: 110, width: 1020, height: 860 },
      article_extra_page_down: 0,
      page_down_wait_sec: 0.8,
      list_page_down_after_batch: 1,
      between_item_delay_sec: 0.7,
      dedup_max_hashes: 8000,
      min_capture_file_size_kb: 45,
      loop_interval_sec: 300,
      health_stale_minutes: 20,
      _fromMock: true
    }));
}

function updateWechatAgentConfig(payload) {
  return request("/api/collector/wechat-agent/config", {
    method: "PUT",
    data: payload || {}
  }).catch(() => ({ ...(payload || {}), _fromMock: true }));
}

function getWechatAgentCapturePreview() {
  return request("/api/collector/wechat-agent/preview-capture")
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      captured_at: new Date().toISOString(),
      image_base64: "",
      mime_type: "image/png",
      region: { x: 0, y: 0, width: 0, height: 0 },
      image_size_bytes: 0,
      _fromMock: true
    }));
}

function getWechatAgentOCRPreview(payload) {
  const query = [];
  if (payload && payload.output_language) {
    query.push(`output_language=${encodeURIComponent(payload.output_language)}`);
  }
  const path = `/api/collector/wechat-agent/preview-ocr${query.length ? `?${query.join("&")}` : ""}`;
  return request(path)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      captured_at: new Date().toISOString(),
      provider: "mock_ocr",
      confidence: 0,
      text_length: 0,
      title: "",
      body_preview: "",
      keywords: [],
      quality_ok: false,
      quality_reason: "mock_fallback",
      _fromMock: true
    }));
}

function getWechatAgentHealth(payload) {
  const query = [];
  if (payload && payload.stale_minutes) {
    query.push(`stale_minutes=${encodeURIComponent(String(payload.stale_minutes))}`);
  }
  const path = `/api/collector/wechat-agent/health${query.length ? `?${query.join("&")}` : ""}`;
  return request(path)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      healthy: false,
      checked_at: new Date().toISOString(),
      stale_threshold_minutes: 20,
      running: false,
      last_cycle_at: null,
      minutes_since_last_cycle: null,
      reasons: ["mock_fallback"],
      recommendation: "start",
      status: {
        running: false,
        pid: null,
        pid_from_file: null,
        pid_file_present: false,
        run_once_running: false,
        run_once_pid: null,
        uptime_seconds: null,
        config_file: "",
        config_file_present: false,
        state_file: "",
        state_file_present: false,
        report_file: "",
        report_file_present: false,
        processed_hashes: 0,
        last_cycle_at: null,
        last_cycle_submitted: 0,
        last_cycle_failed: 0,
        last_cycle_skipped_seen: 0,
        last_cycle_skipped_low_quality: 0,
        last_cycle_error: null,
        log_file: "",
        log_size_bytes: 0,
        log_tail: []
      },
      _fromMock: true
    }));
}

function runWechatAgentSelfHeal(payload) {
  const query = [];
  if (payload && payload.force) {
    query.push("force=true");
  }
  const path = `/api/collector/wechat-agent/self-heal${query.length ? `?${query.join("&")}` : ""}`;
  return request(path, {
    method: "POST",
    data: {}
  }).catch(() => ({
    ok: false,
    action: "none",
    message: "mock fallback",
    health_before: {
      healthy: false,
      checked_at: new Date().toISOString(),
      stale_threshold_minutes: 20,
      running: false,
      last_cycle_at: null,
      minutes_since_last_cycle: null,
      reasons: ["mock_fallback"],
      recommendation: "start",
      status: {
        running: false,
        pid: null,
        pid_from_file: null,
        pid_file_present: false,
        run_once_running: false,
        run_once_pid: null,
        uptime_seconds: null,
        config_file: "",
        config_file_present: false,
        state_file: "",
        state_file_present: false,
        report_file: "",
        report_file_present: false,
        processed_hashes: 0,
        last_cycle_at: null,
        last_cycle_submitted: 0,
        last_cycle_failed: 0,
        last_cycle_skipped_seen: 0,
        last_cycle_skipped_low_quality: 0,
        last_cycle_error: null,
        log_file: "",
        log_size_bytes: 0,
        log_tail: []
      }
    },
    health_after: {
      healthy: false,
      checked_at: new Date().toISOString(),
      stale_threshold_minutes: 20,
      running: false,
      last_cycle_at: null,
      minutes_since_last_cycle: null,
      reasons: ["mock_fallback"],
      recommendation: "start",
      status: {
        running: false,
        pid: null,
        pid_from_file: null,
        pid_file_present: false,
        run_once_running: false,
        run_once_pid: null,
        uptime_seconds: null,
        config_file: "",
        config_file_present: false,
        state_file: "",
        state_file_present: false,
        report_file: "",
        report_file_present: false,
        processed_hashes: 0,
        last_cycle_at: null,
        last_cycle_submitted: 0,
        last_cycle_failed: 0,
        last_cycle_skipped_seen: 0,
        last_cycle_skipped_low_quality: 0,
        last_cycle_error: null,
        log_file: "",
        log_size_bytes: 0,
        log_tail: []
      }
    },
    output: "",
    _fromMock: true
  }));
}

function processCollectorPending(limit = 60) {
  return request(`/api/collector/process-pending?limit=${limit}`, {
    method: "POST",
    data: {}
  }).catch(() => ({
    scanned: 0,
    processed: 0,
    failed: 0,
    remaining_pending: 0,
    item_ids: [],
    _fromMock: true
  }));
}

function listCollectorFailed(limit = 12) {
  return request(`/api/collector/failed?limit=${limit}`)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      total_failed: 0,
      items: [],
      _fromMock: true
    }));
}

function retryCollectorFailed(limit = 20) {
  return request(`/api/collector/retry-failed?limit=${limit}`, {
    method: "POST",
    data: {}
  }).catch(() => ({
    scanned: 0,
    retried: 0,
    ready: 0,
    failed: 0,
    item_ids: [],
    _fromMock: true
  }));
}

function getCollectorDailySummary(hours = 24, limit = 12) {
  return request(`/api/collector/daily-summary?hours=${hours}&limit=${limit}`)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      generated_at: new Date().toISOString(),
      range_hours: hours,
      total_ingested: 0,
      ready_count: 0,
      processing_count: 0,
      failed_count: 0,
      deep_read_count: 0,
      later_count: 0,
      skip_count: 0,
      top_items: [],
      failed_items: [],
      markdown: "# Collector Daily Summary\n\n- Local mock fallback\n",
      _fromMock: true
    }));
}

function listCollectorSources(limit = 200, enabledOnly = false) {
  const query = [`limit=${limit}`];
  if (enabledOnly) query.push("enabled_only=true");
  return request(`/api/collector/sources?${query.join("&")}`)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      total: 0,
      items: [],
      _fromMock: true
    }));
}

function createCollectorSource(payload) {
  return request("/api/collector/sources", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: `mock-source-${Date.now()}`,
    source_url: payload.source_url || "",
    source_domain: "mock.local",
    note: payload.note || "",
    enabled: payload.enabled !== false,
    last_collected_at: null,
    last_error: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function importCollectorSources(payload) {
  return request("/api/collector/sources/import", {
    method: "POST",
    data: payload
  }).catch(() => ({
    total: Array.isArray(payload.urls) ? payload.urls.length : 0,
    created: Array.isArray(payload.urls) ? payload.urls.length : 0,
    exists: 0,
    invalid: 0,
    results: [],
    _fromMock: true
  }));
}

function updateCollectorSource(sourceId, payload) {
  return request(`/api/collector/sources/${sourceId}`, {
    method: "PATCH",
    data: payload
  }).catch(() => ({
    id: sourceId,
    source_url: "",
    source_domain: "",
    note: payload.note || "",
    enabled: payload.enabled !== false,
    last_collected_at: null,
    last_error: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function deleteCollectorSource(sourceId) {
  return request(`/api/collector/sources/${sourceId}`, {
    method: "DELETE"
  }).catch(() => ({
    id: sourceId,
    status: "deleted",
    _fromMock: true
  }));
}

function listCollectorFeedSources(feedType = "rss") {
  const query = feedType ? `?feed_type=${encodeURIComponent(feedType)}` : "";
  return request(`/api/collector/feeds${query}`)
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      total: 0,
      items: [],
      _fromMock: true
    }));
}

function createCollectorRssSource(payload) {
  return request("/api/collector/rss/sources", {
    method: "POST",
    data: payload
  }).catch(() => ({
    id: `mock-feed-${Date.now()}`,
    feed_type: "rss",
    source_url: payload.source_url || "",
    title: payload.title || "本地 RSS 源",
    note: payload.note || "",
    enabled: true,
    status: "mock",
    last_synced_at: new Date().toISOString(),
    last_error: "",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    _fromMock: true
  }));
}

function pullCollectorRssFeeds(payload = {}) {
  return request("/api/collector/rss/pull", {
    method: "POST",
    data: payload
  })
    .then((res) => ({ ...res, _fromMock: false }))
    .catch(() => ({
      total: 0,
      results: [],
      _fromMock: true
    }));
}

function ingestNewsletter(payload) {
  return request("/api/collector/newsletter/ingest", {
    method: "POST",
    data: payload
  })
    .then((res) => normalizeExternalIngestResponse({ ...res, _fromMock: false }))
    .catch(() =>
      normalizeExternalIngestResponse(
        {
          item: {
            id: `mock-newsletter-${Date.now()}`,
            source_type: payload.source_url ? "plugin" : "text",
            source_url: payload.source_url || "",
            source_domain: payload.source_url ? "mock.local" : "newsletter.local",
            title: payload.title || "Newsletter 导入",
            raw_content: payload.raw_content || "",
            short_summary: "当前显示本地 newsletter 演示结果。",
            long_summary: "API 未连接，newsletter 已保留在本地演示态。",
            score_value: 3,
            action_suggestion: "later",
            output_language: payload.output_language || "zh-CN",
            ingest_route: "newsletter",
            status: "ready",
            created_at: new Date().toISOString(),
            tags: [{ tag_name: "Newsletter" }],
            _fromMock: true
          },
          ingest_route: "newsletter",
          content_acquisition_status: "body_acquired",
          resolver: "local_mock",
          body_source: "newsletter_body",
          fallback_used: true,
          metadata: { sender: payload.sender || "" },
          _fromMock: true
        },
        { sender: payload.sender || "" }
      )
    );
}

function uploadCollectorFile(payload) {
  return request("/api/collector/files/upload", {
    method: "POST",
    data: payload,
    timeout: 30000
  })
    .then((res) => normalizeExternalIngestResponse({ ...res, _fromMock: false }))
    .catch(() =>
      normalizeExternalIngestResponse(
        {
          item: {
            id: `mock-file-${Date.now()}`,
            source_type: payload.source_url ? "plugin" : "text",
            source_url: payload.source_url || "",
            source_domain: payload.source_url ? "mock.local" : "upload.local",
            title: payload.title || payload.file_name || "文件导入",
            raw_content: payload.extracted_text || "",
            short_summary: "当前显示本地文件导入演示结果。",
            long_summary: "API 未连接，文件已保留为本地演示导入结果。",
            score_value: 3,
            action_suggestion: "later",
            output_language: payload.output_language || "zh-CN",
            ingest_route: "file_upload",
            status: "ready",
            created_at: new Date().toISOString(),
            tags: [{ tag_name: "文件上传" }],
            _fromMock: true
          },
          ingest_route: "file_upload",
          content_acquisition_status: "body_acquired",
          resolver: "local_mock",
          body_source: "client_extract",
          fallback_used: true,
          metadata: { parse_status: "mock", parse_method: "client_extract" },
          _fromMock: true
        },
        { parse_status: "mock", parse_method: "client_extract" }
      )
    );
}

function ingestYouTubeTranscript(payload) {
  return request("/api/collector/youtube/ingest", {
    method: "POST",
    data: payload
  })
    .then((res) => normalizeExternalIngestResponse({ ...res, _fromMock: false }))
    .catch(() =>
      normalizeExternalIngestResponse(
        {
          item: {
            id: `mock-youtube-${Date.now()}`,
            source_type: "plugin",
            source_url: payload.video_url || "",
            source_domain: "youtube.com",
            title: payload.title || "YouTube Transcript",
            raw_content: payload.transcript_text || "",
            short_summary: "当前显示本地 YouTube transcript 演示结果。",
            long_summary: "API 未连接，视频转录已保留为本地演示结果。",
            score_value: 3,
            action_suggestion: "later",
            output_language: payload.output_language || "zh-CN",
            ingest_route: "youtube_transcript",
            status: "ready",
            created_at: new Date().toISOString(),
            tags: [{ tag_name: "YouTube" }],
            _fromMock: true
          },
          ingest_route: "youtube_transcript",
          content_acquisition_status: payload.transcript_text ? "body_acquired" : "title_only",
          resolver: "local_mock",
          body_source: payload.transcript_text ? "youtube_transcript" : "youtube_link_only",
          fallback_used: true,
          metadata: { transcript_attached: !!payload.transcript_text },
          _fromMock: true
        },
        { transcript_attached: !!payload.transcript_text }
      )
    );
}

module.exports = {
  listItems,
  listSavedItems,
  getItem,
  getPreferenceSummary,
  resetPreferences,
  boostPreference,
  getItemDiagnostics,
  getCollectorItemAttempts,
  interpretItem,
  addItemToKnowledge,
  listKnowledgeEntries,
  getKnowledgeEntry,
  getKnowledgeMarkdown,
  getKnowledgeBatchMarkdown,
  listRelatedKnowledgeEntries,
  updateKnowledgeEntry,
  updateKnowledgeEntriesBatch,
  getKnowledgeMergePreview,
  mergeKnowledgeEntries,
  getKnowledgeRule,
  updateKnowledgeRule,
  createFocusAssistantPlan,
  executeFocusAssistantAction,
  createItem,
  createResearchReport,
  createResearchJob,
  getResearchJob,
  getResearchJobTimeline,
  getResearchSourceSettings,
  updateResearchSourceSettings,
  listResearchConversations,
  createResearchConversation,
  getResearchConversation,
  sendResearchConversationMessage,
  getMobileDailyBrief,
  getResearchWorkspace,
  listResearchWatchlists,
  createResearchWatchlist,
  getResearchWatchlistChanges,
  refreshResearchWatchlist,
  getResearchEntityDetail,
  getResearchTrackingTopicVersion,
  getResearchTrackingTopicVersions,
  saveResearchView,
  deleteResearchView,
  saveResearchTrackingTopic,
  deleteResearchTrackingTopic,
  refreshResearchTrackingTopic,
  createResearchActionPlan,
  saveResearchReport,
  saveResearchActionCards,
  reprocessItem,
  submitFeedback,
  startSession,
  finishSession,
  getSession,
  getLatestSession,
  getApiHealth,
  previewTodoCalendarImport,
  importTodoCalendar,
  createTask,
  getWorkBuddyHealth,
  sendWorkBuddyWebhook,
  flushPendingQueue,
  ingestOCRImage,
  getCollectorStatus,
  getCollectorDaemonStatus,
  startCollectorDaemon,
  stopCollectorDaemon,
  runCollectorDaemonOnce,
  getWechatAgentStatus,
  getWechatAgentConfig,
  getWechatAgentHealth,
  getWechatAgentCapturePreview,
  getWechatAgentOCRPreview,
  getWechatAgentBatchStatus,
  runWechatAgentSelfHeal,
  startWechatAgent,
  stopWechatAgent,
  runWechatAgentBatch,
  runWechatAgentOnce,
  updateWechatAgentConfig,
  processCollectorPending,
  listCollectorFailed,
  retryCollectorFailed,
  getCollectorDailySummary,
  listCollectorSources,
  createCollectorSource,
  importCollectorSources,
  updateCollectorSource,
  deleteCollectorSource,
  listCollectorFeedSources,
  createCollectorRssSource,
  pullCollectorRssFeeds,
  ingestNewsletter,
  uploadCollectorFile,
  ingestYouTubeTranscript
};
