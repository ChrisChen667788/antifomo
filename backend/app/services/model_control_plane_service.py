from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import ssl
import threading
from typing import Any
from urllib import error, request

from app.core.config import BACKEND_DIR


MODEL_POLICY_VERSION = "2026-08-07.1"
MODEL_ENV_FIELDS = {
    "openai_model": "OPENAI_MODEL",
    "openai_vision_model": "OPENAI_VISION_MODEL",
    "strategy_openai_model": "STRATEGY_OPENAI_MODEL",
}

_MODEL_UPDATE_LOCK = threading.Lock()
_SAFE_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,199}$")
_NON_CHAT_MARKERS = (
    "embedding",
    "embed-",
    "rerank",
    "whisper",
    "tts",
    "speech",
    "transcribe",
    "moderation",
    "dall-e",
    "image-gen",
    "gpt-image",
    "sora",
    "realtime",
)
_UNSUPPORTED_RUNTIME_MARKERS = (
    "codex",
    "computer-use",
    "deep-research",
    "search-preview",
)
_LIGHTWEIGHT_MARKERS = ("mini", "nano", "small", "lite", "flash", "haiku", "turbo")

ModelCatalogFetcher = Callable[[dict[str, Any]], list[dict[str, Any]]]
RuntimeRefresh = Callable[[], None]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _effective_remote_status(settings: Any, role: str) -> tuple[str, str]:
    strategy = role == "strategy"
    provider = settings.strategy_llm_provider if strategy else settings.llm_provider
    api_key = settings.strategy_openai_api_key if strategy else settings.openai_api_key
    if provider == "mock":
        return "mock", "local"
    if api_key:
        return provider, "configured"
    if not strategy and settings.llm_fallback_to_mock:
        return "mock", "fallback"
    return "disabled", "disabled"


