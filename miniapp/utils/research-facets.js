const REGION_RULES = [
  { label: "全国", tokens: ["全国", "国家", "中央", "国务院", "国家级"] },
  { label: "北京", tokens: ["北京", "京津冀"] },
  { label: "上海", tokens: ["上海", "长三角"] },
  { label: "广东", tokens: ["广东", "广州", "深圳", "佛山", "东莞", "珠三角", "粤港澳"] },
  { label: "江苏", tokens: ["江苏", "南京", "苏州", "无锡", "常州", "徐州"] },
  { label: "浙江", tokens: ["浙江", "杭州", "宁波", "绍兴", "嘉兴", "温州"] },
  { label: "山东", tokens: ["山东", "济南", "青岛", "烟台"] },
  { label: "四川", tokens: ["四川", "成都"] },
  { label: "重庆", tokens: ["重庆", "渝"] },
  { label: "湖北", tokens: ["湖北", "武汉"] },
  { label: "河南", tokens: ["河南", "郑州"] },
  { label: "福建", tokens: ["福建", "福州", "厦门", "泉州"] },
  { label: "安徽", tokens: ["安徽", "合肥"] },
  { label: "陕西", tokens: ["陕西", "西安"] },
  { label: "湖南", tokens: ["湖南", "长沙"] },
  { label: "江西", tokens: ["江西", "南昌"] },
  { label: "广西", tokens: ["广西", "南宁"] },
  { label: "云南", tokens: ["云南", "昆明"] },
  { label: "东北", tokens: ["辽宁", "吉林", "黑龙江", "沈阳", "大连", "哈尔滨", "长春", "东北"] },
  { label: "西北", tokens: ["甘肃", "青海", "宁夏", "新疆", "西北", "乌鲁木齐", "兰州"] },
  { label: "西南", tokens: ["贵州", "云南", "西藏", "西南", "贵阳", "拉萨"] },
  { label: "华中", tokens: ["华中", "湖北", "湖南", "河南"] },
  { label: "华南", tokens: ["华南", "广东", "广西", "海南", "深圳", "广州"] },
  { label: "华东", tokens: ["华东", "上海", "江苏", "浙江", "山东", "安徽", "福建"] },
];

const INDUSTRY_RULES = [
  { label: "政务", tokens: ["政务", "政府", "财政", "发改", "住建", "公安", "信创", "国资", "智慧城市"] },
  { label: "医疗", tokens: ["医疗", "医院", "卫健", "医保", "疾控", "医共体"] },
  { label: "教育", tokens: ["教育", "高校", "职教", "学校", "校园"] },
  { label: "能源", tokens: ["能源", "电力", "电网", "新能源", "储能", "石油", "煤炭"] },
  { label: "制造", tokens: ["制造", "工业", "工厂", "汽车", "装备", "供应链"] },
  { label: "金融", tokens: ["金融", "银行", "证券", "保险", "资管"] },
  { label: "交通", tokens: ["交通", "轨道", "高速", "港口", "航运", "机场", "物流"] },
  { label: "文旅", tokens: ["文旅", "文博", "景区", "旅游", "会展"] },
  { label: "零售消费", tokens: ["零售", "消费", "商超", "门店", "电商"] },
  { label: "企业数字化", tokens: ["企业数字化", "ERP", "CRM", "办公", "协同", "SaaS"] },
  { label: "AI/大模型", tokens: ["大模型", "AI", "AIGC", "智能体", "算力", "MaaS"] },
  { label: "算力基础设施", tokens: ["算力", "数据中心", "智算", "云计算", "政务云", "云平台"] },
];

const ACTION_TYPE_LABELS = {
  industry_intelligence: "行业情报",
  solution_design: "方案设计",
  sales_strategy: "销售推进",
  bidding_strategy: "投标规划",
  outreach_strategy: "陌拜推进",
  ecosystem_strategy: "生态合作"
};

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function collectResearchText(entry) {
  const payload = (entry && entry.metadata_payload) || {};
  const report = payload.report || {};
  const card = payload.card || {};
  const sectionText = Array.isArray(report.sections)
    ? report.sections
        .flatMap((section) => [section && section.title ? section.title : "", ...((section && section.items) || [])])
        .join(" ")
    : "";
  return normalizeText(
    [
      entry && entry.title,
      entry && entry.content,
      report.keyword,
      report.research_focus,
      report.report_title,
      report.executive_summary,
      report.consulting_angle,
      ...((report.client_peer_moves || [])),
      ...((report.winner_peer_moves || [])),
      ...((report.competition_analysis || [])),
      ...((report.five_year_outlook || [])),
      sectionText,
      payload.keyword,
      card.summary,
      ...((card.evidence || [])),
      ...((card.recommended_steps || [])),
      card.action_type
    ].join(" ")
  ).toLowerCase();
}

