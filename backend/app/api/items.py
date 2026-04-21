from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import (
    Feedback,
    FocusSession,
    Item,
    SourcePreference,
    TopicPreference,
)
from app.schemas.items import (
    ItemBatchCreateRequest,
    ItemBatchCreateResponse,
    ItemBatchCreateResult,
    ItemCreateRequest,
    ItemFeedbackRequest,
    ItemFeedbackResponse,
    ItemInterpretRequest,
    ItemInterpretResponse,
    ItemKnowledgeSaveRequest,
    ItemKnowledgeSaveResponse,
    ItemListResponse,
    ItemOut,
    ItemReprocessRequest,
    ItemReprocessResponse,
)
from app.schemas.collector import ItemDiagnosticsOut
from app.services.collector_diagnostics import list_item_attempts, serialize_item_diagnostics
from app.services.feedback_service import apply_feedback
from app.services.content_extractor import extract_domain, normalize_text
from app.services.item_processing_runtime import process_item_by_id
from app.services.item_processing_runtime import process_item_in_session
from app.services.interpreter import Interpreter
from app.services.knowledge_service import (
    create_or_get_knowledge_entry,
    maybe_auto_archive_item,
    resolve_knowledge_title,
)
from app.services.language import localized_text, normalize_output_language
from app.services.preference_service import capture_preference_snapshot, resolve_preference_version
from app.services.recommender import (
    RecommendationFeatures,
    compute_final_score,
    compute_focus_goal_match_score,
    compute_freshness_score,
    map_item_quality_score,
    map_source_preference_score,
    map_topic_preference_score,
    score_bucket,
)
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/items", tags=["items"])
settings = get_settings()
interpreter = Interpreter()