def _runtime_routes(settings: Any) -> list[dict[str, Any]]:
    generation_effective, generation_status = _effective_remote_status(settings, "generation")
    strategy_effective, strategy_status = _effective_remote_status(settings, "strategy")
    vision_model = settings.openai_vision_model or settings.openai_model
    if settings.ocr_provider == "local":
        vision_effective = "ocrmac"
        vision_status = "local"
    elif settings.ocr_provider == "mock":
        vision_effective = "mock"
        vision_status = "local"
    else:
        vision_effective = "ocrmac -> openai -> mock" if settings.ocr_provider == "auto" else generation_effective
        vision_status = generation_status

    return [
        {
            "key": "generation",
            "label": "通用生成路由",
            "provider": settings.llm_provider,
            "effective_provider": generation_effective,
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
            "strategy": f"结构化输出：{settings.langchain_structured_output_method or '关闭'}",
            "fallback": (
                "通用内容失败可回退 deterministic mock；正式研报不回退 mock"
                if settings.llm_fallback_to_mock and not getattr(settings, "research_llm_fallback_to_mock", False)
                else "远程失败回退 deterministic mock"
                if settings.llm_fallback_to_mock
                else "不回退 mock"
            ),
            "status": generation_status,
            "upgrade_managed": settings.llm_provider != "mock",
        },
        {
            "key": "strategy",
            "label": "复杂策略路由",
            "provider": settings.strategy_llm_provider,
            "effective_provider": strategy_effective,
            "model": settings.strategy_openai_model,
            "base_url": settings.strategy_openai_base_url,
            "strategy": "低温度独立推理，用于范围锁定与策略复核",
            "fallback": "失败时保留原报告或规则结果，不降级到 mock 策略",
            "status": strategy_status,
            "upgrade_managed": settings.strategy_llm_provider != "mock",
        },
        {
            "key": "vision",
            "label": "视觉识别路由",
            "provider": settings.ocr_provider,
            "effective_provider": vision_effective,
            "model": vision_model,
            "base_url": settings.openai_base_url,
            "strategy": "auto 模式优先 macOS Vision，失败后调用远程视觉模型",
            "fallback": "本地 OCR -> 远程视觉 -> mock",
            "status": vision_status,
            "upgrade_managed": settings.llm_provider != "mock" and settings.ocr_provider in {"auto", "openai"},
        },
        {
            "key": "reranker",
            "label": "研究重排路由",
            "provider": settings.research_cross_encoder_backend,
            "effective_provider": settings.research_cross_encoder_backend,
            "model": settings.research_cross_encoder_model,
            "base_url": None,
            "strategy": "Cross Encoder 仅用于研究来源相关性重排",
            "fallback": "不可用时继续使用规则排序",
            "status": "local" if settings.research_cross_encoder_rerank_enabled else "disabled",
            "upgrade_managed": False,
        },
        {
            "key": "decision_embedding",
            "label": "Decision Studio 语义向量路由",
            "provider": settings.decision_embedding_provider,
            "effective_provider": settings.decision_embedding_provider,
            "model": settings.decision_embedding_model,
            "base_url": None,
            "strategy": (
                "真实 SentenceTransformer 向量写入不可变来源段落，查询与索引模型必须一致；"
                f"device={settings.decision_embedding_device}，"
                f"cache={settings.decision_embedding_cache_dir or 'default'}"
            ),
            "fallback": "严格模式阻断；非严格模式显式标记 lexical_fallback",
            "status": (
                "local"
                if settings.decision_embedding_enabled and settings.decision_embedding_provider != "disabled"
                else "disabled"
            ),
            "upgrade_managed": False,
        },
        {
            "key": "workbuddy",
            "label": "专注助手动作路由",
            "provider": "CodeBuddy / WorkBuddy",
            "effective_provider": settings.workbuddy_mode,
            "model": getattr(settings, "workbuddy_official_model", None),
            "base_url": settings.workbuddy_official_gateway_url,
            "strategy": (
                f"{settings.workbuddy_mode} 模式；CLI 显式锁定 {settings.workbuddy_official_model}，"
                "执行结果回写 requested/effective model"
            ),
            "fallback": "官方链路不可用时按 WorkBuddy 模式回退本地任务执行",
            "status": "external",
            "upgrade_managed": False,
        },
        {
            "key": "deterministic",
            "label": "确定性规则路由",
            "provider": "rule_based",
            "effective_provider": "rule_based",
            "model": None,
            "base_url": None,
            "strategy": "URL、文本块、评分规则与本地解析器直接执行",
            "fallback": "无模型依赖",
            "status": "local",
            "upgrade_managed": False,
        },
    ]


_MODULE_BINDINGS = (
    ("research_generation", "研报主报告生成", "研究", "generation", "基于检索证据生成结构化主报告"),
    ("research_strategy", "研报范围规划与策略复核", "研究", "strategy", "独立策略模型先锁定范围，再复核商业策略"),
    ("item_summary", "收藏内容摘要", "采集", "generation", "生成短摘要、长摘要和展示标题"),
    ("item_tagging", "收藏内容自动打标", "采集", "generation", "生成主题标签与关键词"),
    ("item_scoring", "收藏内容价值评分", "推荐", "generation", "生成质量、可信度和新颖度分数"),
    ("session_summary", "专注会话总结", "专注", "generation", "汇总本轮阅读、行动项和后续建议"),
    ("knowledge_insight", "知识条目洞察", "知识库", "generation", "解释内容价值并生成行动洞察"),
    ("vision_ocr", "截图与长图 OCR", "采集", "vision", "本地 Vision 优先，必要时调用视觉模型"),
    ("research_reranker", "研究来源重排", "研究", "reranker", "本地 Cross Encoder 对候选来源重排"),
    ("decision_semantic_search", "Decision Studio 语义检索", "Decision Studio", "decision_embedding", "来源范围硬过滤后执行真实段落向量检索"),
    ("decision_document_parser", "Decision Studio 文档解析", "Decision Studio", "deterministic", "原生 OOXML、HTML、文本和 PDF 解析；可选 Docling 增强"),
    ("focus_assistant", "专注助手动作执行", "专注", "workbuddy", "通过 CodeBuddy / WorkBuddy 编排可确认动作"),
    ("wechat_parser", "微信收藏导入与解析", "采集", "strategy", "确定性解析 URL 与文本块；摘要、标签和评分进入 Claude 策略路由"),
)


