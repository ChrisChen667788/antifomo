export type SuggestedAction = "立即深读" | "稍后精读" | "可放心忽略";
export type SuggestedActionType = "deep_read" | "later" | "skip";

export interface FeedItem {
  id: string;
  title: string;
  source: string;
  tags: string[];
  summary: string;
  shortSummary: string;
  longSummary: string;
  valueScore: number;
  suggestedAction: SuggestedAction;
  suggestedActionType?: SuggestedActionType;
  recommendationReasons?: string[];
  whyRecommended?: string[];
  matchedPreferences?: string[];
  topicMatchScore?: number;
  sourceMatchScore?: number;
  preferenceVersion?: string;
  url: string;
  createdAt?: string;
  recommendationScore?: number;
}

export interface SessionMetrics {
  sessionId?: string;
  durationMinutes: number;
  goalText?: string;
  newContentCount: number;
  deepReadCount: number;
  laterCount: number;
  ignorableCount: number;
}

export const feedItems: FeedItem[] = [
  {
    id: "insight-001",
    title: "OpenAI 发布新一代推理模型基准结果",
    source: "OpenAI Research",
    tags: ["AI", "模型评测", "推理"],
    summary:
      "官方公布了新一代推理模型在数学、代码和长链路任务上的改进，尤其在多步规划稳定性上提升明显。对开发者来说，意味着在复杂代理任务中可减少兜底规则与重试逻辑。若你的产品强依赖复杂推理，这条值得关注。",
    shortSummary:
      "推理模型在复杂任务上稳定性明显提高，能减少多轮重试与规则兜底成本。",
    longSummary:
      "公告重点不是单一分数提升，而是多步规划时的鲁棒性和错误恢复能力。对应用层的直接影响是：代理任务里长链路失败率会下降，流程自动化中的人工介入阈值可以后移。如果你的产品当前因为模型不稳定而保守上线，这次进展可能改变投入产出比。",
    valueScore: 92,
    suggestedAction: "立即深读",
    suggestedActionType: "deep_read",
    recommendationReasons: ["信息增量高", "与 AI/Agent 主题高度相关", "来源可信度高"],
    url: "https://openai.com",
  },
  {
    id: "insight-002",
    title: "多家 SaaS 开始默认启用“AI 会议纪要”",
    source: "SaaS Weekly",
    tags: ["SaaS", "效率工具", "会议"],
    summary:
      "会议纪要 AI 功能从可选插件转向默认开启，竞争点从“能不能做”转为“是否可信可追溯”。这意味着你的产品若包含协作能力，需要尽快补齐可验证摘要和行动项追踪，否则体验会落后于用户预期。",
    shortSummary:
      "行业基线改变：AI 纪要从加分项变成标配，差异化转向可信与可追溯。",
    longSummary:
      "用户已经默认期待会后自动产出摘要、决策与任务列表。仅生成文本不再足够，真正价值在于可追溯来源、责任人确认和后续执行追踪。若产品还在“摘要正确率”阶段，建议尽快补全工作流闭环。",
    valueScore: 78,
    suggestedAction: "稍后精读",
    suggestedActionType: "later",
    recommendationReasons: ["行业基线正在变化", "对协作产品方向有参考价值", "可作为中优先级跟进"],
    url: "https://example.com/saas-weekly",
  },
  {
    id: "insight-003",
    title: "社媒热议新生产力框架：多数是旧概念重包装",
    source: "Maker Digest",
    tags: ["方法论", "效率", "热点"],
    summary:
      "本周爆火的生产力框架核心仍是目标拆分、时间盒和复盘，只是更换了命名与视觉包装。若你已有稳定执行系统，这类内容短期参考价值有限，投入时间可能大于收益。",
    shortSummary:
      "高热度不等于高价值，内容创新度低，适合快速略读而非深挖。",
    longSummary:
      "文章拆解了多个热门帖子，指出其结构与 GTD、番茄工作法及周复盘高度重合。对信息摄入策略来说，这类内容更适合作为认知校准而不是新体系学习。建议将其归入“可忽略池”，避免占用深度阅读配额。",
    valueScore: 38,
    suggestedAction: "可放心忽略",
    suggestedActionType: "skip",
    recommendationReasons: ["新增信息有限", "重复旧方法论", "优先级低可忽略"],
    url: "https://example.com/maker-digest",
  },
  {
    id: "insight-004",
    title: "浏览器厂商推进更细粒度权限控制草案",
    source: "Web Platform News",
    tags: ["Web", "隐私", "标准"],
    summary:
      "新的权限控制提案会把传感器、剪贴板、后台任务等能力按场景拆分，减少“一次授权长期放行”。对前端产品团队，意味着权限请求流程和降级体验要尽早重构，以避免后续兼容成本骤增。",
    shortSummary:
      "权限模型正在细化，前端授权与降级路径将成为必做项。",
    longSummary:
      "草案方向是最小权限与短时授权，目标是降低误授权风险。短期内可能出现不同浏览器策略并行，开发侧需要尽早引入能力检测、按需请求和失败后替代路径。越晚处理，后期修复成本越高。",
    valueScore: 85,
    suggestedAction: "立即深读",
    suggestedActionType: "deep_read",
    recommendationReasons: ["涉及产品兼容风险", "影响前端权限设计", "适合提前规划技术改造"],
    url: "https://example.com/web-platform-news",
  },
];

export const sessionMetrics: SessionMetrics = {
  sessionId: "demo-session-001",
  durationMinutes: 50,
  goalText: "整理 AI 行业求职材料",
  newContentCount: 14,
  deepReadCount: 4,
  laterCount: 4,
  ignorableCount: 6,
};

export function getItemById(id: string): FeedItem | undefined {
  return feedItems.find((item) => item.id === id);
}

export const savedItemIds = ["insight-001", "insight-004"];

export function getSavedItems(): FeedItem[] {
  return feedItems.filter((item) => savedItemIds.includes(item.id));
}
