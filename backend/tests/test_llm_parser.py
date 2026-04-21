from app.services.llm_parser import (
    parse_insight_response,
    parse_score_response,
    parse_session_summary_response,
    parse_summarize_response,
    parse_tags_response,
)


def test_parse_json_from_wrapped_text() -> None:
    raw = """模型输出如下：
{
  "tags": ["AI Agent", "浏览器"]
}
谢谢。"""
    result = parse_tags_response(raw)
    assert result.tags == ["AI Agent", "浏览器"]


def test_parse_invalid_json_fallback() -> None:
    result = parse_score_response("not a json")
    assert result.score_value == 2.5
    assert result.action_suggestion == "later"
    assert result.recommendation_reason


def test_parse_session_summary_fallback() -> None:
    result = parse_session_summary_response("[]")
    assert "专注" in result.summary_text


def test_parse_summarize_reads_display_title() -> None:
    raw = """```json
{
  "display_title": "AI 制药上市潮升温",
  "short_summary": "短摘要",
  "long_summary": "长摘要",
  "key_points": ["a", "b", "c"]
}
```"""
    result = parse_summarize_response(raw)
    assert result.display_title == "AI 制药上市潮升温"
    assert result.short_summary == "短摘要"


def test_parse_insight_fallback() -> None:
    result = parse_insight_response("not-json")
    assert result.insight_title
    assert result.expert_take