def _get_item_or_404(db: Session, item_id: UUID) -> Item:
    item = db.scalar(
        select(Item)
        .where(Item.id == item_id)
        .where(Item.user_id == settings.single_user_id)
        .options(selectinload(Item.tags))
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _is_valid_http_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _process_item_task(item_id: UUID, output_language: str | None = None) -> None:
    process_item_by_id(item_id, output_language=output_language, auto_archive=True)


def _compute_recommendation(
    db: Session,
    item: Item,
    *,
    mode: str = "normal",
    goal_text: str | None = None,
) -> tuple[float, str, list[str], list[str], list[str], float, float]:
    topic_raw_scores: list[float] = []
    topic_matches: list[tuple[str, float]] = []
    for tag in item.tags:
        pref = db.scalar(
            select(TopicPreference.preference_score).where(
                TopicPreference.user_id == item.user_id,
                TopicPreference.tag_name == tag.tag_name,
            )
        )
        if pref is not None:
            raw_score = float(pref)
            topic_raw_scores.append(raw_score)
            topic_matches.append((tag.tag_name, raw_score))

    source_raw = 0.0
    if item.source_domain:
        pref = db.scalar(
            select(SourcePreference.preference_score).where(
                SourcePreference.user_id == item.user_id,
                SourcePreference.source_domain == item.source_domain,
            )
        )
        if pref is not None:
            source_raw = float(pref)

    topic_score = map_topic_preference_score(topic_raw_scores)
    source_score = map_source_preference_score(source_raw)
    quality_score = map_item_quality_score(float(item.score_value) if item.score_value is not None else None)

    created_at = item.created_at
    now = datetime.now(timezone.utc if created_at.tzinfo else None)
    hours_since_created = max(0.0, (now - created_at).total_seconds() / 3600)
    freshness_score = compute_freshness_score(hours_since_created)
    focus_goal_match_score = compute_focus_goal_match_score(
        goal_text=goal_text,
        title=item.title,
        short_summary=item.short_summary,
        long_summary=item.long_summary,
        tags=[tag.tag_name for tag in item.tags],
    )

    action = item.action_suggestion if item.action_suggestion in {"skip", "later", "deep_read"} else None
    features = RecommendationFeatures(
        topic_preference_score=topic_score,
        source_preference_score=source_score,
        item_quality_score=quality_score,
        freshness_score=freshness_score,
        focus_goal_match_score=focus_goal_match_score,
        action_suggestion=action,  # type: ignore[arg-type]
    )
    final_score = compute_final_score(features, focus_mode=mode == "focus")
    bucket = score_bucket(final_score)

    reasons: list[str] = []
    if topic_score >= 60:
        reasons.append("与历史主题偏好匹配")
    if source_score >= 60:
        reasons.append("来源偏好匹配度较高")
    if quality_score >= 70:
        reasons.append("内容质量分较高")
    if freshness_score >= 60:
        reasons.append("内容新鲜度较高")
    if mode == "focus" and focus_goal_match_score >= 60:
        reasons.append("与当前专注目标匹配")
    if not reasons:
        reasons.append("综合分中等，建议按需处理")
    matched_preferences: list[str] = []
    positive_topic_matches = [match for match in topic_matches if match[1] > 0]
    for tag_name, _raw_score in sorted(positive_topic_matches, key=lambda row: row[1], reverse=True)[:2]:
        matched_preferences.append(f"主题 · {tag_name}")
    if item.source_domain and source_raw > 0:
        matched_preferences.append(f"来源 · {item.source_domain}")

    why_recommended: list[str] = []
    if positive_topic_matches:
        top_tag_name, _top_tag_score = sorted(
            positive_topic_matches, key=lambda row: row[1], reverse=True
        )[0]
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": f"你最近更常保留“{top_tag_name}”相关内容",
                    "zh-TW": f"你最近更常保留「{top_tag_name}」相關內容",
                    "en": f'You have been keeping more items about "{top_tag_name}".',
                    "ja": f"最近は「{top_tag_name}」関連の内容を残すことが増えています。",
                    "ko": f'최근에는 "{top_tag_name}" 관련 내용을 더 자주 남기고 있습니다.',
                },
                f"你最近更常保留“{top_tag_name}”相关内容",
            )
        )
    if item.source_domain and source_raw > 0:
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": f"你对来源 {item.source_domain} 的反馈更积极",
                    "zh-TW": f"你對來源 {item.source_domain} 的反饋更積極",
                    "en": f"Your recent feedback toward {item.source_domain} has been positive.",
                    "ja": f"{item.source_domain} への最近の反応は前向きです。",
                    "ko": f"{item.source_domain} 출처에 대한 최근 반응이 긍정적입니다.",
                },
                f"你对来源 {item.source_domain} 的反馈更积极",
            )
        )
    if quality_score >= 70:
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": "这条内容本身质量分较高",
                    "zh-TW": "這條內容本身質量分較高",
                    "en": "This item already scores well on quality.",
                    "ja": "この内容自体の品質スコアが高めです。",
                    "ko": "이 콘텐츠 자체의 품질 점수가 높습니다.",
                },
                "这条内容本身质量分较高",
            )
        )
    if freshness_score >= 60:
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": "这条内容仍然比较新",
                    "zh-TW": "這條內容仍然比較新",
                    "en": "This item is still relatively fresh.",
                    "ja": "この内容はまだ比較的新しいです。",
                    "ko": "이 콘텐츠는 아직 비교적 최신입니다.",
                },
                "这条内容仍然比较新",
            )
        )
    if mode == "focus" and focus_goal_match_score >= 60:
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": "它和当前 Focus 目标直接相关",
                    "zh-TW": "它和當前 Focus 目標直接相關",
                    "en": "It directly matches your current focus goal.",
                    "ja": "現在の Focus 目標と直接一致しています。",
                    "ko": "현재 Focus 목표와 직접적으로 맞닿아 있습니다.",
                },
                "它和当前 Focus 目标直接相关",
            )
        )
    if not why_recommended:
        why_recommended.append(
            localized_text(
                item.output_language,
                {
                    "zh-CN": "当前还在冷启动阶段，先按内容质量和新鲜度推荐",
                    "zh-TW": "目前仍在冷啟動階段，先按內容質量與新鮮度推薦",
                    "en": "Preference learning is still cold-starting, so this is ranked by quality and freshness.",
                    "ja": "まだ学習初期のため、品質と鮮度を優先して推薦しています。",
                    "ko": "아직 학습 초기라서 품질과 최신성을 우선해 추천하고 있습니다.",
                },
                "当前还在冷启动阶段，先按内容质量和新鲜度推荐",
            )
        )

    return final_score, bucket, reasons[:4], why_recommended[:4], matched_preferences[:4], topic_score, source_score


