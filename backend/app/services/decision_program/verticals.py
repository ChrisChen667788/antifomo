from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_program_entities import DecisionVerticalPack
from app.services.decision_program.common import canonical_digest, iso


VERTICAL_PACKS: tuple[dict[str, Any], ...] = (
    {
        "pack_key": "medical-evidence-cn",
        "sector": "medical",
        "title": "中国医疗循证决策包",
        "sources": ["国家卫生健康委员会", "国家药品监督管理局", "国家医保局", "中国临床试验注册中心"],
        "ontology": {"entities": ["医疗机构", "药品", "器械", "适应证", "临床终点"], "relation_policy": "evidence_required"},
        "contract": {"required_sections": ["适用范围", "临床证据", "合规约束", "风险与不确定性", "实施建议"]},
        "hard_negatives": ["新闻媒体名称不得识别为医疗机构", "产品宣传语不得识别为适应证", "未经批准的治疗建议"],
        "rubric": {"critical_dimensions": ["真实性", "证据等级", "监管时效", "患者安全"], "hard_fail": ["虚构机构", "无来源疗效数字"]},
    },
    {
        "pack_key": "financial-diligence-cn",
        "sector": "finance",
        "title": "中国金融尽调与投研证据包",
        "sources": ["中国人民银行", "国家金融监督管理总局", "中国证监会", "上海证券交易所", "深圳证券交易所"],
        "ontology": {"entities": ["发行人", "金融机构", "监管机构", "产品", "风险因子"], "relation_policy": "time_scoped"},
        "contract": {"required_sections": ["主体核验", "业务与财务", "监管与合规", "风险情景", "决策建议"]},
        "hard_negatives": ["媒体栏目不得识别为金融机构", "历史监管规则不得视为现行规则", "预测数字不得标记为事实"],
        "rubric": {"critical_dimensions": ["主体真实性", "财务血缘", "时点一致性", "风险披露"], "hard_fail": ["无来源财务数字", "忽略重大监管风险"]},
    },
    {
        "pack_key": "tourism-project-cn",
        "sector": "tourism",
        "title": "中国文旅项目策划与可研证据包",
        "sources": ["文化和旅游部", "国家发展改革委", "自然资源部", "国家统计局", "地方政府公报"],
        "ontology": {"entities": ["项目业主", "景区", "运营商", "投资机构", "生态伙伴", "客群"], "relation_policy": "entity_verified"},
        "contract": {"required_sections": ["资源本底", "市场与竞品", "产品策划", "投资测算", "合规约束", "运营实施"]},
        "hard_negatives": ["新闻栏目不得识别为公司", "景点别名不得识别为运营商", "未核验客流不得用于收益测算"],
        "rubric": {"critical_dimensions": ["实体真实性", "政策适配", "需求证据", "测算血缘", "落地性"], "hard_fail": ["虚构甲方或伙伴", "无来源投资收益"]},
    },
)


def seed_vertical_packs(db: Session) -> list[DecisionVerticalPack]:
    rows: list[DecisionVerticalPack] = []
    for definition in VERTICAL_PACKS:
        content = {
            "source_registry": [{"authority": value, "source_class": "official", "verification_required": True} for value in definition["sources"]],
            "ontology": definition["ontology"],
            "contract": definition["contract"],
            "hard_negatives": definition["hard_negatives"],
            "rubric": definition["rubric"],
        }
        digest = canonical_digest(content)
        existing = db.scalar(
            select(DecisionVerticalPack)
            .where(DecisionVerticalPack.pack_key == definition["pack_key"])
            .where(DecisionVerticalPack.version == "1.0.0")
        )
        if existing is not None:
            if existing.content_hash != digest:
                raise ValueError(f"Immutable vertical pack changed: {definition['pack_key']}")
            rows.append(existing)
            continue
        row = DecisionVerticalPack(
            pack_key=definition["pack_key"],
            version="1.0.0",
            sector=definition["sector"],
            title=definition["title"],
            status="validation_pending",
            source_registry_payload=content["source_registry"],
            ontology_payload=content["ontology"],
            contract_payload=content["contract"],
            hard_negatives_payload=content["hard_negatives"],
            review_rubric_payload=content["rubric"],
            licensing_payload={
                "license": "internal",
                "redistribution": "prohibited",
                "source_terms_review_required": True,
                "generated_content_customer_review_required": True,
            },
            benchmark_payload={"status": "blocked", "blockers": ["需要 >=100 个任务和 >=30 份独立专家复核 artifact。"]},
            content_hash=digest,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def record_vertical_pack_benchmark(
    db: Session,
    *,
    pack: DecisionVerticalPack,
    task_count: int,
    expert_review_count: int,
    pass_rate: float,
    critical_error_count: int,
    artifact_uri: str,
) -> DecisionVerticalPack:
    findings = [
        {"key": "task_count", "actual": task_count, "target": ">= 100", "status": "pass" if task_count >= 100 else "blocked"},
        {"key": "expert_review_count", "actual": expert_review_count, "target": ">= 30", "status": "pass" if expert_review_count >= 30 else "blocked"},
        {"key": "pass_rate", "actual": pass_rate, "target": ">= 0.90", "status": "pass" if pass_rate >= 0.90 else "blocked"},
        {"key": "critical_error_count", "actual": critical_error_count, "target": "= 0", "status": "pass" if critical_error_count == 0 else "blocked"},
        {"key": "artifact_uri", "actual": bool(artifact_uri.strip()), "target": "required", "status": "pass" if artifact_uri.strip() else "blocked"},
    ]
    status = "pass" if all(value["status"] == "pass" for value in findings) else "blocked"
    pack.benchmark_payload = {
        "status": status,
        "task_count": task_count,
        "expert_review_count": expert_review_count,
        "pass_rate": pass_rate,
        "critical_error_count": critical_error_count,
        "artifact_uri": artifact_uri.strip(),
        "findings": findings,
    }
    pack.status = "active" if status == "pass" else "validation_pending"
    db.commit()
    db.refresh(pack)
    return pack


def serialize_vertical_pack(pack: DecisionVerticalPack) -> dict[str, Any]:
    return {
        "id": str(pack.id),
        "pack_key": pack.pack_key,
        "version": pack.version,
        "sector": pack.sector,
        "title": pack.title,
        "status": pack.status,
        "source_registry": list(pack.source_registry_payload or []),
        "ontology": dict(pack.ontology_payload or {}),
        "contract": dict(pack.contract_payload or {}),
        "hard_negatives": list(pack.hard_negatives_payload or []),
        "review_rubric": dict(pack.review_rubric_payload or {}),
        "licensing": dict(pack.licensing_payload or {}),
        "benchmark": dict(pack.benchmark_payload or {}),
        "content_hash": pack.content_hash,
        "created_at": iso(pack.created_at),
    }
