# Research Center Gap Plan

## Competitor References

### AlphaSense
- Positioning: market intelligence and research workflow with source-grounded summaries.
- Strengths:
  - executive-summary-first reading flow
  - evidence-linked smart summaries
  - premium + public source blending
  - company / sector / event monitoring
- Gaps vs Anti-FOMO:
  - Anti-FOMO still has weaker evidence density scoring
  - topic report pages are less “workspace-like”
  - named-entity extraction is still sparse in low-signal queries
- Reference:
  - https://www.alpha-sense.com/platform/smart-summaries/

### Glean
- Positioning: enterprise knowledge workspace and collections.
- Strengths:
  - strong collection/workspace mental model
  - source connectors as first-class capability
  - clean filter + artifact organization
- Gaps vs Anti-FOMO:
  - research reports and action cards are still separated too loosely
  - saved views / report collections / reusable research workspaces are incomplete
- Reference:
  - https://docs.glean.com/user-guide/knowledge/collections/how-collections-work

### Perplexity
- Positioning: fast deep research with citations and asset generation.
- Strengths:
  - low-friction query -> report workflow
  - citation-first trust model
  - asset export path is very obvious
- Gaps vs Anti-FOMO:
  - research output still needs stronger inline citations and evidence anchors
  - report generation should expose search breadth / evidence confidence more clearly
- Reference:
  - https://www.perplexity.ai/help-center/en/articles/12528830-creating-assets-with-perplexity-overview

### CB Insights
- Positioning: market intelligence and competitive monitoring.
- Strengths:
  - competitor maps
  - company tracking and strategic movement framing
  - decision-oriented output
- Gaps vs Anti-FOMO:
  - competitor comparison is present but not yet rendered as a dedicated compare matrix
  - action-card workflow is stronger than our comparison workflow
- Reference:
  - https://www.cbinsights.com/platform

### Public Tender Data Platforms
- National Public Resource Trading Platform
  - https://www.ggzy.gov.cn/
- China Bidding Network
  - https://www.cecbid.org.cn/
- China Bidding Public Service Platform
  - http://www.cebpubservice.com/
- China Public Procurement
  - https://www.china-cpp.com/

## Current Gaps

### Data
- Need more official procurement and regional public-resource adapters.
- Need stronger extraction of:
  - buyer names
  - budget signals
  - winning vendors
  - project phase timing
  - leadership policy attention
- Need a more stable recurrent-refresh path for tracked topics so research can be re-run and versioned without manual copy/paste.
- Need better fallback search expansion when scoped keywords (region + industry + client) return sparse evidence.

### UX
- Research center still behaves like a filtered list before it behaves like a consulting workspace.
- Report detail should surface:
  - confidence
  - evidence density
  - named entities
  - compare matrix
  - recommended next moves

### Workflow
- Report -> action cards is good, but:
  - report -> compare matrix
  - report -> client follow-up package
  - report -> bidding timeline package
  are still missing.
- Long-term tracking topics need:
  - one-click refresh
  - last refreshed status
  - direct link to latest report
  - saved filters / saved views reuse

## Current Status Snapshot

- Done:
  - compare workspace route
  - evidence links in compare rows
  - benchmark case chips in compare rows
  - budget-range extraction in compare rows
  - saved views in research center
  - long-term tracking topics
  - one-click refresh for tracking topics
  - compliant procurement aggregate source label
- Still missing:
  - richer evidence-density scoring
  - report-version compare between refresh runs
  - dedicated recurring monitoring queue
  - stronger official-source hit rate on narrow keywords

## Compliant Public Extraction Stack

The research center should keep a clear line between:
- public, accessible, repeatable extraction
- licensed / partner data sources
- explicitly unsupported anti-protection / paywall bypass

Recommended public-page extraction stack:
- Crawl4AI for LLM-friendly extraction orchestration
  - https://github.com/unclecode/crawl4ai
- scrapy-playwright for JavaScript-heavy public pages
  - https://github.com/scrapy-plugins/scrapy-playwright
- trafilatura for article/body extraction and metadata cleanup
  - https://github.com/adbar/trafilatura
- browser-use for interactive public-page browsing tasks that require human-like navigation, but still on accessible pages
  - https://github.com/browser-use/browser-use

Recommended source mix:
- official procurement
- official public-resource trading
- official policy / speech / filing
- compliant procurement aggregators
- public industry media / public WeChat articles

Not in scope:
- paywall bypass
- login-wall circumvention
- unlicensed backend data scraping
- CAPTCHA / anti-bot evasion

## Next Development Plan

### Round A: Data Source Expansion
- Add official-source adapters:
  - compliant procurement aggregate replacement for unstable direct procurement crawling
  - Gov.cn policy / speech adapter
  - local public resource platform adapter by scoped region
- Add source confidence labels:
  - official procurement
  - official policy
  - official filing
  - industry media
  - tender aggregation

### Round B: Evidence & Entity Layer
- Add evidence density scoring per section.
- Add named-entity extraction panels:
  - buyers
  - budgets
  - winning vendors
  - ecosystem partners
  - key people
- Add “evidence insufficient” diagnostics by section.

### Round C: Research Workspace UX
- Add report compare matrix for:
  - buyer peers
  - winning vendors
  - benchmark cases
- Add saved views:
  - regional intelligence
  - client follow-up
  - bidding schedule
  - ecosystem partnership
- Add recurring topic refresh cards:
  - refresh status
  - latest report link
  - refresh notes
  - report version history

### Round D: Consulting Output Upgrade
- Add more formal memo layout:
  - thesis
  - evidence
  - implications
  - action plan
  - references
- Add export templates:
  - client briefing
  - bidding prep memo
  - ecosystem outreach memo

### Round E: Operationalization
- Add recurring monitoring topics.
- Add alerting for:
  - new procurement
  - new award
  - policy change
  - competitor movement

## Next Priority Iterations

1. Improve official-source hit rate for narrow queries by region + industry + buyer suffix expansion.
2. Add report version comparison across refresh runs.
3. Add compare workspace export with evidence appendix.
4. Add saved-topic scheduled refresh and failure diagnostics.
5. Add evidence confidence and source-quality badges to report sections.