def _resolve_focus_goal_text(db: Session, goal_text: str | None) -> str | None:
    if goal_text and goal_text.strip():
        return goal_text.strip()
    running_goal = db.scalar(
        select(FocusSession.goal_text)
        .where(FocusSession.user_id == settings.single_user_id)
        .where(FocusSession.status == "running")
        .order_by(desc(FocusSession.start_time))
        .limit(1)
    )
    if not running_goal:
        return None
    return running_goal.strip() or None


def _to_item_out(
    db: Session,
    item: Item,
    *,
    mode: str = "normal",
    goal_text: str | None = None,
    preference_version: str | None = None,
) -> ItemOut:
    score, bucket, reasons, why_recommended, matched_preferences, topic_score, source_score = _compute_recommendation(
        db, item, mode=mode, goal_text=goal_text
    )
    resolved_title = normalize_text(item.title or "")
    if not resolved_title or resolved_title.lower().startswith(("wechat auto", "wechat ocr")):
        summary = normalize_text(item.short_summary or item.long_summary or "")
        for sentence in summary.replace("。", ".").replace("！", ".").replace("？", ".").split("."):
            candidate = normalize_text(sentence).strip("，,：:；; ")
            if len(candidate) >= 8:
                resolved_title = candidate[:36]
                break
    if not resolved_title:
        resolved_title = localized_text(
            item.output_language,
            {
                "zh-CN": "主题待确认",
                "zh-TW": "主題待確認",
                "en": "Topic pending",
                "ja": "テーマ確認待ち",
                "ko": "주제 확인 대기",
            },
            "主题待确认",
        )
    return ItemOut.model_validate(item).model_copy(
        update={
            "title": resolved_title,
            "recommendation_score": round(score, 2),
            "recommendation_bucket": bucket,
            "recommendation_reason": reasons,
            "topic_match_score": round(topic_score, 2),
            "source_match_score": round(source_score, 2),
            "preference_version": preference_version or resolve_preference_version(db, item.user_id),
            "matched_preferences": matched_preferences,
            "why_recommended": why_recommended,
        }
    )


def _build_item_interpretation(item: Item, output_language: str) -> ItemInterpretResponse:
    result = interpreter.interpret(
        title=item.title or localized_text(
            output_language,
            {
                "zh-CN": "未命名内容",
                "zh-TW": "未命名內容",
                "en": "Untitled item",
                "ja": "無題コンテンツ",
                "ko": "제목 없음",
            },
            "未命名内容",
        ),
        source_domain=item.source_domain or "",
        short_summary=item.short_summary or "",
        long_summary=item.long_summary or "",
        clean_content=item.clean_content or item.raw_content or "",
        output_language=output_language,
    )
    return ItemInterpretResponse(
        item_id=item.id,
        output_language=output_language,
        insight_title=result.insight_title,
        expert_take=result.expert_take,
        key_signals=result.key_signals[:3],
        knowledge_note=result.knowledge_note,
    )


def _list_items_impl(
    db: Session,
    *,
    limit: int,
    saved_only: bool = False,
    mode: str = "normal",
    goal_text: str | None = None,
    include_pending: bool = True,
) -> ItemListResponse:
    query = (
        select(Item)
        .where(Item.user_id == settings.single_user_id)
        .options(selectinload(Item.tags))
        .order_by(desc(Item.created_at))
        .limit(max(1, min(limit, 100)))
    )

    if not include_pending:
        query = query.where(Item.status == "ready")

    if saved_only:
        query = (
            select(Item)
            .where(Item.user_id == settings.single_user_id)
            .where(Item.status == "ready")
            .where(
                Item.id.in_(
                    select(Feedback.item_id).where(
                        Feedback.user_id == settings.single_user_id,
                        Feedback.feedback_type == "save",
                    )
                )
            )
            .options(selectinload(Item.tags))
            .order_by(desc(Item.created_at))
            .limit(max(1, min(limit, 100)))
        )

    items = list(db.scalars(query))
    preference_version = resolve_preference_version(db, settings.single_user_id)
    ranked_items = sorted(
        [
            _to_item_out(
                db,
                item,
                mode=mode,
                goal_text=goal_text,
                preference_version=preference_version,
            )
            for item in items
        ],
        key=lambda x: x.recommendation_score or 0,
        reverse=True,
    )
    return ItemListResponse(items=ranked_items)


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ItemOut:
    ensure_demo_user(db)

    source_domain = extract_domain(payload.source_url)
    raw_content = payload.raw_content

    item = Item(
        user_id=settings.single_user_id,
        source_type=payload.source_type,
        source_url=payload.source_url,
        source_domain=source_domain,
        title=payload.title,
        raw_content=raw_content,
        output_language=payload.output_language,
        status="pending",
    )
    db.add(item)
    db.flush()

    should_process_inline = payload.source_type == "text" or bool(
        payload.raw_content and payload.source_type == "plugin"
    )
    if should_process_inline:
        process_item_in_session(db, item, output_language=payload.output_language, auto_archive=True)
        db.commit()
        db.refresh(item)
    else:
        db.commit()
        db.refresh(item)
        background_tasks.add_task(_process_item_task, item.id, payload.output_language)
    return _to_item_out(db, item)


