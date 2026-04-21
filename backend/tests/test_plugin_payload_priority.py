from __future__ import annotations

import uuid

from app.models.entities import Item
from app.services import item_processor


def test_plugin_payload_prefers_raw_content_without_remote_fetch(monkeypatch) -> None:
    called = {"url": False, "proxy": False}

    def fake_extract_from_url(*args, **kwargs):  # pragma: no cover
        called["url"] = True
        raise AssertionError("extract_from_url should not be called for rich plugin payload")

    def fake_extract_from_reader_proxy(*args, **kwargs):  # pragma: no cover
        called["proxy"] = True
        raise AssertionError("extract_from_reader_proxy should not be called for rich plugin payload")

    monkeypatch.setattr(item_processor, "extract_from_url", fake_extract_from_url)
    monkeypatch.setattr(item_processor, "extract_from_reader_proxy", fake_extract_from_reader_proxy)

    body = "这是一段用于测试的正文内容。" * 20
    item = Item(
        user_id=uuid.uuid4(),
        source_type="plugin",
        source_url="https://mp.weixin.qq.com/s/demo",
        title="测试公众号文章",
        raw_content=body,
        status="pending",
    )

    source_domain, title, clean_content = item_processor._prepare_item_content(item)
    assert source_domain == "mp.weixin.qq.com"
    assert title == "测试公众号文章"
    assert clean_content == body
    assert called["url"] is False
    assert called["proxy"] is False


def test_plugin_structured_payload_extracts_body_and_keywords() -> None:
    item = Item(
        user_id=uuid.uuid4(),
        source_type="plugin",
        source_url="https://mp.weixin.qq.com/s/demo-structured",
        title=None,
        raw_content=(
            "标题：企业 Agent 落地观察\n"
            "作者：Demo\n"
            "关键词：AI Agent, 工作流自动化, 组织效率\n"
            f"正文：{'这是正文内容。' * 80}"
        ),
        status="pending",
    )

    source_domain, title, clean_content = item_processor._prepare_item_content(item)
    assert source_domain == "mp.weixin.qq.com"
    assert title == "企业 Agent 落地观察"
    assert "标题：" not in clean_content
    assert clean_content.startswith("这是正文内容。")
    assert "关键词：AI Agent, 工作流自动化, 组织效率" in clean_content