function getReport(entry) {
  const payload = (entry && entry.metadata_payload) || {};
  return payload.report || null;
}

function includesAny(text, tokens) {
  return tokens.some((token) => text.includes(String(token).toLowerCase()));
}

function matchRule(text, rules, fallback) {
  for (const rule of rules) {
    if (rule.tokens.some((token) => text.includes(String(token).toLowerCase()))) {
      return rule.label;
    }
  }
  return fallback;
}

function getResearchActionTypeLabel(entry, fallback = "研报") {
  const payload = (entry && entry.metadata_payload) || {};
  const actionType = payload.card && payload.card.action_type ? payload.card.action_type : "";
  return ACTION_TYPE_LABELS[actionType] || fallback;
}

function getResearchFacets(entry) {
  const text = collectResearchText(entry);
  const isAction = entry && entry.source_domain === "research.action_card";
  return {
    region: matchRule(text, REGION_RULES, "未识别区域"),
    industry: matchRule(text, INDUSTRY_RULES, "综合行业"),
    actionType: isAction ? getResearchActionTypeLabel(entry, "其他动作") : "研报"
  };
}

function getResearchPerspectiveScore(entry, perspective) {
  if (perspective === "all") return 1;
  const text = collectResearchText(entry || {});
  const report = getReport(entry || {});
  const payload = (entry && entry.metadata_payload) || {};
  const actionType = payload.card && payload.card.action_type ? payload.card.action_type : "";
  const sourceCount = Number((report && report.source_count) || 0);
  const region = getResearchFacets(entry || {}).region;

  if (perspective === "regional") {
    let score = 0;
    if (region !== "未识别区域") score += 3;
    if (entry && entry.source_domain === "research.report") score += 2;
    if (sourceCount > 0) score += 1;
    if (includesAny(text, ["区域", "地市", "省级", "市级", "长三角", "粤港澳", "华东", "华南"])) score += 2;
    return score;
  }

  if (perspective === "client_followup") {
    let score = 0;
    if (actionType === "sales_strategy") score += 4;
    if (actionType === "outreach_strategy") score += 3;
    if (report && Array.isArray(report.client_peer_moves) && report.client_peer_moves.length) score += 2;
    if (includesAny(text, ["甲方", "客户", "拜访", "预算归口", "关键人", "销售", "跟进"])) score += 2;
    return score;
  }

  if (perspective === "bidding") {
    let score = 0;
    if (actionType === "bidding_strategy") score += 4;
    if (includesAny(text, ["招标", "投标", "采购", "中标", "预算", "招采", "二期", "三期", "四期", "标前"])) score += 3;
    if (report && Array.isArray(report.competition_analysis) && report.competition_analysis.length) score += 1;
    return score;
  }

  if (perspective === "ecosystem") {
    let score = 0;
    if (actionType === "ecosystem_strategy") score += 4;
    if (report && Array.isArray(report.winner_peer_moves) && report.winner_peer_moves.length) score += 2;
    if (includesAny(text, ["生态", "伙伴", "联合", "渠道", "集成商", "厂商", "联盟"])) score += 3;
    return score;
  }

  return 0;
}

function buildFacetOptions(values, allLabel) {
  const counts = new Map();
  (Array.isArray(values) ? values : []).forEach((value) => {
    if (!value) return;
    counts.set(value, (counts.get(value) || 0) + 1);
  });
  const sorted = [...counts.entries()]
    .sort((left, right) => {
      if (right[1] !== left[1]) return right[1] - left[1];
      return String(left[0]).localeCompare(String(right[0]), "zh-Hans-CN");
    })
    .map(([label]) => label);
  return [allLabel, ...sorted];
}

module.exports = {
  getResearchFacets,
  getResearchActionTypeLabel,
  getResearchPerspectiveScore,
  buildFacetOptions
};
