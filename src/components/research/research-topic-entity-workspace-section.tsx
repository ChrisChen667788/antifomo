"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { useResearchTopicWorkspaceController } from "@/components/research/use-research-topic-workspace-controller";

type ResearchTopicWorkspaceController = ReturnType<typeof useResearchTopicWorkspaceController>;

type ResearchTopicEntityWorkspaceSectionProps = {
  controller: ResearchTopicWorkspaceController;
  t: (key: string, fallback: string) => string;
};

export function ResearchTopicEntityWorkspaceSection({
  controller,
  t,
}: ResearchTopicEntityWorkspaceSectionProps) {
  const {
    latestEntityGroups,
    selectedEntity,
    setSelectedEntityKey,
  } = controller;

  return (
    <>
      {latestEntityGroups.length ? (
        <section className="af-glass rounded-[30px] p-6">
          <p className="af-kicker">{t("research.entityWorkspace", "Entity Workspace")}</p>
          <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-3">
              {latestEntityGroups.map((group) => (
                <article key={group.key} className="rounded-[24px] border border-white/70 bg-white/70 p-4">
                  <p className="text-sm font-semibold text-slate-900">{group.title}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {group.items.map((entity) => (
                      <button
                        key={`${group.key}-${entity.canonical_name}`}
                        type="button"
                        onClick={() => setSelectedEntityKey(entity.canonical_name)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                          selectedEntity?.canonical_name === entity.canonical_name
                            ? "border-sky-300 bg-sky-50 text-sky-700"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        {entity.canonical_name}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <article className="rounded-[24px] border border-white/70 bg-white/70 p-5">
              {selectedEntity ? (
                <>
                  <p className="text-sm font-semibold text-slate-900">{selectedEntity.canonical_name}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {selectedEntity.entity_type} · {t("research.entityAliasCount", "别名")} {selectedEntity.aliases.length} ·{" "}
                    {t("research.entitySourceCount", "来源")} {selectedEntity.source_count}
                  </p>
                  {selectedEntity.aliases.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedEntity.aliases.map((alias) => (
                        <span key={alias} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                          {alias}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="mt-4 space-y-3">
                    {(selectedEntity.evidence_links || []).slice(0, 4).map((link) => (
                      <div
                        key={`${selectedEntity.canonical_name}-${link.url}`}
                        className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-3"
                      >
                        <a
                          href={normalizeExternalUrl(link.url)}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-medium text-slate-900 underline-offset-4 hover:text-sky-700 hover:underline"
                        >
                          {link.title}
                        </a>
                        <p className="mt-1 text-xs text-slate-500">
                          {[link.source_label, link.source_tier].filter(Boolean).join(" · ")}
                        </p>
                        <ExternalLinkActions url={link.url} className="mt-2" openLabel={t("research.openEvidenceLink", "网页打开")} />
                      </div>
                    ))}
                    {!selectedEntity.evidence_links?.length ? (
                      <p className="text-sm text-slate-500">
                        {t("research.entityEvidenceEmpty", "当前实体还没有稳定依据链接。")}
                      </p>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">{t("research.entityWorkspaceEmpty", "当前专题还没有整理出实体。")}</p>
              )}
            </article>
          </div>
        </section>
      ) : null}
    </>
  );
}
