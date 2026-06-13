from __future__ import annotations

import math

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


def _build_simple_pdf(lines: list[str]) -> bytes:
    page_height = 842
    start_x = 48
    start_y = 794
    line_height = 18
    max_lines_per_page = 38
    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(_pdf_wrap_line(line))
    if not wrapped_lines:
        wrapped_lines = [""]
    total_pages = max(1, math.ceil(len(wrapped_lines) / max_lines_per_page))
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    page_object_numbers = []
    content_object_numbers = []
    next_object_number = 5
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

    for page_index in range(total_pages):
        page_lines = wrapped_lines[page_index * max_lines_per_page:(page_index + 1) * max_lines_per_page]
        stream_lines = ["BT", "/F1 11 Tf", f"{line_height} TL", f"{start_x} {start_y} Td"]
        first = True
        for line in page_lines:
            if first:
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
                first = False
            else:
                stream_lines.append("T*")
                stream_lines.append(f"<{_pdf_hex(line)}> Tj")
        stream_lines.append("ET")
        stream_bytes = "\n".join(stream_lines).encode("utf-8")
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 {page_height}] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_numbers[page_index]} 0 R >>"
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
