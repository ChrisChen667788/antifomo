from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app.services.vision_ocr_service import VisionOCRService, decode_image_base64


def test_decode_image_base64_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        decode_image_base64("not-base64")


def test_vision_ocr_service_mock_extract_returns_text() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(buffer, format="PNG")
    tiny_png_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
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


def test_vision_ocr_service_invalid_image_skips_openai(monkeypatch) -> None:
    service = VisionOCRService()
    service.settings.llm_provider = "openai"
    service.settings.openai_api_key = "demo-key"

    monkeypatch.setattr(
        service,
        "_extract_with_openai",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("openai vision should be skipped")),
    )

    invalid_png_base64 = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR").decode("utf-8")
    result = service.extract(
        image_base64=invalid_png_base64,
        mime_type="image/png",
        source_url="https://mp.weixin.qq.com/s/demo",
        title_hint="Demo OCR Title",
        output_language="zh-CN",
    )

    assert result.provider == "mock_ocr"
    assert "OCR" in result.title


def test_vision_ocr_service_uses_dedicated_openai_timeout() -> None:
    service = VisionOCRService()
    service.settings.openai_timeout_seconds = 120
    service.settings.ocr_openai_timeout_seconds = 6

    assert service._resolve_openai_timeout_seconds() == 6
