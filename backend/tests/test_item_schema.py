import pytest
from pydantic import ValidationError

from app.api.items import _parse_item_ids
from app.schemas.items import ItemBatchCreateRequest, ItemBatchReprocessRequest, ItemCreateRequest


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


def test_parse_item_ids_deduplicates_and_ignores_invalid_values() -> None:
    value = "9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa,invalid,9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa"
    item_ids = _parse_item_ids(value)

    assert [str(item_id) for item_id in item_ids] == [
        "9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa"
    ]


def test_item_batch_reprocess_request_deduplicates_ids() -> None:
    payload = ItemBatchReprocessRequest(
        item_ids=[
            "9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa",
            "9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa",
        ]
    )

    assert [str(item_id) for item_id in payload.item_ids] == [
        "9fdcb277-96dd-4b0c-b1a8-e09aba6a13aa"
    ]
