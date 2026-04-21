const nowIso = new Date().toISOString();

const feedItems = [
  {
    id: "mock-item-1",
    source_type: "url",
    source_url: "https://36kr.com/p/ai-agent-browser",
    source_domain: "36kr.com",
    title: "AI Agent 浏览器进入加速期",
    short_summary: "多家厂商在过去两周发布 Agent Browser，竞争点聚焦自动执行与隐私保护。",
    long_summary:
      "近期 Agent Browser 赛道快速升温，产品形态从问答助手转向可执行网页任务。文章指出，自动填写、网页理解、流程执行和权限控制是关键差异点。对知识工作者而言价值在于减少重复网页操作，提升信息处理效率，但稳定性和权限边界仍需持续观察。",
    score_value: 4.2,
    action_suggestion: "deep_read",
    status: "ready",
    created_at: nowIso,
    recommendation_score: 82,
    recommendation_bucket: "deep_read",
    recommendation_reason: ["信息增量较高", "主题匹配较高", "内容新鲜度较高"],
    tags: [{ tag_name: "AI Agent" }, { tag_name: "浏览器" }, { tag_name: "创业" }]
  },
  {
    id: "mock-item-2",
    source_type: "text",
    source_url: "",
    source_domain: "local-note",
    title: "行业招聘趋势速记",
    short_summary: "岗位从通用 PM 向 AI 工作流落地方向倾斜，企业更看重自动化项目经验。",
    long_summary:
      "这段内容总结了近期岗位需求变化。企业在 JD 中提高了自动化、AI 工具使用与业务流程理解相关要求。对于求职者，短期建议是补齐可落地案例，中期建议围绕效率提升做可量化成果。",
    score_value: 3.4,
    action_suggestion: "later",
    status: "ready",
    created_at: nowIso,
    recommendation_score: 63,
    recommendation_bucket: "later",
    recommendation_reason: ["与目标相关", "信息密度中等"],
    tags: [{ tag_name: "求职" }, { tag_name: "AI" }]
  }
];

const savedItems = [feedItems[0]];

const mockSession = {
  id: "mock-session-1",
  goal_text: "整理 AI 行业求职材料",
  duration_minutes: 25,
  status: "finished",
  summary_text:
    "你已完成本次 25 分钟专注，期间新增信息未打断当前任务。建议先处理两条深读内容，再把低价值信息归档。",
  metrics: {
    new_content_count: 5,
    deep_read_count: 2,
    later_count: 2,
    skip_count: 1
  },
  items: [
    {
      id: "mock-item-1",
      title: "AI Agent 浏览器进入加速期",
      source_domain: "36kr.com",
      short_summary: "多家厂商在过去两周发布 Agent Browser。",
      action_suggestion: "deep_read",
      score_value: 4.2,
      tags: ["AI Agent", "浏览器"]
    }
  ]
};

module.exports = {
  feedItems,
  savedItems,
  mockSession
};
