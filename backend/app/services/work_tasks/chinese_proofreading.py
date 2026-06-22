from __future__ import annotations

import re


_ASCII_PUNCT_RE = re.compile(r"[\u4e00-\u9fff][,;:!?][\u4e00-\u9fff]")
_REPEATED_PUNCT_RE = re.compile(r"[，。；：！？]{2,}")
_LONG_DIGIT_WITHOUT_UNIT_RE = re.compile(r"(?<![A-Za-z0-9])\d{4,}(?![A-Za-z0-9年月日号%％元万亿])")
_SPACED_CJK_RE = re.compile(r"[\u4e00-\u9fff]\s+[\u4e00-\u9fff]")
_UNCLOSED_BRACKET_RE = re.compile(r"[（(][^）)]{1,60}$|^[^（(]{0,60}[）)]")
_UNSAFE_ABSOLUTE_RE = re.compile(r"(一定|必然|100%|百分百|绝对|确保)(?:可以|能够|实现|达成|提升|解决)")


def proofread_chinese_delivery_text(lines: list[str], *, limit: int = 12) -> list[str]:
    """Return deterministic Chinese proofreading findings for formal deliverables.

    The checker intentionally stays conservative: it flags concrete, easy-to-review
    typography, numeric-unit, and overclaiming issues without rewriting the report.
    """

    findings: list[str] = []
    seen: set[str] = set()

    def add(message: str) -> None:
        normalized = message.strip()
        if not normalized or normalized in seen or len(findings) >= limit:
            return
        findings.append(normalized)
        seen.add(normalized)

    for index, raw in enumerate(lines, start=1):
        raw_text = str(raw or "").strip()
        text = " ".join(raw_text.split())
        if not text:
            continue
        if _ASCII_PUNCT_RE.search(text):
            add(f"第 {index} 行存在中文语境半角标点，建议改为全角中文标点。")
        if _REPEATED_PUNCT_RE.search(text):
            add(f"第 {index} 行存在连续重复标点，建议人工校对语气和断句。")
        if _SPACED_CJK_RE.search(raw_text):
            add(f"第 {index} 行存在中文词间多余空格，建议清理版式。")
        if _LONG_DIGIT_WITHOUT_UNIT_RE.search(text):
            add(f"第 {index} 行存在长数字但缺少明确单位，建议补充元/万元/年/月/% 等口径。")
        if _UNCLOSED_BRACKET_RE.search(text):
            add(f"第 {index} 行可能存在括号不闭合，建议检查。")
        if _UNSAFE_ABSOLUTE_RE.search(text):
            add(f"第 {index} 行存在绝对化承诺表达，正式外发前应改为有条件结论并绑定证据。")
        if "待核验" in text and not any(token in text for token in ("下一步", "验证", "补充", "确认", "责任")):
            add(f"第 {index} 行包含待核验事项，建议补充责任人或验证动作。")

    if not findings:
        findings.append("未发现确定性中文标点、单位、括号或绝对化承诺问题；仍建议正式外发前人工通读。")
    return findings
