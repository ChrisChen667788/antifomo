import { PageShell } from "@/components/layout/page-shell";
import { ResearchCompareMatrix } from "@/components/research/research-compare-matrix";

export default async function ResearchComparePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = (await searchParams) || {};
  const query = Array.isArray(resolved.query) ? resolved.query[0] : resolved.query || "";
  const region = Array.isArray(resolved.region) ? resolved.region[0] : resolved.region || "";
  const industry = Array.isArray(resolved.industry) ? resolved.industry[0] : resolved.industry || "";

  return (
    <PageShell
      title="对比矩阵"
      description="横向对比甲方、中标方、竞品与伙伴，优先查看预算、项目、战略与竞争压力。"
    >
      <ResearchCompareMatrix initialQuery={query} initialRegion={region} initialIndustry={industry} />
    </PageShell>
  );
}
