from __future__ import annotations

import math
from dataclasses import dataclass
import re
from typing import Literal


ActionSuggestion = Literal["skip", "later", "deep_read"]
ScoreBucket = Literal["skip", "later", "deep_read"]


ACTION_BONUS: dict[ActionSuggestion, float] = {
    "deep_read": 8.0,
    "later": 3.0,
    "skip": -8.0,
}

TOPIC_FEEDBACK_WEIGHTS: dict[str, float] = {
    "like": 3.0,
    "save": 4.0,
    "open_detail": 2.0,
    "ignore": -3.0,
    "inaccurate": -2.0,
}

SOURCE_FEEDBACK_WEIGHTS: dict[str, float] = {
    "like": 2.0,
    "save": 3.0,
    "open_detail": 1.0,
    "ignore": -2.0,
    "inaccurate": -1.0,
}


@dataclass(slots=True)
class RecommendationFeatures:
    topic_preference_score: float
    source_preference_score: float
    item_quality_score: float
    freshness_score: float
    focus_goal_match_score: float = 0.0
    action_suggestion: ActionSuggestion | None = None


def clamp_score(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def map_item_quality_score(score_value: float | None) -> float:
    """Map score_value from [1, 5] to [0, 100]."""
    if score_value is None:
        return 50.0
    normalized = ((score_value - 1.0) / 4.0) * 100
    return clamp_score(normalized)


def map_source_preference_score(raw_preference: float) -> float:
    """Map raw source preference to [0, 100] by rule: clamp(50 + raw * 5)."""
    return clamp_score(50 + raw_preference * 5)


def map_topic_preference_score(raw_tag_scores: list[float]) -> float:
    """Average raw topic scores and map to [0, 100] by the same linear transform."""
    if not raw_tag_scores:
        return 50.0
    avg_raw = sum(raw_tag_scores) / len(raw_tag_scores)
    return clamp_score(50 + avg_raw * 5)


def compute_freshness_score(hours_since_created: float, *, mode: Literal["exp", "linear"] = "exp") -> float:
    if hours_since_created < 0:
        hours_since_created = 0

    if mode == "linear":
        # 100 - hours * 2, compatible with first-pass business rule.
        return clamp_score(100 - hours_since_created * 2)

    # Default: smooth exponential decay.
    return clamp_score(100 * math.exp(-hours_since_created / 24))


def compute_final_score(features: RecommendationFeatures, *, focus_mode: bool = False) -> float:
    if focus_mode:
        score = (
            0.30 * features.topic_preference_score
            + 0.15 * features.source_preference_score
            + 0.20 * features.item_quality_score
            + 0.15 * features.freshness_score
            + 0.20 * features.focus_goal_match_score
        )
    else:
        score = (
            0.35 * features.topic_preference_score
            + 0.20 * features.source_preference_score
            + 0.25 * features.item_quality_score
            + 0.20 * features.freshness_score
        )

    if features.action_suggestion:
        score += ACTION_BONUS[features.action_suggestion]

    return clamp_score(score)


def score_bucket(score: float) -> ScoreBucket:
    if score >= 75:
        return "deep_read"
    if score >= 45:
        return "later"
    return "skip"


def cold_start_score(item_quality_score: float, freshness_score: float, general_topic_priority: float) -> float:
    score = (
        0.50 * item_quality_score
        + 0.30 * freshness_score
        + 0.20 * clamp_score(general_topic_priority)
    )
    return clamp_score(score)


_GOAL_STOPWORDS = {
    "",
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "整理",
    "完成",
    "本次",
    "任务",
    "工作",
    "内容",
}


def _extract_goal_tokens(goal_text: str) -> list[str]:
    # English words + contiguous CJK text chunks, then keep meaningful pieces.
    raw_tokens = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", goal_text.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        token = token.strip()
        if not token or token in _GOAL_STOPWORDS:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) >= 4:
            # For long CJK phrases, split by two-char chunks to improve partial matching.
            for index in range(0, len(token), 2):
                chunk = token[index : index + 2]
                if len(chunk) >= 2 and chunk not in _GOAL_STOPWORDS:
                    tokens.append(chunk)
            continue

        if len(token) >= 2:
            tokens.append(token)
    # Deduplicate while preserving order.
    deduped = list(dict.fromkeys(tokens))
    return deduped[:12]


def _char_ngram_set(text: str, n: int = 2) -> set[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    if not normalized:
        return set()
    if len(normalized) < n:
        return {normalized}
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def compute_focus_goal_match_score(
    *,
    goal_text: str | None,
    title: str | None,
    short_summary: str | None,
    long_summary: str | None,
    tags: list[str] | None = None,
) -> float:
    if not goal_text:
        return 0.0

    tokens = _extract_goal_tokens(goal_text)
    if not tokens:
        return 0.0

    haystack_parts = [
        title or "",
        short_summary or "",
        long_summary or "",
        " ".join(tags or []),
    ]
    haystack = " ".join(haystack_parts).lower()
    if not haystack.strip():
        return 0.0

    matched = sum(1 for token in tokens if token in haystack)
    token_ratio = matched / len(tokens)
    token_score = token_ratio * 100

    ngrams_goal = _char_ngram_set(goal_text, n=2)
    ngrams_text = _char_ngram_set(haystack, n=2)
    ngram_overlap = 0.0
    if ngrams_goal and ngrams_text:
        ngram_overlap = len(ngrams_goal & ngrams_text) / len(ngrams_goal)
    ngram_score = ngram_overlap * 100

    # Token signal is primary, n-gram overlap smooths CJK phrase matching.
    score = 0.75 * token_score + 0.25 * ngram_score

    # Phrase-level boost when most of goal phrase appears verbatim.
    normalized_goal = re.sub(r"\s+", "", goal_text.lower())
    normalized_haystack = re.sub(r"\s+", "", haystack)
    if len(normalized_goal) >= 6 and normalized_goal in normalized_haystack:
        score = max(score, 85.0)

    return clamp_score(score)
