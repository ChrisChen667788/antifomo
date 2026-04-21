import pytest
from pydantic import ValidationError

from app.schemas.items import ItemBatchCreateRequest, ItemCreateRequest


def test_plugin_item_create_request_accepts_source_url() -> None:
    payload = ItemCreateRequest(
        source_type="plugin",
        source_url="https://example.com/article",
        title="demo",
    )
    assert payload.source_type == "plugin"


def test_plugin_item_create_request_requires_url_or_content() -> None:
    with pytest.raises(ValidationError):
        ItemCreateRequest(source_type="plugin", title="only title")


def test_item_batch_create_request_normalizes_urls() -> None:
    payload = ItemBatchCreateRequest(
        urls=[
            " https://mp.weixin.qq.com/s?__biz=demo1 ",
            "",
            "https://mp.weixin.qq.com/s?__biz=demo2",
        ]
    )
    assert payload.source_type == "url"
    assert payload.urls == [
        "https://mp.weixin.qq.com/s?__biz=demo1",
        "https://mp.weixin.qq.com/s?__biz=demo2",
    ]


def test_item_batch_create_request_rejects_empty_urls() -> None:
    with pytest.raises(ValidationError):
        ItemBatchCreateRequest(urls=[" ", "\n", ""])
