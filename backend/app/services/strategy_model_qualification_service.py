from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.services.legacy_openai_adapter import OpenAILLMService
from app.services.llm_parser import parse_research_strategy_refine_response


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_PATH = PROJECT_ROOT / "output/model-qualification/strategy-latest.json"
StrategyRunner = Callable[[str, str, dict[str, str]], str]

_FIXED_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "tourism-procurement",
        "variables": {
            "keyword": "杭州智慧文旅公共服务平台",
            "research_focus": "核验建设主体、公开采购信号、游客服务范围和可执行推进路径",
            "output_language": "zh-CN",
            "scope_hints": json.dumps(
                {
                    "regions": ["杭州"],
                    "industries": ["智慧文旅"],
                    "clients": ["杭州市文化广电旅游局"],
                    "must_exclude_terms": ["天津", "银行", "芯片"],
                },
                ensure_ascii=False,
            ),
            "source_intelligence": json.dumps(
                {
                    "target_accounts": ["杭州市文化广电旅游局"],
                    "budget_signals": ["2026 年公开招标意向，范围含游客服务与运营分析"],
                    "ecosystem_partners": ["本地政务云与文旅运营服务商"],
                },
                ensure_ascii=False,
            ),
            "current_report": json.dumps(
                {
                    "report_title": "智慧文旅项目研究分析",
                    "executive_summary": "现有材料显示项目处于采购准备阶段。",
                    "consulting_angle": "继续跟踪。",
                },
                ensure_ascii=False,
            ),
        },
        "required_terms": ["杭州", "智慧文旅", "杭州市文化广电旅游局"],
        "evidence_terms": ["2026", "公开招标", "游客服务", "运营分析"],
        "forbidden_terms": ["天津", "银行", "芯片"],
    },
    {
        "case_id": "government-ai-governance",
        "variables": {
            "keyword": "南京政务人工智能服务",
            "research_focus": "核验市级主管部门、试点场景、合规前置条件和最小验证动作",
            "output_language": "zh-CN",
            "scope_hints": json.dumps(
                {
                    "regions": ["南京"],
                    "industries": ["数字政府"],
                    "clients": ["南京市数据局"],
                    "must_exclude_terms": ["上海", "消费金融", "游戏"],
                },
                ensure_ascii=False,
            ),
            "source_intelligence": json.dumps(
                {
                    "target_accounts": ["南京市数据局"],
                    "strategic_directions": ["政务问答、材料辅助和知识检索试点"],
                    "budget_signals": ["正式预算金额尚未公开"],
                    "leadership_focus": ["数据安全、模型评测和人工复核"],
                },
                ensure_ascii=False,
            ),
            "current_report": json.dumps(
                {
                    "report_title": "南京政务 AI 解决方案",
                    "executive_summary": "应先确认场景和边界。",
                    "consulting_angle": "建议开展试点。",
                },
                ensure_ascii=False,
            ),
        },
        "required_terms": ["南京", "数字政府", "南京市数据局"],
        "evidence_terms": ["政务问答", "知识检索", "数据安全", "人工复核"],
        "forbidden_terms": ["上海", "消费金融", "游戏"],
    },
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fixture_digest() -> str:
    payload = json.dumps(_FIXED_CASES, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _default_runner(settings: Any) -> StrategyRunner:
    def run(model: str, prompt_name: str, variables: dict[str, str]) -> str:
        service = OpenAILLMService(
            api_key=str(settings.strategy_openai_api_key or ""),
            fallback_api_key=settings.strategy_openai_fallback_api_key,
            base_url=settings.strategy_openai_base_url,
            model=model,
            temperature=settings.strategy_openai_temperature,
            timeout_seconds=settings.strategy_openai_timeout_seconds,
            organization=settings.openai_organization,
            project=settings.openai_project,
            verify_ssl=settings.openai_verify_ssl,
            ca_bundle=settings.openai_ca_bundle,
        )
        return service.run_prompt(prompt_name, variables)

    return run


def _evaluate_case(raw: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = parse_research_strategy_refine_response(raw)
    except Exception as exc:
        return {"score": 0, "valid": False, "error": exc.__class__.__name__, "output": {}}
    output = parsed.model_dump(mode="json")
    combined = " ".join(str(value or "") for value in output.values())
    required_hits = [term for term in case["required_terms"] if term in combined]
    evidence_hits = [term for term in case["evidence_terms"] if term in combined]
    forbidden_hits = [term for term in case["forbidden_terms"] if term in combined]
    action_hits = [
        term
        for term in ("核验", "验证", "对接", "推进", "并行", "试点", "工作流")
        if term in combined
    ]
    score = 25
    score += round(30 * len(required_hits) / max(1, len(case["required_terms"])))
    score += min(15, len(evidence_hits) * 5)
    score += 10 if action_hits else 0
    score += 20 if not forbidden_hits else 0
    return {
        "score": min(100, score),
        "valid": True,
        "required_hits": required_hits,
        "evidence_hits": evidence_hits,
        "action_hits": action_hits,
        "forbidden_hits": forbidden_hits,
        "output": output,
    }


def _write_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_strategy_model_qualification(
    settings: Any,
    *,
    baseline_model: str,
    candidate_model: str,
    runner: StrategyRunner | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    execute = runner or _default_runner(settings)
    model_results: dict[str, Any] = {}
    for label, model in (("baseline", baseline_model), ("candidate", candidate_model)):
        cases: list[dict[str, Any]] = []
        for case in _FIXED_CASES:
            raw = execute(model, "research_strategy_refine.txt", dict(case["variables"]))
            cases.append({"case_id": case["case_id"], **_evaluate_case(raw, case)})
        average = round(sum(int(row["score"]) for row in cases) / max(1, len(cases)), 2)
        model_results[label] = {
            "model": model,
            "average_score": average,
            "all_valid": all(bool(row["valid"]) for row in cases),
            "cases": cases,
        }
    baseline = model_results["baseline"]
    candidate = model_results["candidate"]
    passed = bool(
        candidate["all_valid"]
        and candidate["average_score"] >= 80
        and candidate["average_score"] >= baseline["average_score"]
    )
    payload = {
        "schema_version": "1.0",
        "created_at": _utc_now().isoformat(),
        "fixture_digest": _fixture_digest(),
        "prompt_name": "research_strategy_refine.txt",
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "status": "pass" if passed else "blocked",
        "decision": "promote_candidate" if passed else "keep_baseline",
        "minimum_candidate_score": 80,
        "results": model_results,
    }
    _write_artifact(artifact_path or DEFAULT_ARTIFACT_PATH, payload)
    return payload


def load_strategy_model_qualification(
    *,
    baseline_model: str,
    candidate_model: str,
    artifact_path: Path | None = None,
    max_age_days: int = 30,
) -> dict[str, Any] | None:
    path = artifact_path or DEFAULT_ARTIFACT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    if created_at < _utc_now() - timedelta(days=max(1, int(max_age_days))):
        return None
    if payload.get("fixture_digest") != _fixture_digest():
        return None
    if payload.get("baseline_model") != baseline_model or payload.get("candidate_model") != candidate_model:
        return None
    if payload.get("status") != "pass" or payload.get("decision") != "promote_candidate":
        return None
    return payload
