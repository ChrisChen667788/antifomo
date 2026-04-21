type TextRule = {
  pattern: RegExp;
  replacement: string;
};

const COMMERCIAL_RISK_REFERENCE_RULES: TextRule[] = [
  {
    pattern: /参考飞书多视图和\s*AlphaSense\s*式筛选/g,
    replacement: "用统一多视图和聚合筛选",
  },
  {
    pattern: /参考飞书式角色视图和规则提醒/g,
    replacement: "用角色视图和规则提醒",
  },
  {
    pattern: /参考\s*(飞书|AlphaSense|Salesforce|HubSpot|Gong|PitchBook|Feedly|Notion)[^，。；;\n]*/g,
    replacement: "用统一工作台编排",
  },
  {
    pattern: /AlphaSense\s*式筛选/g,
    replacement: "聚合筛选",
  },
  {
    pattern: /按\s*Salesforce\s*的\s*account planning\s*思路/g,
    replacement: "按账户规划工作流",
  },
  {
    pattern: /更接近\s*Salesforce\s*式可推进账户\/机会信号/g,
    replacement: "更接近可推进账户与机会信号",
  },
  {
    pattern: /(?:飞书|Salesforce|HubSpot|Gong|PitchBook|Feedly|Notion)\s*式角色视图/g,
    replacement: "角色视图",
  },
];

const PRODUCTIZED_DISPLAY_RULES: TextRule[] = [
  {
    pattern: /用统一多视图和聚合筛选，把账户、机会、提醒和审查队列用同一组 facet 联动起来。?/g,
    replacement: "用统一多视图和聚合筛选，将账户、机会、提醒和审查队列纳入同一组筛选维度。",
  },
  {
    pattern: /用角色视图和规则提醒，把同一批账户\/机会切换成不同职责的工作台。?/g,
    replacement: "用角色视图和规则提醒，将同一组账户与机会切换为不同职责视图。",
  },
  {
    pattern: /先看今天新增的重点内容和 watchlist 变化，再决定要不要刷新专题。?/gi,
    replacement: "优先查看当日重点增量与 Watchlist 变化，再决定是否刷新专题。",
  },
  {
    pattern: /把脚本级 audit \/ rewrite 收成可审查队列，先看 diff，再决定接受还是回退。?/gi,
    replacement: "将 audit / rewrite 治理沉淀为可审查队列，支持先查看 diff，再决定接受或回退。",
  },
  {
    pattern: /把专题刷新结果沉淀成变化摘要，快速知道今天新增了什么。?/g,
    replacement: "将专题刷新结果沉淀为变化摘要，集中查看当日新增内容。",
  },
  {
    pattern: /适合直接转成会前简报、拜访策略或外联任务的条目。?/g,
    replacement: "可直接转为会前简报、拜访策略或外联任务的条目。",
  },
  {
    pattern: /把 Watchlist 变化、推进风险和重点异常汇总到一处。?/g,
    replacement: "集中汇总 Watchlist 变化、推进风险和重点异常。",
  },
  {
    pattern: /把冲突结论和低置信章节集中出来，优先二次核验。?/g,
    replacement: "集中呈现冲突结论和低置信章节，优先安排二次核验。",
  },
  {
    pattern: /把进入路径、预算确认和交付物按阶段拆成 close plan。?/gi,
    replacement: "将进入路径、预算确认和交付物按阶段拆解为 Close Plan。",
  },
  {
    pattern: /把预算、证据、联系人和标杆缺口变成可执行的风险缓释列表。?/g,
    replacement: "将预算、证据、联系人和标杆缺口整理为可执行的风险缓释列表。",
  },
  {
    pattern: /把研报、机会、Watchlist 变化和冲突审查状态放到同一条推进时间线上。?/g,
    replacement: "将研报、机会、Watchlist 变化和冲突审查状态统一到同一条推进时间线。",
  },
];

function applyTextRules(value: string, rules: TextRule[]): string {
  let next = String(value || "");
  rules.forEach(({ pattern, replacement }) => {
    next = next.replace(pattern, replacement);
  });
  return next;
}

function finalizeDisplayText(value: string): string {
  return String(value || "")
    .replace(/，\s*，/g, "，")
    .replace(/。\s*。/g, "。")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function sanitizeCommercialRiskCopy(value: string): string {
  return finalizeDisplayText(applyTextRules(value, COMMERCIAL_RISK_REFERENCE_RULES));
}

export function sanitizeExternalDisplayText(value: string): string {
  return finalizeDisplayText(
    applyTextRules(
      applyTextRules(value, COMMERCIAL_RISK_REFERENCE_RULES),
      PRODUCTIZED_DISPLAY_RULES,
    ),
  );
}

export function sanitizeExternalDisplayList(values: string[]): string[] {
  const seen = new Set<string>();
  return (Array.isArray(values) ? values : [])
    .map((value) => sanitizeExternalDisplayText(String(value || "")))
    .filter((value) => {
      if (!value || seen.has(value)) {
        return false;
      }
      seen.add(value);
      return true;
    });
}
