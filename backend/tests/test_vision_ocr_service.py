from __future__ import annotations

import base64

import pytest

from app.services.vision_ocr_service import VisionOCRService, decode_image_base64


def test_decode_image_base64_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        decode_image_base64("not-base64")


def test_vision_ocr_service_mock_extract_returns_text() -> None:
    tiny_png_base64 = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    ).decode("utf-8")
    service = VisionOCRService()
    result = service.extract(
        image_base64=tiny_png_base64,
        mime_type="image/png",
        source_url="https://mp.weixin.qq.com/s/demo",
        title_hint="Demo OCR Title",
        output_language="en",
    )
    assert result.provider in {"mock_ocr", "openai_vision"}
    assert result.title
    assert len(result.body_text) >= 20
