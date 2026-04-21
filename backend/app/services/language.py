from __future__ import annotations

from typing import Literal


OutputLanguage = Literal["zh-CN", "zh-TW", "en", "ja", "ko"]
SUPPORTED_OUTPUT_LANGUAGES: tuple[OutputLanguage, ...] = ("zh-CN", "zh-TW", "en", "ja", "ko")
DEFAULT_OUTPUT_LANGUAGE: OutputLanguage = "zh-CN"

LANGUAGE_DISPLAY_NAME: dict[OutputLanguage, str] = {
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
}


def normalize_output_language(value: str | None) -> OutputLanguage:
    if value in SUPPORTED_OUTPUT_LANGUAGES:
        return value
    return DEFAULT_OUTPUT_LANGUAGE


def describe_output_language(value: str | None) -> str:
    code = normalize_output_language(value)
    return f"{LANGUAGE_DISPLAY_NAME[code]} ({code})"


def localized_text(value: str | None, mapping: dict[str, str], fallback: str) -> str:
    code = normalize_output_language(value)
    if code in mapping:
        return mapping[code]
    if code == "zh-TW" and "zh-CN" in mapping:
        return mapping["zh-CN"]
    if "en" in mapping:
        return mapping["en"]
    if "zh-CN" in mapping:
        return mapping["zh-CN"]
    return fallback
