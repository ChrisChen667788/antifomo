from __future__ import annotations

from app.schemas.research import (
    ResearchCommercialBidPackOut,
    ResearchCommercialBuyerMapEntryOut,
    ResearchReportResponse,
)
from app.services.content_extractor import normalize_text


def build_commercial_bid_pack(report: ResearchReportResponse) -> ResearchCommercialBidPackOut:
    pursuit = report.account_pursuit_pack
    if pursuit.status != "ready" or not pursuit.cards:
        return ResearchCommercialBidPackOut(
            status="market_only",
            blockers=["无经核验的本地目标账户，禁止生成客户级投标推进判断。"],
            no_bid_triggers=[
                "采购主体或业主单位未被一手来源确认。",
                "预算、项目阶段或技术参数均不可核验。",
                "异地案例被误当作本地商机证据。",
            ],
            next_actions=[
                "先形成账户卡，再启动买方地图、资格核验和 win theme 设计。",
                "将当前材料作为市场扫描，不进入 bid/no-bid 评审。",
            ],
        )

    card = pursuit.cards[0]
    budget_is_verified = bool(card.budget_signal and "未取得" not in card.budget_signal)
    buyer_map = [
        ResearchCommercialBuyerMapEntryOut(
            role="采购/建设责任主体",
            organization=card.account_name,
            status="verified",
            evidence_links=card.evidence_links,
            next_proof="复核采购公告原文、统一社会信用主体与项目归口。",
        ),
        ResearchCommercialBuyerMapEntryOut(
            role="业务牵头部门",
            status="to_verify",
            next_proof="从项目公告、机构职责、公开联系人或客户会中确认业务 owner。",
        ),
        ResearchCommercialBuyerMapEntryOut(
            role="预算/采购归口",
            status="to_verify",
            next_proof="核验预算批复、采购意向、采购方式和时间节点。",
        ),
        ResearchCommercialBuyerMapEntryOut(
            role="信息化与安全合规",
            status="to_verify",
            next_proof="确认系统 owner、部署边界、数据分级和评审窗口。",
        ),
    ]
    stage_label = {
        "intent": "采购意向/立项核验阶段",
        "tender": "招标文件与资格预审阶段",
        "award": "中标/成交复盘与后续扩展线索阶段",
        "discovery": "组织入口与项目窗口核验阶段",
        "unknown": "项目阶段待核验",
    }.get(card.procurement_stage, "项目阶段待核验")
    verified_competitors = [item.name for item in report.top_competitors[:3] if normalize_text(item.name)]
    verified_partners = [item.name for item in report.top_ecosystem_partners[:3] if normalize_text(item.name)]
    return ResearchCommercialBidPackOut(
        status="ready_for_review",
        account_name=card.account_name,
        buyer_map=buyer_map,
        budget_route=(card.budget_signal if budget_is_verified else "预算来源、金额和采购方式尚待核验。"),
        procurement_calendar=[
            stage_label,
            "T+5 个工作日：确认采购主体、业务 owner、预算口径和公开联系人。",
            "T+10 个工作日：完成技术参数、既有系统、部署和合规约束访谈。",
            "T+15 个工作日：进入 bid/no-bid 评审，冻结联合方案与资格缺口。",
        ],
        competitor_or_incumbent_evidence=(
            [f"已核验竞品/既有供应商候选：{'、'.join(verified_competitors)}。"]
            if verified_competitors
            else ["未取得可作为既有供应商或竞品定论的直接证据。"]
        ),
        partner_role_fit=(
            [f"生态伙伴候选：{'、'.join(verified_partners)}；需逐项核验授权、区域覆盖和交付责任。"]
            if verified_partners
            else ["未锁定可核验伙伴，先按能力缺口规划联合体/集成商筛选。"]
        ),
        qualification_plan=[
            "核验采购方式、资格条件、业绩门槛、资质和本地交付要求。",
            "确认是否需要联合体、分包、原厂授权或本地服务承诺。",
            "建立资格缺口、责任人和关闭日期台账。",
        ],
        win_themes=[
            "用客户已验证的业务信号和采购阶段切入，避免以泛化产品能力替代需求事实。",
            "以一期可验收价值、可控集成范围和安全合规前置为主线。",
            "将外部标杆转化为能力参考，明确其不等于客户现状或预算。",
        ],
        loss_risks=[
            "项目阶段或预算仍未确认，投入可能早于真实采购窗口。",
            "客户既有系统、数据、安全与部署边界未知，方案可能返工。",
            "竞品和伙伴信息未被直接来源锚定，不能据此承诺排他或优势。",
        ],
        no_bid_triggers=[
            "采购主体、业务 owner 或预算路径在规定核验期内仍无法确认。",
            "关键资格、交付地域、数据安全或部署约束无法满足。",
            "只能依赖异地标杆或二手新闻，无法取得本地一手证据。",
            "客户拒绝确认一期验收范围、接口责任或付款条件。",
        ],
        next_actions=[card.next_action, "召开内部 bid/no-bid 会，逐项确认事实、假设、风险和退出条件。"],
    )