def build_model_control_plane_snapshot(settings: Any) -> dict[str, Any]:
    routes = _runtime_routes(settings)
    route_map = {route["key"]: route for route in routes}
    modules: list[dict[str, Any]] = []
    for key, label, area, route_key, strategy in _MODULE_BINDINGS:
        route = route_map[route_key]
        modules.append(
            {
                "key": key,
                "label": label,
                "area": area,
                "route_key": route_key,
                "provider": route["effective_provider"],
                "model": route["model"],
                "strategy": strategy,
                "fallback": route["fallback"],
                "status": route["status"],
                "upgrade_managed": route["upgrade_managed"],
            }
        )
    return {
        "generated_at": _now_iso(),
        "policy_version": MODEL_POLICY_VERSION,
        "routes": routes,
        "modules": modules,
    }


def _catalog_route(settings: Any, role: str) -> dict[str, Any]:
    strategy = role == "strategy"
    return {
        "route_key": role,
        "label": "复杂策略路由" if strategy else "通用生成与视觉路由",
        "provider": settings.strategy_llm_provider if strategy else settings.llm_provider,
        "base_url": settings.strategy_openai_base_url if strategy else settings.openai_base_url,
        "api_key": settings.strategy_openai_api_key if strategy else settings.openai_api_key,
        "fallback_api_key": settings.strategy_openai_fallback_api_key if strategy else settings.openai_fallback_api_key,
        "timeout_seconds": settings.strategy_openai_timeout_seconds if strategy else settings.openai_timeout_seconds,
        "verify_ssl": settings.openai_verify_ssl,
        "ca_bundle": settings.openai_ca_bundle,
        "organization": settings.openai_organization,
        "project": settings.openai_project,
    }


def _ssl_context(route: dict[str, Any]) -> ssl.SSLContext | None:
    if not route["verify_ssl"]:
        return ssl._create_unverified_context()
    if route["ca_bundle"]:
        return ssl.create_default_context(cafile=str(route["ca_bundle"]))
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def fetch_openai_compatible_models(route: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = str(route["base_url"] or "").rstrip("/")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {route['api_key']}",
        "User-Agent": "anti-fomo-model-scanner/1.0",
    }
    if route.get("organization"):
        headers["OpenAI-Organization"] = str(route["organization"])
    if route.get("project"):
        headers["OpenAI-Project"] = str(route["project"])
    req = request.Request(f"{base_url}/models", headers=headers, method="GET")
    timeout = max(5, min(int(route["timeout_seconds"] or 20), 30))
    with request.urlopen(req, timeout=timeout, context=_ssl_context(route)) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("provider returned an invalid model catalog")
    return [row for row in rows if isinstance(row, dict)]


def _model_exclusion(model_id: str) -> str:
    lowered = model_id.lower()
    if any(marker in lowered for marker in _NON_CHAT_MARKERS):
        return "不是聊天生成模型"
    if any(marker in lowered for marker in _UNSUPPORTED_RUNTIME_MARKERS):
        return "需要当前应用未使用的专用运行时"
    return ""


