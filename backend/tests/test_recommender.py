from app.services.recommender import (
    RecommendationFeatures,
    compute_final_score,
    compute_focus_goal_match_score,
    score_bucket,
)


def test_compute_final_score_normal_mode() -> None:
    features = RecommendationFeatures(
        topic_preference_score=80,
        source_preference_score=60,
        item_quality_score=70,
        freshness_score=50,
        action_suggestion="later",
    )
    score = compute_final_score(features, focus_mode=False)
    assert score == 70.5
    assert score_bucket(score) == "later"


def test_compute_final_score_focus_mode() -> None:
    features = RecommendationFeatures(
        topic_preference_score=65,
        source_preference_score=50,
        item_quality_score=72,
        freshness_score=40,
        focus_goal_match_score=90,
        action_suggestion="deep_read",
    )
    score = compute_final_score(features, focus_mode=True)
    assert score == 73.4


def test_compute_focus_goal_match_score() -> None:
    score_high = compute_focus_goal_match_score(
        goal_text="整理AI行业求职材料",
        title="AI 行业招聘变化速览",
        short_summary="聚焦 AI 行业岗位和求职策略",
        long_summary="",
        tags=["AI", "求职"],
    )
    score_low = compute_focus_goal_match_score(
        goal_text="整理AI行业求职材料",
        title="旅行拍照技巧",
        short_summary="手机摄影入门",
        long_summary="",
        tags=["旅行"],
    )
    assert score_high >= 60
    assert score_low <= 20