@router.post("/batch", response_model=ItemBatchCreateResponse, status_code=status.HTTP_201_CREATED)
def create_items_batch(
    payload: ItemBatchCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ItemBatchCreateResponse:
    ensure_demo_user(db)

    normalized_urls = [url.strip() for url in payload.urls if url.strip()]
    existing_urls: set[str] = set()
    if payload.deduplicate and normalized_urls:
        existing_urls = {
            value
            for value in db.scalars(
                select(Item.source_url).where(
                    Item.user_id == settings.single_user_id,
                    Item.source_url.in_(normalized_urls),
                )
            )
            if value
        }

    results: list[ItemBatchCreateResult] = []
    created_item_ids: list[UUID] = []
    created_urls_in_batch: set[str] = set()

    for source_url in normalized_urls:
        if not _is_valid_http_url(source_url):
            results.append(
                ItemBatchCreateResult(
                    source_url=source_url,
                    status="invalid",
                    detail="URL must start with http:// or https://",
                )
            )
            continue

        if payload.deduplicate and (source_url in existing_urls or source_url in created_urls_in_batch):
            results.append(
                ItemBatchCreateResult(
                    source_url=source_url,
                    status="skipped",
                    detail="already exists",
                )
            )
            continue

        source_domain = extract_domain(source_url)
        item = Item(
            user_id=settings.single_user_id,
            source_type=payload.source_type,
            source_url=source_url,
            source_domain=source_domain,
            raw_content=None,
            output_language=payload.output_language,
            status="pending",
        )
        db.add(item)
        db.flush()

        created_urls_in_batch.add(source_url)
        created_item_ids.append(item.id)
        results.append(
            ItemBatchCreateResult(
                source_url=source_url,
                status="created",
                item_id=item.id,
            )
        )

    db.commit()

    for item_id in created_item_ids:
        background_tasks.add_task(_process_item_task, item_id, payload.output_language)

    created_count = sum(1 for row in results if row.status == "created")
    skipped_count = sum(1 for row in results if row.status == "skipped")
    invalid_count = sum(1 for row in results if row.status == "invalid")
    return ItemBatchCreateResponse(
        total=len(results),
        created=created_count,
        skipped=skipped_count,
        invalid=invalid_count,
        results=results,
    )


@router.get("", response_model=ItemListResponse)
def list_items(
    limit: int = 30,
    mode: str = "normal",
    goal_text: str | None = None,
    include_pending: bool = True,
    db: Session = Depends(get_db),
) -> ItemListResponse:
    ensure_demo_user(db)
    safe_mode = mode if mode in {"normal", "focus"} else "normal"
    resolved_goal_text = _resolve_focus_goal_text(db, goal_text) if safe_mode == "focus" else None
    return _list_items_impl(
        db,
        limit=limit,
        saved_only=False,
        mode=safe_mode,
        goal_text=resolved_goal_text,
        include_pending=include_pending,
    )


@router.get("/saved", response_model=ItemListResponse)
def list_saved_items(limit: int = 30, db: Session = Depends(get_db)) -> ItemListResponse:
    ensure_demo_user(db)
    return _list_items_impl(db, limit=limit, saved_only=True)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: UUID, db: Session = Depends(get_db)) -> ItemOut:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    return _to_item_out(db, item, preference_version=resolve_preference_version(db, settings.single_user_id))


