from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import struct
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape
import zlib


def _xml(value: object) -> str:
    return escape(str(value or ""), {'"': "&quot;"})


def _lines(values: Iterable[object], *, limit: int = 8) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text:
            rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def _openxml_text(value: object, *, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _openxml_hex(value: object, *, fallback: str) -> str:
    text = _openxml_text(value).lstrip("#").upper()
    if len(text) == 6 and all(ch in "0123456789ABCDEF" for ch in text):
        return text
    return fallback.lstrip("#").upper()


def _openxml_brand_template(brand_template: dict[str, object] | None) -> dict[str, str]:
    raw = brand_template if isinstance(brand_template, dict) else {}
    display_name = _openxml_text(raw.get("display_name"), fallback="Anti-FOMO Professional")
    return {
        "template_id": _openxml_text(raw.get("template_id"), fallback="anti-fomo-professional"),
        "display_name": display_name,
        "primary_color": _openxml_hex(raw.get("primary_color"), fallback="2563EB"),
        "secondary_color": _openxml_hex(raw.get("secondary_color"), fallback="0F766E"),
        "accent_color": _openxml_hex(raw.get("accent_color"), fallback="F97316"),
        "logo_text": _openxml_text(raw.get("logo_text"), fallback=display_name[:24]),
        "footer_text": _openxml_text(raw.get("footer_text"), fallback="Anti-FOMO 正式交付 · evidence-first delivery"),
        "confidentiality_label": _openxml_text(raw.get("confidentiality_label"), fallback="内部评审稿"),
        "font_family": _openxml_text(raw.get("font_family"), fallback="Microsoft YaHei / PingFang SC / Aptos"),
    }


def _openxml_asset_rows(
    assets: list[dict[str, object]] | None,
    *,
    asset_type: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, asset in enumerate(assets if isinstance(assets, list) else [], start=1):
        if not isinstance(asset, dict):
            continue
        data_rows = asset.get("data_rows")
        rows.append(
            {
                "asset_id": _openxml_text(asset.get("asset_id"), fallback=f"{asset_type}-{index}"),
                "asset_type": asset_type,
                "title": _openxml_text(asset.get("title"), fallback=("真实数据图表" if asset_type == "chart" else "可替换图片资源")),
                "description": _openxml_text(asset.get("description"), fallback="外发前替换为正式项目素材。"),
                "source": _openxml_text(asset.get("source"), fallback="delivery_supplement"),
                "unit": _openxml_text(asset.get("unit"), fallback=("万元/评分" if asset_type == "chart" else "16:9 可替换素材")),
                "period": _openxml_text(asset.get("period"), fallback="待项目确认"),
                "replacement_slot": _openxml_text(asset.get("replacement_slot"), fallback=f"{asset_type}-slot-{index}"),
                "data_rows": _lines(data_rows if isinstance(data_rows, list) else [], limit=4),
            }
        )
    return rows


def _openxml_asset_summary(asset: dict[str, object]) -> str:
    data_rows = asset.get("data_rows")
    data_summary = "；".join(data_rows if isinstance(data_rows, list) else [])
    pieces = [
        _openxml_text(asset.get("description")),
        f"单位：{_openxml_text(asset.get('unit'))}",
        f"期间：{_openxml_text(asset.get('period'))}",
        f"来源：{_openxml_text(asset.get('source'))}",
        f"替换槽：{_openxml_text(asset.get('replacement_slot'))}",
    ]
    if data_summary:
        pieces.append(f"数据：{data_summary}")
    return "；".join(piece for piece in pieces if piece and not piece.endswith("："))


def _openxml_chart_points(asset: dict[str, object], *, limit: int = 5) -> list[tuple[str, float]]:
    rows = asset.get("data_rows")
    points: list[tuple[str, float]] = []
    for index, row in enumerate(rows if isinstance(rows, list) else [], start=1):
        text = _openxml_text(row)
        if not text:
            continue
        if "：" in text:
            label, value = text.split("：", 1)
        elif ":" in text:
            label, value = text.split(":", 1)
        else:
            label, value = f"指标{index}", text
        numeric = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
        try:
            number = float(numeric)
        except ValueError:
            number = float(index)
        points.append((_openxml_text(label, fallback=f"指标{index}")[:32], number))
        if len(points) >= limit:
            break
    if not points:
        points = [("阶段一", 30.0), ("阶段二", 55.0), ("阶段三", 80.0)]
    return points


def _rgb_from_hex(value: str, *, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    text = _openxml_hex(value, fallback="%02X%02X%02X" % fallback)
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return fallback


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def _build_placeholder_png(
    *,
    brand_template: dict[str, str],
    asset: dict[str, object],
    width: int = 960,
    height: int = 540,
) -> bytes:
    """Create a deterministic native PNG placeholder without third-party libs."""

    primary = _rgb_from_hex(brand_template.get("primary_color", "2563EB"), fallback=(37, 99, 235))
    secondary = _rgb_from_hex(brand_template.get("secondary_color", "0F766E"), fallback=(15, 118, 110))
    accent = _rgb_from_hex(brand_template.get("accent_color", "F97316"), fallback=(249, 115, 22))
    title = _openxml_text(asset.get("title"), fallback="Anti-FOMO image asset")
    seed = sum(ord(ch) for ch in title)
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            if y < 42:
                color = primary
            elif x < 28:
                color = secondary
            elif y > height - 54:
                color = accent
            elif (x // 48 + y // 36 + seed) % 9 == 0:
                color = (229, 239, 255)
            else:
                mix = 248 - ((x + y + seed) % 12)
                color = (mix, min(255, mix + 3), 255)
            rows.extend(color)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _xlsx_col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name or "A"


def _xlsx_sheet_data(points: list[tuple[str, float]], *, chart_title: str) -> str:
    rows = [
        '<row r="1"><c r="A1" t="inlineStr"><is><t>维度</t></is></c><c r="B1" t="inlineStr"><is><t>'
        + _xml(chart_title)
        + "</t></is></c></row>"
    ]
    for row_index, (label, value) in enumerate(points, start=2):
        rows.append(
            f'<row r="{row_index}"><c r="A{row_index}" t="inlineStr"><is><t>{_xml(label)}</t></is></c><c r="B{row_index}"><v>{value:g}</v></c></row>'
        )
    return "".join(rows)


def _build_minimal_xlsx(points: list[tuple[str, float]], *, chart_title: str) -> bytes:
    buffer = BytesIO()
    dimension_end = f"B{len(points) + 1}"
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="ChartData" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:{dimension_end}"/>
  <sheetData>{_xlsx_sheet_data(points, chart_title=chart_title)}</sheetData>
</worksheet>""",
        )
    return buffer.getvalue()


def _pptx_chart_xml(asset: dict[str, object], points: list[tuple[str, float]]) -> str:
    chart_title = _openxml_text(asset.get("title"), fallback="P2.5 原生可编辑图表")
    point_count = len(points)
    cat_points = "".join(
        f'<c:pt idx="{index}"><c:v>{_xml(label)}</c:v></c:pt>'
        for index, (label, _value) in enumerate(points)
    )
    num_points = "".join(
        f'<c:pt idx="{index}"><c:v>{value:g}</c:v></c:pt>'
        for index, (_label, value) in enumerate(points)
    )
    last_row = point_count + 1
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <c:lang val="zh-CN"/>
  <c:roundedCorners val="0"/>
  <c:chart>
    <c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="1400" b="1"/><a:t>{_xml(chart_title)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>
    <c:plotArea>
      <c:layout/>
      <c:barChart>
        <c:barDir val="bar"/><c:grouping val="clustered"/><c:varyColors val="0"/>
        <c:ser>
          <c:idx val="0"/><c:order val="0"/>
          <c:tx><c:strRef><c:f>ChartData!$B$1</c:f><c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>{_xml(chart_title)}</c:v></c:pt></c:strCache></c:strRef></c:tx>
          <c:cat><c:strRef><c:f>ChartData!$A$2:$A${last_row}</c:f><c:strCache><c:ptCount val="{point_count}"/>{cat_points}</c:strCache></c:strRef></c:cat>
          <c:val><c:numRef><c:f>ChartData!$B$2:$B${last_row}</c:f><c:numCache><c:formatCode>General</c:formatCode><c:ptCount val="{point_count}"/>{num_points}</c:numCache></c:numRef></c:val>
        </c:ser>
        <c:axId val="123456"/><c:axId val="654321"/>
      </c:barChart>
      <c:catAx><c:axId val="123456"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="l"/><c:tickLblPos val="nextTo"/><c:crossAx val="654321"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx>
      <c:valAx><c:axId val="654321"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/><c:majorGridlines/><c:numFmt formatCode="General" sourceLinked="1"/><c:tickLblPos val="nextTo"/><c:crossAx val="123456"/><c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx>
    </c:plotArea>
    <c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>
    <c:plotVisOnly val="1"/>
  </c:chart>
  <c:externalData r:id="rIdWorkbook1"><c:autoUpdate val="0"/></c:externalData>
</c:chartSpace>"""


def _pptx_chart_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdWorkbook1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="../embeddings/chart-data.xlsx"/>
</Relationships>"""


def _docx_paragraph(
    text: str,
    *,
    style: str | None = None,
    bold: bool = False,
    align: str | None = None,
    color: str | None = None,
    size: int | None = None,
) -> str:
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    align_xml = f'<w:jc w:val="{align}"/>' if align else ""
    bold_xml = "<w:b/>" if bold else ""
    color_xml = f'<w:color w:val="{color}"/>' if color else ""
    size_xml = f'<w:sz w:val="{size}"/>' if size else ""
    return (
        "<w:p>"
        f"<w:pPr>{style_xml}{align_xml}</w:pPr>"
        "<w:r>"
        f"<w:rPr>{bold_xml}{color_xml}{size_xml}</w:rPr>"
        f"<w:t xml:space=\"preserve\">{_xml(text)}</w:t>"
        "</w:r>"
        "</w:p>"
    )


def _docx_table(rows: list[list[str]], *, accent_first_row: bool = True) -> str:
    cells: list[str] = []
    for row_index, row in enumerate(rows):
        cells.append("<w:tr>")
        for cell in row:
            shading = '<w:shd w:fill="EAF3FF"/>' if accent_first_row and row_index == 0 else ""
            cells.append(
                "<w:tc>"
                f"<w:tcPr><w:tcW w:w=\"0\" w:type=\"auto\"/>{shading}</w:tcPr>"
                f"{_docx_paragraph(cell, bold=bool(accent_first_row and row_index == 0))}"
                "</w:tc>"
            )
        cells.append("</w:tr>")
    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblStyle w:val=\"TableGrid\"/>"
        "<w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"CBD5E1\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        + "".join(cells)
        + "</w:tbl>"
    )


def _docx_toc_field() -> str:
    return (
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve">TOC \\o "1-2" \\h \\z \\u</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t>请在 Word 中右键更新域以刷新目录页码。</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )


def _docx_vml_placeholder(title: str, body: str, *, fill: str = "#EAF3FF", stroke: str = "#2563EB") -> str:
    return (
        "<w:p><w:r><w:pict>"
        '<v:roundrect style="width:460pt;height:92pt" arcsize="10%" '
        f'fillcolor="{fill}" strokecolor="{stroke}">'
        '<v:textbox inset="12pt,10pt,12pt,10pt">'
        '<w:txbxContent>'
        f"{_docx_paragraph(title, bold=True, color='0F172A')}"
        f"{_docx_paragraph(body, color='334155', size=18)}"
        "</w:txbxContent>"
        "</v:textbox>"
        "</v:roundrect>"
        "</w:pict></w:r></w:p>"
    )


def _docx_image_drawing(*, title: str, rel_id: str = "rIdImage1", cx: int = 5486400, cy: int = 3086100) -> str:
    return f"""
<w:p>
  <w:r>
    <w:drawing>
      <wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:docPr id="1" name="{_xml(title)}"/>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:nvPicPr><pic:cNvPr id="1" name="{_xml(title)}"/><pic:cNvPicPr/></pic:nvPicPr>
              <pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
              <pic:spPr>
                <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              </pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing>
  </w:r>
</w:p>"""


def _docx_content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""


def _docx_styles() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="40"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/><w:color w:val="475569"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:pPr><w:keepNext/><w:spacing w:before="280" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="30"/><w:color w:val="0F3B66"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Caption">
    <w:name w:val="Caption"/>
    <w:pPr><w:spacing w:before="80" w:after="140"/></w:pPr>
    <w:rPr><w:i/><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="18"/><w:color w:val="64748B"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="AFExecutiveNote">
    <w:name w:val="AF Executive Note"/>
    <w:pPr><w:spacing w:before="100" w:after="100"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/><w:color w:val="334155"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="AFBrandBand">
    <w:name w:val="AF Brand Band"/>
    <w:pPr><w:spacing w:before="120" w:after="120"/><w:shd w:fill="EAF3FF"/></w:pPr>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/><w:color w:val="0F3B66"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="AFChecklist">
    <w:name w:val="AF Checklist"/>
    <w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="20"/><w:color w:val="1E293B"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="AFSmallNote">
    <w:name w:val="AF Small Note"/>
    <w:pPr><w:spacing w:before="40" w:after="80"/></w:pPr>
    <w:rPr><w:i/><w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="18"/><w:color w:val="64748B"/></w:rPr>
  </w:style>
  <w:style w:type="table" w:styleId="TableGrid">
    <w:name w:val="Table Grid"/>
    <w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="CBD5E1"/><w:left w:val="single" w:sz="4" w:color="CBD5E1"/><w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/><w:right w:val="single" w:sz="4" w:color="CBD5E1"/><w:insideH w:val="single" w:sz="4" w:color="CBD5E1"/><w:insideV w:val="single" w:sz="4" w:color="CBD5E1"/></w:tblBorders></w:tblPr>
  </w:style>
</w:styles>"""


def _docx_numbering() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="1">
    <w:multiLevelType w:val="hybridMultilevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="420" w:hanging="300"/></w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="1">
      <w:start w:val="1"/>
      <w:numFmt w:val="lowerLetter"/>
      <w:lvlText w:val="%2)"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="240"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""


def _docx_settings() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:updateFields w:val="true"/>
  <w:evenAndOddHeaders w:val="false"/>
  <w:defaultTabStop w:val="720"/>
  <w:compat/>
</w:settings>"""


def _docx_numbered_paragraph(text: str, *, level: int = 0) -> str:
    return (
        "<w:p>"
        f'<w:pPr><w:pStyle w:val="AFChecklist"/><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"<w:r><w:t xml:space=\"preserve\">{_xml(text)}</w:t></w:r>"
        "</w:p>"
    )


def build_docx_bytes(
    *,
    title: str,
    subtitle: str,
    document_kind_label: str,
    meta_rows: list[str],
    sections: list[tuple[str, list[str]]],
    layout_rows: list[str],
    roundtrip_rows: list[str],
    proofreading_rows: list[str],
    brand_template: dict[str, object] | None = None,
    chart_assets: list[dict[str, object]] | None = None,
    image_assets: list[dict[str, object]] | None = None,
    renderer_strategy: str | None = None,
) -> bytes:
    brand = _openxml_brand_template(brand_template)
    charts = _openxml_asset_rows(chart_assets, asset_type="chart")
    images = _openxml_asset_rows(image_assets, asset_type="image")
    if not charts:
        charts = _openxml_asset_rows(
            [
                {
                    "title": "真实数据图表：投资估算与实施阶段图",
                    "description": "从当前报告预算和实施窗口派生，外发前可替换为正式项目数据。",
                    "source": "research_report / delivery_supplement",
                    "replacement_slot": "chart-slot-1",
                }
            ],
            asset_type="chart",
        )
    if not images:
        images = _openxml_asset_rows(
            [
                {
                    "title": "可替换图片资源：客户场景与架构示意图",
                    "description": "外发前替换为客户授权素材或可编辑架构图。",
                    "source": "manual replacement required",
                    "replacement_slot": "image-slot-1",
                }
            ],
            asset_type="image",
        )
    renderer_note = _openxml_text(
        renderer_strategy,
        fallback="受控渲染策略：默认使用 in-repo controlled preview + OpenXML 结构校验；LibreOffice CLI 可选。",
    )
    appendix_count = sum(1 for section_title, _rows in sections if section_title.startswith("附录"))
    executive_panel_rows = [
        ["模板版本", "Anti-FOMO P2.3 专业交付模板 / P2.4 客户品牌与可替换资产模板"],
        ["客户品牌模板", f"{brand['display_name']} · Logo：{brand['logo_text']} · #{brand['primary_color']}/#{brand['secondary_color']}/#{brand['accent_color']}"],
        ["保密标识", brand["confidentiality_label"]],
        ["文档类型", document_kind_label],
        ["章节/附录", f"{len(sections)} 个章节，其中 {appendix_count} 个附录"],
        ["校对状态", "已写入中文校对清单，外发前仍需人工确认"],
        ["视觉回归", "DOCX/PDF/PPTX 均保留稳定 fingerprint 和 required markers"],
        ["渲染策略", renderer_note],
    ]
    media_layout_rows = [
        ["P2.4 可替换资产清单", "客户品牌模板、真实数据图表、可替换图片资源均需保留来源、单位、期间和替换槽。"],
        *[
            [f"真实数据图表 {index}", f"{asset['title']}；{_openxml_asset_summary(asset)}"]
            for index, asset in enumerate(charts, start=1)
        ],
        *[
            [f"可替换图片资源 {index}", f"{asset['title']}；{_openxml_asset_summary(asset)}"]
            for index, asset in enumerate(images, start=1)
        ],
    ]
    first_chart = charts[0]
    first_image = images[0]
    image_png = _build_placeholder_png(brand_template=brand, asset=first_image)
    body: list[str] = [
        _docx_paragraph(title, style="Title"),
        _docx_paragraph(subtitle, style="Subtitle"),
        _docx_paragraph("交付摘要看板", style="Heading1"),
        _docx_table([["项目", "说明"], *executive_panel_rows]),
        _docx_paragraph("P2.5 复杂样式模板与真实打开验证门禁", style="AFBrandBand"),
        _docx_numbered_paragraph("复杂样式模板：DOCX 包内写入 Office theme、numbering、多级清单和品牌提示样式，供 Word/LibreOffice 保留。"),
        _docx_numbered_paragraph("真实打开验证：默认不启动 GUI；使用 office:roundtrip --libreoffice-convert 或 --open-gui 作为显式外发前门禁。"),
        _docx_numbered_paragraph("视觉回归：QuickLook/LibreOffice 转换产物必须与 visual_regression required markers 对齐。"),
        _docx_paragraph("本文件使用 P2.3 专业交付模板，并叠加 P2.4 客户品牌模板、真实数据图表、可替换图片资源和受控渲染策略：固定封面区、元信息区、Word 可更新目录、正文表格、图表/图片占位、校对清单与往返检查清单。", style="AFExecutiveNote"),
        _docx_paragraph("项目元信息", style="Heading1"),
        _docx_table([["字段", "内容"], *[_split_label_row(row) for row in meta_rows]]),
        _docx_paragraph("目录（Word 中可更新域）", style="Heading1"),
        _docx_toc_field(),
        _docx_table([["序号", "章节"], *[[str(index), section_title] for index, (section_title, _rows) in enumerate(sections, start=1)]]),
        _docx_paragraph("图表与图片排版占位", style="Heading1"),
        _docx_table([["资产", "外发要求"], *media_layout_rows]),
        _docx_vml_placeholder(
            f"图表占位 / 真实数据图表：{first_chart['title']}",
            f"{_openxml_asset_summary(first_chart)}；外发前可替换为正式可编辑图表。",
            fill="#FFF7ED",
            stroke=f"#{brand['accent_color']}",
        ),
        _docx_paragraph(f"图表 1：{first_chart['title']}，替换槽 {first_chart['replacement_slot']}。", style="Caption"),
        _docx_vml_placeholder(
            f"图片占位 / 可替换图片资源：{first_image['title']}",
            f"{_openxml_asset_summary(first_image)}；外发前需替换为可授权素材。",
            fill="#EEF2FF",
            stroke=f"#{brand['secondary_color']}",
        ),
        _docx_image_drawing(title=f"原生图片嵌入：{first_image['title']}"),
        _docx_paragraph(f"图片 1：{first_image['title']}，替换槽 {first_image['replacement_slot']}。", style="Caption"),
        _docx_paragraph("交付版式控制清单", style="Heading1"),
        _docx_table([["序号", "控制项"], *[[str(index), row] for index, row in enumerate(layout_rows, start=1)]]),
    ]
    for section_title, rows in sections:
        body.append(_docx_paragraph(section_title, style="Heading1"))
        body.append(_docx_table([["序号", "内容 / 证据 / 验证动作"], *[[str(index), row] for index, row in enumerate(_lines(rows, limit=80), start=1)]]))
    body.extend(
        [
            _docx_paragraph("中文校对清单", style="Heading1"),
            _docx_table([["序号", "问题 / 建议"], *[[str(index), row] for index, row in enumerate(proofreading_rows, start=1)]]),
            _docx_paragraph("PDF/Word 往返校验清单", style="Heading1"),
            _docx_table([["序号", "校验项"], *[[str(index), row] for index, row in enumerate(roundtrip_rows, start=1)]]),
        ]
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:o="urn:schemas-microsoft-com:office:office">'
        "<w:body>"
        + "".join(body)
        + '<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader1"/>'
        '<w:footerReference w:type="default" r:id="rIdFooter1"/>'
        '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1120" w:bottom="1440" w:left="1120" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _docx_content_types())
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""")
        archive.writestr("docProps/core.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{_xml(title)}</dc:title><dc:creator>Anti-FOMO</dc:creator><dc:subject>{_xml(document_kind_label)}</dc:subject>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>""")
        archive.writestr("docProps/app.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Anti-FOMO</Application></Properties>""")
        archive.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
  <Relationship Id="rIdImage1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
  <Relationship Id="rIdHeader1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>""")
        archive.writestr("word/styles.xml", _docx_styles())
        archive.writestr("word/settings.xml", _docx_settings())
        archive.writestr("word/numbering.xml", _docx_numbering())
        archive.writestr("word/theme/theme1.xml", _pptx_theme(brand))
        archive.writestr("word/media/image1.png", image_png)
        archive.writestr("word/header1.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">{_docx_paragraph(f"{brand['logo_text']} · Anti-FOMO 正式交付 · {document_kind_label} · {title}")}</w:hdr>""")
        archive.writestr("word/footer1.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>P2.3 native DOCX template · P2.4 brand/media assets · {brand['confidentiality_label']} · evidence anchors preserved · update fields before sending</w:t></w:r></w:p></w:ftr>""")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _split_label_row(row: str) -> list[str]:
    text = " ".join(str(row or "").split())
    if "：" in text:
        label, value = text.split("：", 1)
    elif ":" in text:
        label, value = text.split(":", 1)
    else:
        label, value = "说明", text
    return [label.strip(), value.strip()]


def build_pptx_bytes(
    *,
    title: str,
    subtitle: str,
    slides: list[tuple[str, list[str]]],
    brand_template: dict[str, object] | None = None,
    chart_assets: list[dict[str, object]] | None = None,
    image_assets: list[dict[str, object]] | None = None,
) -> bytes:
    brand = _openxml_brand_template(brand_template)
    charts = _openxml_asset_rows(chart_assets, asset_type="chart")
    images = _openxml_asset_rows(image_assets, asset_type="image")
    if not charts:
        charts = _openxml_asset_rows(
            [{"title": "真实数据图表：预算/收益/证据覆盖图", "source": "research_report"}],
            asset_type="chart",
        )
    if not images:
        images = _openxml_asset_rows(
            [{"title": "可替换图片资源：客户场景/架构图", "source": "manual replacement required"}],
            asset_type="image",
        )
    primary_chart = charts[0]
    primary_image = images[0]
    chart_points = _openxml_chart_points(primary_chart)
    image_png = _build_placeholder_png(brand_template=brand, asset=primary_image)
    selected_slides = [(title, _lines(rows, limit=5)) for title, rows in slides[:12]]
    if not selected_slides:
        selected_slides = [("交付概览", ["暂无可展示内容"])]
    all_slides = [(title, [subtitle])] + selected_slides
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _pptx_content_types(len(all_slides)))
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""")
        archive.writestr("docProps/core.xml", f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{_xml(title)}</dc:title><dc:creator>Anti-FOMO</dc:creator></cp:coreProperties>""")
        archive.writestr("docProps/app.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Anti-FOMO</Application></Properties>""")
        archive.writestr("ppt/presentation.xml", _pptx_presentation(len(all_slides)))
        archive.writestr("ppt/_rels/presentation.xml.rels", _pptx_presentation_rels(len(all_slides)))
        archive.writestr("ppt/theme/theme1.xml", _pptx_theme(brand))
        archive.writestr("ppt/charts/chart1.xml", _pptx_chart_xml(primary_chart, chart_points))
        archive.writestr("ppt/charts/_rels/chart1.xml.rels", _pptx_chart_rels())
        archive.writestr("ppt/media/image1.png", image_png)
        archive.writestr(
            "ppt/embeddings/chart-data.xlsx",
            _build_minimal_xlsx(chart_points, chart_title=_openxml_text(primary_chart.get("title"), fallback="P2.5 原生可编辑图表")),
        )
        for index, (slide_title, bullets) in enumerate(all_slides, start=1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                _pptx_slide(
                    slide_title,
                    bullets,
                    index=index,
                    brand_template=brand,
                    chart_assets=charts,
                    image_assets=images,
                ),
            )
            archive.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdChart1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/>
  <Relationship Id="rIdImage1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>""")
    return buffer.getvalue()


