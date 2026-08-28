"use client";

import type { ApiResearchIndustrySkillLibrary } from "@/lib/api/type-contracts/research-delivery";

type IndustrySkillPickerProps = {
  library: ApiResearchIndustrySkillLibrary | null;
  loading: boolean;
  enabled: boolean;
  selectedSkillIds: string[];
  disabled?: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onSelectionChange: (skillIds: string[]) => void;
};

export function IndustrySkillPicker({
  library,
  loading,
  enabled,
  selectedSkillIds,
  disabled = false,
  onEnabledChange,
  onSelectionChange,
}: IndustrySkillPickerProps) {
  const suggestedSkills = library?.suggested_skills || [];
  const knowledgeBase = library?.knowledge_base;
  const toggleSkill = (skillId: string) => {
    const isSelected = selectedSkillIds.includes(skillId);
    onSelectionChange(
      isSelected ? selectedSkillIds.filter((current) => current !== skillId) : [...selectedSkillIds, skillId].slice(0, 3),
    );
  };

  return (
    <section
      data-testid="industry-skill-picker"
      className="rounded-xl border border-[color-mix(in_srgb,var(--af-info)_24%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_6%,var(--af-surface-muted))] p-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--af-text-primary)]">本地行业资料技能</p>
          <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
            将外接资料盘中的行业框架和规范性检查加入本次方案交付，不替代项目证据或客户确认。
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-[var(--af-text-primary)]">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disabled}
            onChange={(event) => onEnabledChange(event.target.checked)}
            className="h-4 w-4 accent-[var(--af-info)]"
          />
          启用
        </label>
      </div>

      {loading ? <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">正在匹配本地行业资料...</p> : null}

      {!loading && library?.status === "available" ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs leading-5 text-[var(--af-text-secondary)]">
            已索引 {library.document_count} 份资料，沉淀 {library.skill_count} 个行业技能。最多选择 3 个技能。
          </p>
          {knowledgeBase ? (
            <div className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-[11px] leading-5 text-[var(--af-text-secondary)]">
              全文解析 {knowledgeBase.full_text_document_count}/{knowledgeBase.document_count} 份，RAG 分段 {knowledgeBase.passage_count} 条。
              {knowledgeBase.hybrid_search_enabled
                ? " 当前使用关键词 + 语义向量混合检索。"
                : " 当前仅可使用部分本地检索能力。"}
              {knowledgeBase.ocr_pending_count ? ` ${knowledgeBase.ocr_pending_count} 份扫描件待 OCR。` : ""}
            </div>
          ) : null}
          {suggestedSkills.length ? (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {suggestedSkills.map((skill) => {
                const selected = selectedSkillIds.includes(skill.skill_id);
                const documentTypes = Object.entries(skill.document_type_counts)
                  .slice(0, 3)
                  .map(([label, count]) => `${label} ${count} 份`)
                  .join(" / ");
                return (
                  <button
                    key={skill.skill_id}
                    type="button"
                    aria-pressed={selected}
                    disabled={disabled || !enabled}
                    onClick={() => toggleSkill(skill.skill_id)}
                    className={`rounded-lg border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                      selected
                        ? "border-[var(--af-info)] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-elevated))]"
                        : "border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] hover:border-[var(--af-info)]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-[var(--af-text-primary)]">{skill.name}</span>
                      <span className="text-[11px] text-[var(--af-info)]">{selected ? "已选择" : "调用"}</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-secondary)]">
                      全文 {skill.full_content_document_count}/{skill.document_count} 份{documentTypes ? ` · ${documentTypes}` : ""}
                    </p>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-xs leading-5 text-[var(--af-text-tertiary)]">当前场景未匹配到特定行业技能，可补充行业或垂直场景后重试。</p>
          )}
          {library.warnings.length ? (
            <p className="text-xs leading-5 text-[var(--af-warning)]">{library.warnings[0]}</p>
          ) : null}
          {knowledgeBase?.vector_fallback_reason ? (
            <p className="text-[11px] leading-5 text-[var(--af-text-tertiary)]">{knowledgeBase.vector_fallback_reason}</p>
          ) : null}
        </div>
      ) : null}

      {!loading && library?.status === "unavailable" ? (
        <p className="mt-3 text-xs leading-5 text-[var(--af-warning)]">
          {library.warnings[0] || "本地行业资料库暂不可用；本次输出不会使用该资料技能。"}
        </p>
      ) : null}
    </section>
  );
}
