from __future__ import annotations

from app.api import collector as collector_api
from app.schemas.collector import CollectorOCRPreviewResponse


def test_evaluate_ocr_quality_rejects_wechat_history_feed_preview() -> None:
    ok, reason = collector_api._evaluate_ocr_quality(
        (
            "00:39 01:53 昨天 23:35 00:08 00:03 昨天 22:41 凶 昨天 21:05 凶 昨天 20:57 凶 "
            "昨天 19:33 3点必看！ 昨天 19:12 昨天 18:29 3人小班课... 1小时前 白鲸出海 "
            "2个朋友看过 10小时前 GLM-5.1 面向长程任务的"
        ),
        0.604,
    )

    assert ok is False
    assert reason == "timeline_feed"


def test_evaluate_ocr_quality_rejects_dense_timestamp_preview() -> None:
    ok, reason = collector_api._evaluate_ocr_quality(
        (
            "01:13 01:53 昨天 23:35 00:08 00:03 昨天 22:41 昨天 21:05 昨天 20:57 "
            "昨天 19:33 3点必看 昨天 19:12 昨天 18:29 3人小班课 昨天 15:21"
        ),
        0.56,
    )

    assert ok is False
    assert reason == "timeline_feed"


def test_evaluate_ocr_quality_rejects_public_account_hub_text() -> None:
    ok, reason = collector_api._evaluate_ocr_quality(
        (
            "查看历史消息 全部消息 进入公众号 最近更新 相关文章 公众号主页 推荐阅读 "
            "更多文章 查看历史消息 全部消息 推荐阅读"
        ),
        0.88,
    )

    assert ok is False
    assert reason == "non_article_hub"


def test_evaluate_ocr_quality_rejects_chat_list_preview() -> None:
    ok, reason = collector_api._evaluate_ocr_quality(
        (
            "Q 搜索 十 陈皓锐 陈皓锐 ［图片 02:03 • My Wife 后面照着这个抄作业 01:13 "
            "Al影视创作者群 ［8条］ 大公家电 这里 01:53 一米七八的女猎头Selina ［草稿］ "
            "昨天 23:35 公众号 第一财经 00:08 相亲相爱一家人"
        ),
        0.61,
    )

    assert ok is False
    assert reason == "chat_ui"


def test_evaluate_ocr_quality_accepts_real_article_like_text() -> None:
    ok, reason = collector_api._evaluate_ocr_quality(
        (
            "作者：研究团队 发布于 2026年4月8日。本文围绕模型推理优化展开，先说明推理成本变化，"
            "再拆解长程任务中的调度策略与部署建议。文章给出多个段落的完整结论，并附带实施建议。"
        ),
        0.73,
    )

    assert ok is True
    assert reason is None


def test_run_ocr_preview_with_variants_retries_right_focus(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run_ocr_preview(*, image_base64: str, **_kwargs) -> CollectorOCRPreviewResponse:
        calls.append(image_base64)
        if image_base64 == "base-image":
            return CollectorOCRPreviewResponse(
                provider="ocrmac_vision",
                confidence=0.61,
                text_length=220,
                title="01:13",
                body_preview="01:13 01:53 昨天 23:35 00:08",
                body_text="01:13 01:53 昨天 23:35 00:08 00:03 昨天 22:41",
                keywords=[],
                quality_ok=False,
                quality_reason="timeline_feed",
            )
        return CollectorOCRPreviewResponse(
            provider="ocrmac_vision",
            confidence=0.58,
            text_length=96,
            title="项目调研纪要",
            body_preview="该项目已进入方案评估阶段",
            body_text="该项目已进入方案评估阶段。正文信息完整，包含多句内容。",
            keywords=["模型"],
            quality_ok=True,
            quality_reason=None,
        )

    monkeypatch.setattr(collector_api, "_run_ocr_preview", fake_run_ocr_preview)
    monkeypatch.setattr(
        collector_api,
        "_crop_preview_image_base64",
        lambda image_base64, *, variant_name: f"{image_base64}:{variant_name}",
    )

    preview = collector_api._run_ocr_preview_with_variants(
        image_base64="base-image",
        mime_type="image/png",
        source_url=None,
        title_hint=None,
        output_language="zh-CN",
    )

    assert preview.quality_ok is True
    assert calls == ["base-image", "base-image:article_right_focus"]