def _version_score(model_id: str) -> int:
    lowered = model_id.lower()
    patterns = (
        r"gpt[-_/]?(\d+)(?:[.\-_](\d+))?",
        r"claude(?:-[a-z]+)?[-_/]?(\d+)(?:[.\-_](\d+))?",
        r"gemini[-_/]?(\d+)(?:[.\-_](\d+))?",
        r"(?:deepseek|qwen|glm|kimi)[-_/a-z]*(\d+)(?:[.\-_](\d+))?",
        r"\bo(\d+)(?:[.\-_](\d+))?",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            major = min(int(match.group(1)), 20)
            minor = min(int(match.group(2) or 0), 20)
            return major * 10 + minor
    return 0


def _family_base(model_id: str, role: str) -> tuple[int, str]:
    lowered = model_id.lower()
    if "claude" in lowered:
        tier = 800 if "opus" in lowered else 690 if "sonnet" in lowered else 560
        return tier + (100 if role == "strategy" and "opus" in lowered else 20), "Claude 系列"
    if "gpt" in lowered:
        role_bonus = 80 if role in {"generation", "vision"} else 35
        return 820 + role_bonus, "GPT 系列"
    if re.search(r"(^|[/_-])o\d", lowered):
        return 830 + (100 if role == "strategy" else 20), "OpenAI 推理系列"
    if "gemini" in lowered:
        tier = 780 if "pro" in lowered else 640
        return tier + (60 if role == "vision" else 25), "Gemini 系列"
    if "deepseek" in lowered:
        return 720 + (80 if role == "strategy" and any(v in lowered for v in ("reason", "-r")) else 20), "DeepSeek 系列"
    if "qwen" in lowered:
        return 690 + (45 if any(v in lowered for v in ("max", "plus")) else 0), "Qwen 系列"
    if any(family in lowered for family in ("glm", "kimi")):
        return 660, "通用旗舰系列"
    return 400, "未识别通用系列"


def _capabilities(model_id: str) -> list[str]:
    lowered = model_id.lower()
    if _model_exclusion(model_id):
        return []
    capabilities = ["generation", "strategy"]
    vision_markers = ("vision", "-vl", "multimodal", "gpt-4o", "gpt-5", "claude-3", "claude-4", "gemini")
    if any(marker in lowered for marker in vision_markers):
        capabilities.append("vision")
    return capabilities


def _score_model(model_id: str, role: str) -> tuple[int, str]:
    exclusion = _model_exclusion(model_id)
    if exclusion:
        return -1, exclusion
    capabilities = _capabilities(model_id)
    if role not in capabilities:
        return -1, f"不具备 {role} 能力"
    score, family = _family_base(model_id, role)
    score += _version_score(model_id)
    lowered = model_id.lower()
    if any(marker in lowered for marker in _LIGHTWEIGHT_MARKERS):
        score -= 180
    if role != "vision" and any(marker in lowered for marker in ("vision", "-vl", "multimodal")):
        score -= 70
    if any(marker in lowered for marker in ("pro", "opus", "max", "ultra", "thinking", "reasoner")):
        score += 45
    if any(marker in lowered for marker in ("preview", "beta", "experimental", "exp")):
        score -= 35
    if role == "vision" and any(marker in lowered for marker in ("vision", "-vl", "multimodal")):
        score += 90
    return score, f"{family}，按旗舰等级、版本和 {role} 适配度排序"


def _scan_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, error.HTTPError):
        if exc.code in {401, 403}:
            return "access_denied", f"模型目录请求被拒绝（HTTP {exc.code}），请检查密钥权限或额度。"
        if exc.code == 429:
            return "rate_limited", "模型目录请求触发限流，请稍后重试。"
        return "provider_http_error", f"供应商模型目录返回 HTTP {exc.code}。"
    if isinstance(exc, error.URLError):
        return "connection_error", "无法连接模型供应商，请检查地址、网络或证书设置。"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "invalid_catalog", "供应商返回的模型目录格式无效。"
    return "scan_failed", "模型目录扫描失败。"