@router.get("/{item_id}/diagnostics", response_model=ItemDiagnosticsOut)
def get_item_diagnostics(item_id: UUID, db: Session = Depends(get_db)) -> ItemDiagnosticsOut:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    attempts = list_item_attempts(db, item.id)
    return ItemDiagnosticsOut(**serialize_item_diagnostics(item, attempts))


@router.post("/{item_id}/reprocess", response_model=ItemReprocessResponse)
def reprocess_item(
    item_id: UUID,
    background_tasks: BackgroundTasks,
    payload: ItemReprocessRequest | None = None,
    db: Session = Depends(get_db),
) -> ItemReprocessResponse:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    resolved_language = normalize_output_language(payload.output_language if payload else item.output_language)
    item.status = "processing"
    item.processing_error = None
    item.output_language = resolved_language
    db.add(item)
    db.commit()

    background_tasks.add_task(_process_item_task, item_id, resolved_language)
    return ItemReprocessResponse(item_id=item_id, status="processing", output_language=resolved_language)


@router.post("/{item_id}/feedback", response_model=ItemFeedbackResponse)
def create_feedback(
    item_id: UUID,
    payload: ItemFeedbackRequest,
    db: Session = Depends(get_db),
) -> ItemFeedbackResponse:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    apply_feedback(
        db,
        user_id=settings.single_user_id,
        item=item,
        feedback_type=payload.feedback_type,
    )
    db.flush()
    archive_result = None
    if payload.feedback_type in {"like", "save"}:
        archive_result = maybe_auto_archive_item(
            db,
            item=item,
            trigger_feedback_type=payload.feedback_type,
            output_language=item.output_language,
        )

    capture_preference_snapshot(db, settings.single_user_id)
    db.commit()
    return ItemFeedbackResponse(
        item_id=item_id,
        feedback_type=payload.feedback_type,
        status="ok",
        knowledge_entry_id=archive_result.entry.id if archive_result and archive_result.entry else None,
        knowledge_status=(
            archive_result.status
            if archive_result and archive_result.status != "skipped"
            else None
        ),
        knowledge_trigger=payload.feedback_type if archive_result and archive_result.entry else None,
        knowledge_threshold=archive_result.threshold if archive_result and archive_result.entry else None,
        knowledge_score_value=(
            float(item.score_value) if archive_result and archive_result.entry and item.score_value is not None else None
        ),
    )


@router.post("/{item_id}/interpret", response_model=ItemInterpretResponse)
def interpret_item(
    item_id: UUID,
    payload: ItemInterpretRequest | None = None,
    db: Session = Depends(get_db),
) -> ItemInterpretResponse:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    resolved_language = normalize_output_language(payload.output_language if payload else item.output_language)
    return _build_item_interpretation(item, resolved_language)


@router.post("/{item_id}/knowledge", response_model=ItemKnowledgeSaveResponse, status_code=status.HTTP_201_CREATED)
def save_item_to_knowledge(
    item_id: UUID,
    payload: ItemKnowledgeSaveRequest | None = None,
    db: Session = Depends(get_db),
) -> ItemKnowledgeSaveResponse:
    ensure_demo_user(db)
    item = _get_item_or_404(db, item_id)
    resolved_language = normalize_output_language(payload.output_language if payload else item.output_language)

    title = (payload.title if payload else None) or None
    content = (payload.content if payload else None) or None
    if not content:
        if item.short_summary or item.long_summary:
            title = title or resolve_knowledge_title(item=item, title=item.title, output_language=resolved_language)
            content_parts = [item.short_summary or "", item.long_summary or ""]
            content = "\n\n".join(part.strip() for part in content_parts if part and part.strip())
        if not content:
            interpretation = _build_item_interpretation(item, resolved_language)
            title = title or interpretation.insight_title
            content = interpretation.knowledge_note
    entry, _created = create_or_get_knowledge_entry(
        db,
        user_id=settings.single_user_id,
        item=item,
        title=resolve_knowledge_title(item=item, title=title, output_language=resolved_language),
        content=content,
        output_language=resolved_language,
    )
    db.commit()
    db.refresh(entry)
    return ItemKnowledgeSaveResponse(
        entry_id=entry.id,
        item_id=item.id,
        title=entry.title,
        content=entry.content,
        source_domain=entry.source_domain,
        created_at=entry.created_at,
    )