def _pptx_content_types(slide_count: int) -> str:
    overrides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>
  <Override PartName="/ppt/embeddings/chart-data.xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>
{overrides}
</Types>"""


def _pptx_presentation(slide_count: int) -> str:
    slide_ids = "\n".join(
        f'    <p:sldId id="{256 + index}" r:id="rId{index}"/>'
        for index in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldSz cx="12192000" cy="6858000" type="wide"/>
  <p:sldIdLst>
{slide_ids}
  </p:sldIdLst>
</p:presentation>"""


def _pptx_presentation_rels(slide_count: int) -> str:
    rels = "\n".join(
        f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
  <Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>"""


def _pptx_theme(brand_template: dict[str, str]) -> str:
    primary = _openxml_hex(brand_template.get("primary_color"), fallback="2563EB")
    secondary = _openxml_hex(brand_template.get("secondary_color"), fallback="0F766E")
    accent = _openxml_hex(brand_template.get("accent_color"), fallback="F97316")
    theme_name = _xml(_openxml_text(brand_template.get("display_name"), fallback="Anti-FOMO Professional"))
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="{theme_name}">
  <a:themeElements>
    <a:clrScheme name="{theme_name}">
      <a:dk1><a:srgbClr val="0F172A"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1E3A8A"/></a:dk2><a:lt2><a:srgbClr val="EAF3FF"/></a:lt2>
      <a:accent1><a:srgbClr val="{primary}"/></a:accent1><a:accent2><a:srgbClr val="{secondary}"/></a:accent2>
      <a:accent3><a:srgbClr val="{accent}"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4>
      <a:accent5><a:srgbClr val="64748B"/></a:accent5><a:accent6><a:srgbClr val="16A34A"/></a:accent6>
      <a:hlink><a:srgbClr val="{primary}"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Anti-FOMO Fonts">
      <a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface="Microsoft YaHei"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/><a:ea typeface="Microsoft YaHei"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Anti-FOMO Format"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def _pptx_text_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, paragraphs: list[str], *, title: bool = False) -> str:
    font_size = "3400" if title else "2000"
    para_xml = "".join(
        f'<a:p><a:r><a:rPr lang="zh-CN" sz="{font_size}" dirty="0"/><a:t>{_xml(text)}</a:t></a:r></a:p>'
        for text in paragraphs
    )
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{_xml(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
        <p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{para_xml}</p:txBody>
      </p:sp>"""


def _pptx_card_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, paragraphs: list[str], *, fill: str = "EFF6FF", line: str = "BFDBFE") -> str:
    para_parts: list[str] = []
    for index, text in enumerate(paragraphs):
        font_size = "2100" if index == 0 else "1700"
        bold = "1" if index == 0 else "0"
        para_parts.append(
            f'<a:p><a:r><a:rPr lang="zh-CN" sz="{font_size}" dirty="0" b="{bold}"/><a:t>{_xml(text)}</a:t></a:r></a:p>'
        )
    para_xml = "".join(para_parts)
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{_xml(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>
        <p:txBody><a:bodyPr wrap="square" lIns="180000" tIns="120000" rIns="180000" bIns="120000"/><a:lstStyle/>{para_xml}</p:txBody>
      </p:sp>"""


def _pptx_bar_shape(shape_id: int, x: int, y: int, cx: int, *, fill: str) -> str:
    return f"""
      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="Editable chart bar {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="150000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>
      </p:sp>"""


def _pptx_native_chart_shape(shape_id: int, x: int, y: int, cx: int, cy: int) -> str:
    return f"""
      <p:graphicFrame>
        <p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="P2.5 Native Editable Chart"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
        <p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">
            <c:chart r:id="rIdChart1"/>
          </a:graphicData>
        </a:graphic>
      </p:graphicFrame>"""


def _pptx_picture_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, *, rel_id: str = "rIdImage1") -> str:
    return f"""
      <p:pic>
        <p:nvPicPr><p:cNvPr id="{shape_id}" name="{_xml(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
      </p:pic>"""


def _pptx_slide(
    title: str,
    bullets: list[str],
    *,
    index: int,
    brand_template: dict[str, str],
    chart_assets: list[dict[str, object]],
    image_assets: list[dict[str, object]],
) -> str:
    bullet_lines = [f"• {row}" for row in _lines(bullets, limit=6)]
    if not bullet_lines:
        bullet_lines = ["• 待补充"]
    takeaway = bullet_lines[0].replace("• ", "", 1)[:46]
    chart = chart_assets[(index - 1) % len(chart_assets)] if chart_assets else {}
    image = image_assets[(index - 1) % len(image_assets)] if image_assets else {}
    primary = _openxml_hex(brand_template.get("primary_color"), fallback="2563EB")
    secondary = _openxml_hex(brand_template.get("secondary_color"), fallback="0F766E")
    accent = _openxml_hex(brand_template.get("accent_color"), fallback="F97316")
    brand_name = _openxml_text(brand_template.get("display_name"), fallback="Anti-FOMO Professional")
    logo_text = _openxml_text(brand_template.get("logo_text"), fallback=brand_name[:24])
    confidentiality = _openxml_text(brand_template.get("confidentiality_label"), fallback="内部评审稿")
    chart_title = _openxml_text(chart.get("title") if isinstance(chart, dict) else "", fallback="预算/收益/证据覆盖图")
    chart_body = _openxml_asset_summary(chart) if isinstance(chart, dict) else "替换为预算、收益、证据覆盖或推进阶段图"
    image_title = _openxml_text(image.get("title") if isinstance(image, dict) else "", fallback="客户场景/架构/路线图")
    image_body = _openxml_asset_summary(image) if isinstance(image, dict) else "客户场景/架构/路线图"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FBFF"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {_pptx_text_shape(2, "Title", 640000, 460000, 10800000, 820000, [title], title=True)}
      {_pptx_text_shape(12, "Brand Template", 9000000, 300000, 2200000, 420000, [f"客户品牌模板：{brand_name} · {logo_text}"])}
      {_pptx_card_shape(3, "Key Takeaway Card", 760000, 1360000, 5200000, 1180000, ["关键结论", takeaway], fill="EAF3FF")}
      {_pptx_card_shape(4, "Evidence Card", 6320000, 1360000, 4800000, 1180000, ["证据/假设", "外发前核验来源、金额、日期和责任人"], fill="ECFDF5", line="99F6E4")}
      {_pptx_text_shape(5, "Editable Bullet Body", 840000, 2780000, 5200000, 2700000, bullet_lines)}
      {_pptx_card_shape(6, "Chart Placeholder", 6420000, 2760000, 4600000, 1320000, [f"图表占位 / 真实数据图表：{chart_title}", chart_body[:96]], fill="FFF7ED", line=accent)}
      {_pptx_bar_shape(7, 6660000, 3860000, 1300000, fill=primary)}
      {_pptx_bar_shape(8, 6660000, 4140000, 2200000, fill=secondary)}
      {_pptx_bar_shape(9, 6660000, 4420000, 1700000, fill=accent)}
      {_pptx_native_chart_shape(13, 840000, 5480000, 5200000, 560000)}
      {_pptx_card_shape(10, "Image Placeholder", 6420000, 4840000, 4600000, 740000, [f"图片占位 / 可替换图片资源：{image_title}", image_body[:72]], fill="F5F3FF", line="C4B5FD")}
      {_pptx_picture_shape(14, f"原生图片嵌入：{image_title}", 10100000, 4860000, 900000, 520000)}
      {_pptx_text_shape(11, "Footer", 840000, 6260000, 10400000, 360000, [f"Anti-FOMO P2.3 editable PPTX template · P2.4 customer brand/media · {logo_text} · {confidentiality} · slide {index}"])}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""