def scan_supported_models(
    settings: Any,
    *,
    fetcher: ModelCatalogFetcher = fetch_openai_compatible_models,
) -> dict[str, Any]:
    routes = [_catalog_route(settings, "generation"), _catalog_route(settings, "strategy")]
    route_results: list[dict[str, Any]] = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    cache: dict[tuple[str, str, str], tuple[list[dict[str, Any]] | None, tuple[str, str] | None]] = {}

    for route in routes:
        provider = str(route["provider"] or "")
        public_route = {
            "route_key": route["route_key"],
            "label": route["label"],
            "provider": provider,
            "base_url": route["base_url"],
        }
        if provider == "mock":
            route_results.append(
                {**public_route, "status": "skipped", "model_count": 0, "models": [], "message": "Mock 路由无需远程扫描。"}
            )
            continue
        credential_candidates = [
            ("primary", route.get("api_key")),
            ("fallback", route.get("fallback_api_key")),
        ]
        credential_candidates = [
            (label, api_key)
            for index, (label, api_key) in enumerate(credential_candidates)
            if api_key and api_key not in [item[1] for item in credential_candidates[:index]]
        ]
        if not credential_candidates:
            route_results.append(
                {
                    **public_route,
                    "status": "blocked",
                    "model_count": 0,
                    "models": [],
                    "error_code": "missing_api_key",
                    "message": "未配置 API Key，无法扫描模型目录。",
                }
            )
            continue

        catalog: list[dict[str, Any]] | None = None
        scan_error: tuple[str, str] | None = None
        credential_used = "primary"
        for credential_label, api_key in credential_candidates:
            candidate_route = {**route, "api_key": api_key}
            cache_key = (provider, str(route["base_url"] or ""), str(api_key or ""))
            if cache_key not in cache:
                try:
                    cache[cache_key] = (fetcher(candidate_route), None)
                except Exception as exc:
                    cache[cache_key] = (None, _scan_error(exc))
            catalog, scan_error = cache[cache_key]
            credential_used = credential_label
            if scan_error is None:
                break
        if scan_error is not None:
            error_code, message = scan_error
            route_results.append(
                {
                    **public_route,
                    "status": "blocked",
                    "model_count": 0,
                    "models": [],
                    "error_code": error_code,
                    "message": message,
                }
            )
            continue

        model_ids: list[str] = []
        for raw in catalog or []:
            model_id = str(raw.get("id") or "").strip()
            if not model_id or not _SAFE_MODEL_ID.fullmatch(model_id):
                continue
            model_ids.append(model_id)
            merged = rows_by_id.setdefault(
                model_id,
                {
                    "id": model_id,
                    "owned_by": str(raw.get("owned_by") or ""),
                    "created": int(raw["created"]) if isinstance(raw.get("created"), (int, float)) else None,
                    "routes": [],
                },
            )
            if route["route_key"] not in merged["routes"]:
                merged["routes"].append(route["route_key"])
        unique_ids = sorted(set(model_ids), key=str.lower)
        status = "ready" if unique_ids else "blocked"
        route_results.append(
            {
                **public_route,
                "status": status,
                "model_count": len(unique_ids),
                "models": unique_ids,
                "error_code": "" if unique_ids else "empty_catalog",
                "message": (
                    f"主密钥不可用，已使用备用密钥；发现 {len(unique_ids)} 个模型。"
                    if unique_ids and credential_used == "fallback"
                    else f"已发现 {len(unique_ids)} 个模型。"
                    if unique_ids
                    else "供应商模型目录为空。"
                ),
            }
        )

    models: list[dict[str, Any]] = []
    for raw in rows_by_id.values():
        exclusion = _model_exclusion(raw["id"])
        scores: dict[str, int] = {}
        reasons: list[str] = []
        for role in ("generation", "strategy", "vision"):
            score, reason = _score_model(raw["id"], role)
            scores[role] = score
            if score >= 0:
                reasons.append(reason)
        models.append(
            {
                **raw,
                "capabilities": _capabilities(raw["id"]),
                "excluded": bool(exclusion),
                "exclusion_reason": exclusion,
                "scores": scores,
                "rank_reason": reasons[0] if reasons else exclusion,
            }
        )
    models.sort(key=lambda row: (-max(row["scores"].values(), default=-1), row["id"].lower()))

    route_models = {row["route_key"]: set(row["models"]) for row in route_results if row["status"] == "ready"}
    current_by_role = {
        "generation": settings.openai_model,
        "strategy": settings.strategy_openai_model,
        "vision": settings.openai_vision_model or settings.openai_model,
    }
    route_by_role = {"generation": "generation", "strategy": "strategy", "vision": "generation"}
    recommendations: list[dict[str, Any]] = []
    for role, route_key in route_by_role.items():
        eligible_ids = route_models.get(route_key, set())
        eligible = [row for row in models if row["id"] in eligible_ids and row["scores"].get(role, -1) >= 0]
        if not eligible:
            continue
        selected = max(eligible, key=lambda row: (row["scores"][role], int(row["created"] or 0), row["id"]))
        recommendations.append(
            {
                "role": role,
                "route_key": route_key,
                "model": selected["id"],
                "current_model": current_by_role[role],
                "change_required": selected["id"] != current_by_role[role],
                "score": selected["scores"][role],
                "reason": selected["rank_reason"],
            }
        )

    ready_routes = sum(row["status"] == "ready" for row in route_results)
    blocked_routes = sum(row["status"] == "blocked" for row in route_results)
    required_roles = {
        "generation" if settings.llm_provider != "mock" else "",
        "strategy" if settings.strategy_llm_provider != "mock" else "",
        "vision" if settings.llm_provider != "mock" and settings.ocr_provider in {"auto", "openai"} else "",
    } - {""}
    recommendation_roles = {row["role"] for row in recommendations}
    if required_roles.issubset(recommendation_roles) and not blocked_routes:
        status = "ready"
        message = f"扫描完成，共发现 {len(models)} 个模型，可安全执行整批升级。"
    elif ready_routes:
        status = "partial"
        message = f"扫描部分完成，共发现 {len(models)} 个模型；存在未就绪路由，整批升级已阻断。"
    else:
        status = "blocked"
        message = "未获得可用模型目录，整批升级已阻断。"

    return {
        "generated_at": _now_iso(),
        "policy_version": MODEL_POLICY_VERSION,
        "status": status,
        "total_discovered": len(models),
        "routes": route_results,
        "models": models,
        "recommendations": recommendations,
        "message": message,
    }


