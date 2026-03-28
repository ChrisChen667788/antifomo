from __future__ import annotations

import base64
import io
import json
import logging
import ssl
from dataclasses import dataclass
from urllib import error, request

from PIL import Image

from app.core.config import get_settings
from app.services.language import localized_text, normalize_output_language
from app.services.llm_service import extract_openai_message_content

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency path
    from ocrmac import ocrmac as ocrmac_impl
except Exception:  # pragma: no cover
    ocrmac_impl = None


@dataclass(slots=True)
class OCRExtractResult:
    provider: str
    confidence: float
    title: str
    body_text: str
    keywords: list[str]


def decode_image_base64(image_base64: str, *, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    value = image_base64.strip()
    if value.startswith("data:") and "," in value:
        _, _, value = value.partition(",")
    try:
        binary = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("invalid image_base64") from exc
    if len(binary) == 0:
        raise ValueError("empty image payload")
    if len(binary) > max_bytes:
        raise ValueError("image payload too large")
    return binary


class VisionOCRService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def extract(
        self,
        *,
        image_base64: str,
        mime_type: str,
        source_url: str | None,
        title_hint: str | None,
        output_language: str,
    ) -> OCRExtractResult:
        resolved_language = normalize_output_language(output_language)
        _ = decode_image_base64(image_base64)

        provider = str(self.settings.ocr_provider or "auto").strip().lower()

        if provider in {"auto", "local"}:
            try:
                return self._extract_with_ocrmac(
                    image_base64=image_base64,
                    source_url=source_url,
                    title_hint=title_hint,
                    output_language=resolved_language,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("local ocr failed, fallback to next provider: %s", exc)
                if provider == "local":
                    return self._extract_with_mock(
                        source_url=source_url,
                        title_hint=title_hint,
                        output_language=resolved_language,
                    )

        if provider in {"auto", "openai"} and self.settings.llm_provider == "openai" and self.settings.openai_api_key:
            try:
                return self._extract_with_openai(
                    image_base64=image_base64,
                    mime_type=mime_type,
                    source_url=source_url,
                    title_hint=title_hint,
                    output_language=resolved_language,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("openai vision ocr failed, fallback to mock: %s", exc)
                if provider == "openai":
                    return self._extract_with_mock(
                        source_url=source_url,
                        title_hint=title_hint,
                        output_language=resolved_language,
                    )

        return self._extract_with_mock(
            source_url=source_url,
            title_hint=title_hint,
            output_language=resolved_language,
        )

    def _extract_with_ocrmac(
        self,
        *,
        image_base64: str,
        source_url: str | None,
        title_hint: str | None,
        output_language: str,
    ) -> OCRExtractResult:
        if ocrmac_impl is None:
            raise RuntimeError("ocrmac is not installed")

        image_bytes = decode_image_base64(image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        language_pref = self._ocr_language_preferences(output_language)

        ocr = ocrmac_impl.OCR(
            image=image,
            framework="vision",
            recognition_level="accurate",
            language_preference=language_pref,
            confidence_threshold=0.0,
            detail=True,
        )
        recognized = ocr.recognize()
        if not recognized:
            raise RuntimeError("local OCR returned empty result")

        filtered: list[tuple[str, float]] = []
        for row in recognized:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            text = str(row[0]).strip()
            if not text:
                continue
            try:
                confidence = float(row[1])
            except Exception:
                confidence = 0.6
            filtered.append((text, max(0.0, min(1.0, confidence))))

        if not filtered:
            raise RuntimeError("local OCR did not produce usable text")

        body_lines = [text for text, _ in filtered]
        body_text = "\n".join(body_lines).strip()
        if len(body_text) < 30:
            raise RuntimeError("local OCR text too short")

        title = str(title_hint or "").strip()
        if not title:
            first_line = body_lines[0]
            title = first_line[:80]

        confidence = sum(score for _, score in filtered) / max(1, len(filtered))
        keywords = self._extract_keywords_from_lines(body_lines, output_language)
        if source_url:
            body_text = f"{body_text}\nsource_url: {source_url}"

        return OCRExtractResult(
            provider="ocrmac_vision",
            confidence=round(confidence, 3),
            title=title,
            body_text=body_text,
            keywords=keywords[:8],
        )

    def _extract_with_openai(
        self,
        *,
        image_base64: str,
        mime_type: str,
        source_url: str | None,
        title_hint: str | None,
        output_language: str,
    ) -> OCRExtractResult:
        language_name = {
            "zh-CN": "简体中文",
            "zh-TW": "繁體中文",
            "en": "English",
            "ja": "日本語",
            "ko": "한국어",
        }[output_language]
        prompt = (
            "You are an OCR extractor for long-form article screenshots.\n"
            "Return strict JSON only, with keys: title, body_text, keywords, confidence.\n"
            "Rules:\n"
            "1) Keep all JSON keys in English.\n"
            f"2) body_text and title should be written in {language_name} ({output_language}) when possible.\n"
            "3) body_text should keep key paragraphs and remove UI chrome/noise.\n"
            "4) confidence is 0.0~1.0.\n"
            f"5) title_hint={title_hint or ''}\n"
            f"6) source_url={source_url or ''}\n"
        )
        payload = {
            "model": self.settings.openai_vision_model or self.settings.openai_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.openai_api_key}",
        }
        if self.settings.openai_organization:
            headers["OpenAI-Organization"] = self.settings.openai_organization
        if self.settings.openai_project:
            headers["OpenAI-Project"] = self.settings.openai_project

        req = request.Request(
            url=f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            ssl_context: ssl.SSLContext | None = None
            if not self.settings.openai_verify_ssl:
                ssl_context = ssl._create_unverified_context()
            elif self.settings.openai_ca_bundle:
                ssl_context = ssl.create_default_context(cafile=self.settings.openai_ca_bundle)
            timeout_seconds = min(max(8, self.settings.openai_timeout_seconds), 15)
            with request.urlopen(req, timeout=timeout_seconds, context=ssl_context) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"openai vision http {exc.code}: {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"openai vision request failed: {exc}") from exc

        response_json = json.loads(body)
        content = extract_openai_message_content(response_json)
        if not content:
            raise RuntimeError("empty openai vision content")

        parsed = self._safe_parse_json(content)
        title = str(parsed.get("title") or title_hint or "").strip()
        body_text = str(parsed.get("body_text") or "").strip()
        keywords_raw = parsed.get("keywords")
        keywords: list[str] = []
        if isinstance(keywords_raw, list):
            keywords = [str(value).strip() for value in keywords_raw if str(value).strip()]
        confidence_value = parsed.get("confidence")
        try:
            confidence = float(confidence_value)
        except Exception:
            confidence = 0.65
        confidence = max(0.0, min(1.0, confidence))

        if len(body_text) < 40:
            raise RuntimeError("openai vision body_text too short")

        return OCRExtractResult(
            provider="openai_vision",
            confidence=confidence,
            title=title,
            body_text=body_text,
            keywords=keywords[:8],
        )

    def _safe_parse_json(self, value: str) -> dict:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        start = value.find("{")
        end = value.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(value[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def _ocr_language_preferences(self, output_language: str) -> list[str]:
        mapping = {
            "zh-CN": ["zh-Hans", "en-US"],
            "zh-TW": ["zh-Hant", "yue-Hant", "en-US"],
            "en": ["en-US"],
            "ja": ["ja-JP", "en-US"],
            "ko": ["ko-KR", "en-US"],
        }
        return mapping.get(output_language, ["en-US"])

    def _extract_keywords_from_lines(self, lines: list[str], output_language: str) -> list[str]:
        joined = " ".join(lines)
        candidates: list[str] = []
        if output_language in {"zh-CN", "zh-TW"}:
            for token in [
                "AI",
                "Agent",
                "模型",
                "大模型",
                "自动化",
                "公众号",
                "微信",
                "浏览器",
                "产品",
                "技术",
                "效率",
            ]:
                if token in joined:
                    candidates.append(token)
        else:
            for token in [
                "AI",
                "agent",
                "model",
                "automation",
                "product",
                "browser",
                "workflow",
                "efficiency",
                "wechat",
            ]:
                if token.lower() in joined.lower():
                    candidates.append(token)
        if candidates:
            return list(dict.fromkeys(candidates))

        fallback = [value.strip() for value in lines[:3] if value.strip()]
        return [value[:18] for value in fallback if value]

    def _extract_with_mock(
        self,
        *,
        source_url: str | None,
        title_hint: str | None,
        output_language: str,
    ) -> OCRExtractResult:
        title = title_hint or localized_text(
            output_language,
            {
                "zh-CN": "OCR截图内容",
                "zh-TW": "OCR截圖內容",
                "en": "OCR Screenshot Content",
                "ja": "OCRスクリーンショット内容",
                "ko": "OCR 스크린샷 콘텐츠",
            },
            "OCR截图内容",
        )
        body_text = localized_text(
            output_language,
            {
                "zh-CN": (
                    "当前运行在本地 OCR 模拟模式。已接收截图并生成占位正文，用于打通“截图 -> 提炼 -> 入库”链路。"
                    "建议后续配置可用的视觉模型或 OCR 引擎获得真实正文。"
                ),
                "zh-TW": (
                    "目前運行於本地 OCR 模擬模式。已接收截圖並生成占位正文，用於打通「截圖 -> 提煉 -> 入庫」鏈路。"
                    "建議後續配置可用視覺模型或 OCR 引擎取得真實正文。"
                ),
                "en": (
                    "Running in local OCR mock mode. Screenshot was accepted and placeholder text was generated "
                    "to validate the pipeline from capture to summary and storage."
                ),
                "ja": (
                    "現在はローカル OCR モックモードです。スクリーンショットを受け取り、"
                    "取り込みパイプライン検証用のプレースホルダー本文を生成しました。"
                ),
                "ko": (
                    "현재 로컬 OCR 모의 모드로 동작 중입니다. 스크린샷을 수신했고, "
                    "캡처-요약-저장 파이프라인 검증용 본문을 생성했습니다."
                ),
            },
            "当前运行在本地 OCR 模拟模式。",
        )
        if source_url:
            body_text = f"{body_text}\nsource_url: {source_url}"
        return OCRExtractResult(
            provider="mock_ocr",
            confidence=0.55,
            title=title.strip(),
            body_text=body_text.strip(),
            keywords=[
                localized_text(
                    output_language,
                    {
                        "zh-CN": "截图OCR",
                        "zh-TW": "截圖OCR",
                        "en": "Screenshot OCR",
                        "ja": "画像OCR",
                        "ko": "스크린샷 OCR",
                    },
                    "截图OCR",
                ),
                localized_text(
                    output_language,
                    {
                        "zh-CN": "自动采集",
                        "zh-TW": "自動採集",
                        "en": "Auto Collect",
                        "ja": "自動収集",
                        "ko": "자동 수집",
                    },
                    "自动采集",
                ),
            ],
        )
