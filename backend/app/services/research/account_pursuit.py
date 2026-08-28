from __future__ import annotations

from collections.abc import Iterable

from app.schemas.research import (
    ResearchAccountPursuitCardOut,
    ResearchAccountPursuitPackOut,
    ResearchEntityEvidenceOut,
    ResearchReportResponse,
)
from app.services.content_extractor import normalize_text
from app.services.research.delivery_scope import requires_account_truth
from app.services.research.organization_identity import org_surface_variants


_PROCUREMENT_STAGE_TERMS = (
    ("采购意向", "intent"),
    ("招标公告", "tender"),
    ("公开招标", "tender"),
    ("竞争性磋商", "tender"),
    ("中标", "award"),
    ("成交", "award"),
)
_BUYER_ROLE_TERMS = ("采购人", "建设单位", "业主单位", "招标人", "需求方", "主管部门", "甲方")


def _dedupe(values: Iterable[str], limit: int = 8) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _source_text(source: object) -> str:
    return normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "search_query", "") or ""),
            ]
        )
    )


def _source_mentions(source: object, account: str) -> bool:
    text = _source_text(source).casefold()
    return any(variant.casefold() in text for variant in org_surface_variants(account) if normalize_text(variant))


def _stage(text: str) -> str:
    normalized = normalize_text(text)
    for token, stage in _PROCUREMENT_STAGE_TERMS:
        if token in normalized:
            return stage
    return "discovery" if any(token in normalized for token in _BUYER_ROLE_TERMS) else "unknown"


def _evidence_for_account(report: ResearchReportResponse, account: str) -> list[ResearchEntityEvidenceOut]:
    admissions_by_url = {
        normalize_text(row.url): row
        for row in report.research_source_admissions
        if row.decision == "accepted" and row.account_pursuit_eligible
    }
    evidence: list[ResearchEntityEvidenceOut] = []
    for source in report.sources:
        url = normalize_text(source.url)
        if not url or url not in admissions_by_url or not _source_mentions(source, account):
            continue
        evidence.append(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=url,
                source_label=source.source_label,
                source_tier=source.source_tier,
                anchor_text=source.search_query,
                excerpt=source.snippet,
                confidence_tone="high" if source.source_tier == "official" else "low",
            )
        )
    for ranked in report.top_target_accounts:
        if normalize_text(ranked.name) != normalize_text(account):
            continue
        for link in ranked.evidence_links:
            admission = admissions_by_url.get(normalize_text(link.url))
            if admission and link.url and link not in evidence:
                evidence.append(link)
    return evidence[:4]


def _account_names(report: ResearchReportResponse) -> list[str]:
    return _dedupe(
        [
            *(item.name for item in report.top_target_accounts),
            *report.target_accounts,
        ],
        limit=6,
    )


def build_account_pursuit_pack(report: ResearchReportResponse) -> ResearchAccountPursuitPackOut:
    cards: list[ResearchAccountPursuitCardOut] = []
    for account in _account_names(report):
        evidence_links = _evidence_for_account(report, account)
        if not evidence_links:
            continue
        evidence_text = " ".join(
            " ".join([link.title, link.excerpt, link.anchor_text or ""])
            for link in evidence_links
        )
        stage = _stage(evidence_text)
        role = next((term for term in _BUYER_ROLE_TERMS if term in evidence_text), "采购/建设责任主体")
        budget = next(
            (row for row in report.budget_signals if account in row and any(token in row for token in ("预算", "金额", "投资"))),
            "",
        )
        if not budget:
            budget = "未取得该账户可对外确认的预算金额。"
        current_signal = normalize_text(evidence_links[0].title or evidence_links[0].excerpt)
        facts = _dedupe(
            [
                f"公开来源将 {account} 标注为{role}或项目责任相关主体。",
                current_signal,
                *(row for row in report.tender_timeline if account in row),
            ],
            limit=4,
        )
        inferences = [
            "可进入账户核验与会前准备，但不得将未公开的预算、决策人或中标概率写成事实。",
        ]
        if stage in {"intent", "tender"}:
            inferences.append("应优先核对采购文件、技术参数和项目归口，再决定联合方案或投标投入。")
        else:
            inferences.append("当前仅能确认组织入口，需补采购意向、预算或项目阶段证据。")
        confidence = "high" if stage in {"intent", "tender", "award"} else "medium"
        cards.append(
            ResearchAccountPursuitCardOut(
                account_name=account,
                account_role=role,
                status="verified",
                confidence=confidence,  # type: ignore[arg-type]
                current_signal=current_signal,
                signal_kind="procurement" if stage in {"intent", "tender", "award"} else "owner",
                procurement_stage=stage,  # type: ignore[arg-type]
                budget_signal=budget,
                incumbent_or_partner="未取得可核验的既有供应商或伙伴证据。",
                facts=facts,
                inferences=inferences,
                evidence_links=evidence_links,
                next_proof_sources=["采购意向/招标公告原文", "预算批复或项目立项材料", "业务牵头部门公开入口"],
                next_action=f"在 10 个工作日内核验 {account} 的项目归口、采购阶段、技术参数和公开联系人。",
                timebox="10 个工作日",
            )
        )
    if cards:
        return ResearchAccountPursuitPackOut(
            status="ready",
            summary=f"已锁定 {len(cards)} 个具备本地角色证据的账户；其余判断按待核验线索处理。",
            verified_account_count=len(cards),
            cards=cards,
            market_scan_actions=["将外部案例保留在标杆池，不得进入账户优先级排序。"],
        )
    account_task = requires_account_truth(report.research_scope_contract)
    return ResearchAccountPursuitPackOut(
        status="evidence_recovery" if account_task else "market_scan",
        summary=(
            "当前没有可验证的本地采购/业主账户，已降级为市场扫描。"
            if account_task
            else "当前为行业市场扫描，尚未形成可直接推进的账户卡。"
        ),
        market_scan_actions=[
            "检索本地采购意向、招标公告、项目建设单位和业务牵头部门。",
            "将异地项目明确标记为外部标杆，不得作为本地预算或采购窗口。",
            "用户补充目标客户、已有关系或项目线索后再生成账户推进版。",
        ],
        blockers=["缺少具备本地归属、真实机构和采购/业主角色的直接证据。"],
    )
