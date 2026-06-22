from __future__ import annotations

import math
import zlib


def _pdf_placeholder_rgb(width: int = 160, height: int = 90) -> tuple[int, int, bytes]:
    rows = bytearray()
    for y in range(height):
        for x in range(width):
            if y < 8:
                color = (29, 78, 216)
            elif x < 8:
                color = (4, 120, 87)
            elif y > height - 10:
                color = (234, 88, 12)
            elif (x // 12 + y // 9) % 7 == 0:
                color = (219, 234, 254)
            else:
                shade = 246 - ((x + y) % 10)
                color = (shade, min(255, shade + 5), 255)
            rows.extend(color)
    return width, height, bytes(rows)


def _pdf_image_xobject() -> bytes:
    width, height, raw_rgb = _pdf_placeholder_rgb()
    compressed = zlib.compress(raw_rgb, level=9)
    return (
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n"
    ).encode("utf-8") + compressed + b"\nendstream"

def _pdf_hex(text: str) -> str:
    encoded = text.encode("utf-16-be")
    return encoded.hex().upper()


def _pdf_wrap_line(text: str, limit: int = 30) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return [""]
    pieces: list[str] = []
    start = 0
    while start < len(stripped):
        pieces.append(stripped[start:start + limit])
        start += limit
    return pieces or [stripped]


def _build_simple_pdf(
    lines: list[str],
    *,
    header: str | None = None,
    footer: str | None = None,
    layout_profile: str | None = None,
) -> bytes:
    page_height = 842
    start_x = 48
    start_y = 776 if header else 794
    line_height = 18
    max_lines_per_page = 36 if (header or footer) else 38
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(_pdf_wrap_line(line))
    if not wrapped_lines:
        wrapped_lines = [""]
    total_pages = max(1, math.ceil(len(wrapped_lines) / max_lines_per_page))
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    image_object_number = 5 if layout_profile else None
    page_object_numbers = []
    content_object_numbers = []
    next_object_number = 6 if image_object_number is not None else 5
    for _ in range(total_pages):
        page_object_numbers.append(next_object_number)
        content_object_numbers.append(next_object_number + 1)
        next_object_number += 2

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Count {total_pages} /Kids [{kids}] >>".encode("utf-8"))
    objects.append(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>"
    )
    if image_object_number is not None:
        objects.append(_pdf_image_xobject())

    for page_index in range(total_pages):
        page_lines = wrapped_lines[page_index * max_lines_per_page:(page_index + 1) * max_lines_per_page]
        stream_lines: list[str] = []
        if layout_profile:
            stream_lines.extend(
                [
                    "q",
                    "0.93 0.97 1 rg",
                    "0 800 595 42 re f",
                    "0.15 0.39 0.92 RG",
                    "1.5 w",
                    "36 62 523 728 re S",
                    "0.95 0.45 0.10 rg",
                    "36 62 8 728 re f",
                    "0.10 0.46 0.43 rg",
                    "44 62 4 728 re f",
                    "0.15 0.39 0.92 RG",
                    "0.75 w",
                    "48 760 499 0 re S",
                    "48 122 499 0 re S",
                    "0.85 0.90 1 RG",
                    "435 668 112 63 re S",
                    "q",
                    "112 0 0 63 435 668 cm",
                    "/Im1 Do",
                    "Q",
                    "Q",
                ]
            )
        if header:
            stream_lines.extend(
                [
                    "BT",
                    "/F1 9 Tf",
                    f"{start_x} 812 Td",
                    f"<{_pdf_hex(header[:72])}> Tj",
                    "ET",
                ]
            )
        stream_lines.extend(["BT", "/F1 11 Tf", f"{line_height} TL", f"{start_x} {start_y} Td"])
        first = True
        for line in page_lines:
            if first:
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
                first = False
            else:
                stream_lines.append("T*")
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
        stream_lines.append("ET")
        if footer:
            rendered_footer = footer.format(page=page_index + 1, total=total_pages)
            stream_lines.extend(
                [
                    "BT",
                    "/F1 9 Tf",
                    f"{start_x} 40 Td",
                    f"<{_pdf_hex(rendered_footer[:96])}> Tj",
                    "ET",
                ]
            )
        stream_bytes = "\n".join(stream_lines).encode("utf-8")
        xobject_resources = (
            f" /XObject << /Im1 {image_object_number} 0 R >>"
            if image_object_number is not None
            else ""
        )
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 {page_height}] /Resources << /Font << /F1 3 0 R >>{xobject_resources} >> /Contents {content_object_numbers[page_index]} 0 R >>"
        ).encode("utf-8")
        content_obj = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("utf-8")
            + stream_bytes
            + b"\nendstream"
        )
        objects.append(page_obj)
        objects.append(content_obj)

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("utf-8"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("utf-8"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("utf-8")
    )
    return bytes(output)
