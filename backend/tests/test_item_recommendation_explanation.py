from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.items import _to_item_out
from app.core.config import get_settings
from app.db.base import Base
from app.models import Item, ItemTag, User
from app.services.feedback_service import apply_feedback
from app.services.preference_service import capture_preference_snapshot


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_item_out_contains_visible_preference_explanations() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        seed_item = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://openai.com/blog/seed",
            source_domain="openai.com",
            title="Seed item",
            short_summary="AI agent seed",
            long_summary="AI agent seed long summary",
            score_value=4.8,
            action_suggestion="deep_read",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        seed_item.tags = [ItemTag(tag_name="AI"), ItemTag(tag_name="Agent")]
        db.add(seed_item)
        db.flush()
        apply_feedback(db, user_id=settings.single_user_id, item=seed_item, feedback_type="save")
        snapshot, _summary = capture_preference_snapshot(db, settings.single_user_id)
        db.commit()

        candidate = Item(
            user_id=settings.single_user_id,
            source_type="url",
            source_url="https://openai.com/blog/candidate",
            source_domain="openai.com",
            title="Candidate item",
            short_summary="Latest agent workflow",
            long_summary="Latest agent workflow with new reasoning steps",
            score_value=4.5,
            action_suggestion="later",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        candidate.tags = [ItemTag(tag_name="AI"), ItemTag(tag_name="Workflow")]
        db.add(candidate)
        db.commit()

        out = _to_item_out(db, candidate, preference_version=str(snapshot.id))

        assert (out.topic_match_score or 0) > 50
        assert (out.source_match_score or 0) > 50
        assert any("主题" in entry for entry in out.matched_preferences)
        assert any("来源" in entry for entry in out.matched_preferences)
        assert len(out.why_recommended) >= 2
        assert out.preference_version == str(snapshot.id)
    finally:
        db.close()


def test_item_out_rewrites_existing_wechat_local_home_header_title() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        item = Item(
            user_id=settings.single_user_id,
            source_type="plugin",
            source_url="https://wechat.local/article/942c1099361456c91a4fec6f25de8395e3d8e753",
            source_domain="wechat.local",
            title="长安君 中央政法委长安剑 2026年5月9日 06:00",
            clean_content=(
                "长安君 中央政法委长安剑 2026年5月9日 06:00 北京649人 点击蓝字 可以关注我们喔！"
                "每天3分钟，速览天下事 5月9日星期六，农历三月廿三，封面新闻关注政法动态。"
            ),
            short_summary=(
                "长安君 中央政法委长安剑 2026年5月9日 06:00 北京649人 点击蓝字 可以关注我们喔！"
                "每天3分钟，速览天下事 5月9日星期六，封面新闻关注政法动态。"
            ),
            long_summary="每天3分钟，速览天下事，梳理政法、社会治理和公共事件动态。",
            score_value=3.2,
            action_suggestion="later",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        db.add(item)
        db.commit()

        out = _to_item_out(db, item)

        assert out.title
        assert "长安君 中央政法委长安剑" not in out.title
        assert "06:00" not in out.title
        assert "每天3分钟" in out.title
    finally:
        db.close()


def test_item_out_rewrites_existing_wechat_local_browser_nav_title() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

        nav_noise = "个人收藏 方案制作工具 京 京东 天 天猫 淘 淘宝 苏 苏宁易购 W 维基百科"
        item = Item(
            user_id=settings.single_user_id,
            source_type="plugin",
            source_url="https://wechat.local/article/6ff3ce7f5946837fc042af4fdad80f5009962d7c",
            source_domain="wechat.local",
            title=nav_noise,
            clean_content=(
                f"{nav_noise} 精彩演讲视频集锦 iCloud 百度 新浪微博 "
                "本地服务，所有数据存在 /tmp/pixcull_demo/<run_id>/。"
                "第一次跑某种照片时模型加载需10秒，后续每张约2-10秒。"
                "已积累 43 MB，3次记录，本地缓存可查看或清理。"
            ),
            short_summary=(
                f"{nav_noise} 精彩演讲视频集锦 iCloud 百度 新浪微博 "
                "本地服务，所有数据存在 /tmp/pixcull_demo/<run_id>/。"
            ),
            long_summary="本地照片分拣工具记录模型加载、本地缓存和运行状态。",
            score_value=3.2,
            action_suggestion="later",
            status="ready",
            created_at=datetime.now(timezone.utc),
        )
        db.add(item)
        db.commit()

        out = _to_item_out(db, item)

        assert out.title == "本地照片分拣工具运行状态"
    finally:
        db.close()