def _persist_model_env(env_path: Path, values: dict[str, str | None]) -> None:
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = original.splitlines()
    replacements = {MODEL_ENV_FIELDS[field]: value for field, value in values.items()}
    seen: set[str] = set()
    updated: list[str] = []
    for line in lines:
        match = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=", line)
        key = match.group(1) if match else ""
        if key in replacements:
            value = replacements[key]
            updated.append(f"{key}={value or ''}")
            seen.add(key)
        else:
            updated.append(line)
    for key, value in replacements.items():
        if key not in seen:
            updated.append(f"{key}={value or ''}")
    content = "\n".join(updated).rstrip("\n") + "\n"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = env_path.with_name(f".{env_path.name}.model-update-{os.getpid()}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    if env_path.exists():
        os.chmod(temp_path, env_path.stat().st_mode)
    os.replace(temp_path, env_path)


def refresh_llm_runtime_services() -> None:
    from app.services.llm_service import get_llm_service, get_research_llm_service, get_strategy_llm_service

    get_llm_service.cache_clear()
    get_research_llm_service.cache_clear()
    get_strategy_llm_service.cache_clear()
    generation_service = get_llm_service()

    from app.api import items
    from app.services import item_processor, session_service

    item_processor.summarizer.llm_service = generation_service
    item_processor.tagger.llm_service = generation_service
    item_processor.scorer.llm_service = generation_service
    item_processor.reset_wechat_processing_stack()
    session_service.session_summarizer.llm_service = generation_service
    items.interpreter.llm_service = generation_service


def upgrade_to_strongest_models(
    settings: Any,
    *,
    env_path: Path | None = None,
    fetcher: ModelCatalogFetcher = fetch_openai_compatible_models,
    runtime_refresh: RuntimeRefresh = refresh_llm_runtime_services,
) -> dict[str, Any]:
    scan = scan_supported_models(settings, fetcher=fetcher)
    previous = {
        "openai_model": settings.openai_model,
        "openai_vision_model": settings.openai_vision_model,
        "strategy_openai_model": settings.strategy_openai_model,
    }
    if scan["status"] != "ready":
        return {
            "generated_at": _now_iso(),
            "status": "blocked",
            "previous_models": previous,
            "applied_models": previous,
            "changed_fields": [],
            "persisted": False,
            "runtime_reloaded": False,
            "message": "模型扫描未全部就绪，未修改任何配置。",
            "scan": scan,
        }

    recommendations = {row["role"]: row["model"] for row in scan["recommendations"]}
    vision_managed = settings.llm_provider != "mock" and settings.ocr_provider in {"auto", "openai"}
    target = {
        "openai_model": recommendations.get("generation", settings.openai_model),
        "openai_vision_model": (
            recommendations.get("vision", settings.openai_vision_model or settings.openai_model)
            if vision_managed
            else settings.openai_vision_model
        ),
        "strategy_openai_model": recommendations.get("strategy", settings.strategy_openai_model),
    }
    changed_fields = [field for field, value in target.items() if value != previous[field]]
    if not changed_fields:
        return {
            "generated_at": _now_iso(),
            "status": "no_change",
            "previous_models": previous,
            "applied_models": target,
            "changed_fields": [],
            "persisted": False,
            "runtime_reloaded": False,
            "message": "当前已是扫描结果中的最强模型，无需更新。",
            "scan": scan,
        }

    if any(not target[field] or not _SAFE_MODEL_ID.fullmatch(str(target[field])) for field in changed_fields):
        return {
            "generated_at": _now_iso(),
            "status": "blocked",
            "previous_models": previous,
            "applied_models": previous,
            "changed_fields": [],
            "persisted": False,
            "runtime_reloaded": False,
            "message": "推荐结果包含不安全的模型标识，未修改配置。",
            "scan": scan,
        }

    if (
        "strategy_openai_model" in changed_fields
        and bool(getattr(settings, "strategy_model_qualification_required", False))
    ):
        from app.services.strategy_model_qualification_service import load_strategy_model_qualification

        qualification = load_strategy_model_qualification(
            baseline_model=str(previous["strategy_openai_model"] or ""),
            candidate_model=str(target["strategy_openai_model"] or ""),
            max_age_days=int(getattr(settings, "strategy_model_qualification_max_age_days", 30)),
        )
        if qualification is None:
            return {
                "generated_at": _now_iso(),
                "status": "blocked",
                "previous_models": previous,
                "applied_models": previous,
                "changed_fields": [],
                "persisted": False,
                "runtime_reloaded": False,
                "message": "策略模型尚未通过匹配的固定证据 A/B qualification，未修改配置。",
                "scan": scan,
            }

    resolved_env_path = env_path or (BACKEND_DIR / ".env")
    with _MODEL_UPDATE_LOCK:
        original_env = resolved_env_path.read_text(encoding="utf-8") if resolved_env_path.exists() else None
        try:
            _persist_model_env(resolved_env_path, target)
            for field, value in target.items():
                setattr(settings, field, value)
            runtime_refresh()
        except Exception:
            for field, value in previous.items():
                setattr(settings, field, value)
            if original_env is None:
                resolved_env_path.unlink(missing_ok=True)
            else:
                resolved_env_path.write_text(original_env, encoding="utf-8")
            try:
                runtime_refresh()
            except Exception:
                pass
            return {
                "generated_at": _now_iso(),
                "status": "blocked",
                "previous_models": previous,
                "applied_models": previous,
                "changed_fields": [],
                "persisted": False,
                "runtime_reloaded": False,
                "message": "配置写入或运行时刷新失败，已恢复升级前状态。",
                "scan": scan,
            }

    return {
        "generated_at": _now_iso(),
        "status": "applied",
        "previous_models": previous,
        "applied_models": target,
        "changed_fields": changed_fields,
        "persisted": True,
        "runtime_reloaded": True,
        "message": f"已更新 {len(changed_fields)} 个模型配置，并热刷新运行时。",
        "scan": scan,
    }
