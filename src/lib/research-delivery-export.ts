function utf8Bytes(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function concatBytes(chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(total);
  let offset = 0;
  chunks.forEach((chunk) => {
    output.set(chunk, offset);
    offset += chunk.length;
  });
  return output;
}

function pdfHex(text: string): string {
  const codes: string[] = [];
  Array.from(text).forEach((char) => {
    const codePoint = char.codePointAt(0) || 0;
    if (codePoint <= 0xffff) {
      codes.push(codePoint.toString(16).padStart(4, "0"));
      return;
    }
    const adjusted = codePoint - 0x10000;
    const high = 0xd800 + (adjusted >> 10);
    const low = 0xdc00 + (adjusted & 0x3ff);
    codes.push(high.toString(16).padStart(4, "0"));
    codes.push(low.toString(16).padStart(4, "0"));
  });
  return codes.join("").toUpperCase();
}

function wrapPdfLine(text: string, limit = 30): string[] {
  const chars = Array.from(String(text || "").trim());
  if (!chars.length) {
    return [""];
  }
  const rows: string[] = [];
  for (let start = 0; start < chars.length; start += limit) {
    rows.push(chars.slice(start, start + limit).join(""));
  }
  return rows.length ? rows : [""];
}

export function replaceFilenameExtension(filename: string, extension: string): string {
  const normalizedExtension = extension.startsWith(".") ? extension : `.${extension}`;
  if (!filename) {
    return `download${normalizedExtension}`;
  }
  if (/\.[^./]+$/.test(filename)) {
    return filename.replace(/\.[^./]+$/, normalizedExtension);
  }
  return `${filename}${normalizedExtension}`;
}

export function triggerFileDownload(
  filename: string,
  content: BlobPart | Uint8Array,
  mimeType = "application/octet-stream",
): void {
  const blobContent = content instanceof Uint8Array
    ? (() => {
        const copy = new Uint8Array(content.byteLength);
        copy.set(content);
        return copy.buffer;
      })()
    : content;
  const blob = new Blob([blobContent], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function buildSimplePdfBytes(lines: string[]): Uint8Array {
  const pageHeight = 842;
  const startX = 48;
  const startY = 794;
  const lineHeight = 18;
  const maxLinesPerPage = 38;
  const wrappedLines = (lines || []).flatMap((line) => wrapPdfLine(line));
  if (!wrappedLines.length) {
    wrappedLines.push("");
  }

  const totalPages = Math.max(1, Math.ceil(wrappedLines.length / maxLinesPerPage));
  const objects: Uint8Array[] = [];

  objects.push(utf8Bytes("<< /Type /Catalog /Pages 2 0 R >>"));

  const pageObjectNumbers: number[] = [];
  const contentObjectNumbers: number[] = [];
  let nextObjectNumber = 5;
  for (let index = 0; index < totalPages; index += 1) {
    pageObjectNumbers.push(nextObjectNumber);
    contentObjectNumbers.push(nextObjectNumber + 1);
    nextObjectNumber += 2;
  }

  const kids = pageObjectNumbers.map((number) => `${number} 0 R`).join(" ");
  objects.push(utf8Bytes(`<< /Type /Pages /Count ${totalPages} /Kids [${kids}] >>`));
  objects.push(
    utf8Bytes("<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"),
  );
  objects.push(
    utf8Bytes("<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>"),
  );

  for (let pageIndex = 0; pageIndex < totalPages; pageIndex += 1) {
    const pageLines = wrappedLines.slice(pageIndex * maxLinesPerPage, (pageIndex + 1) * maxLinesPerPage);
    const streamLines = ["BT", "/F1 11 Tf", `${lineHeight} TL`, `${startX} ${startY} Td`];
    pageLines.forEach((line, index) => {
      if (index > 0) {
        streamLines.push("T*");
      }
      streamLines.push(`<${pdfHex(line)}> Tj`);
    });
    streamLines.push("ET");
    const streamBytes = utf8Bytes(streamLines.join("\n"));
    objects.push(
      utf8Bytes(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 ${pageHeight}] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentObjectNumbers[pageIndex]} 0 R >>`,
      ),
    );
    objects.push(
      concatBytes([
        utf8Bytes(`<< /Length ${streamBytes.length} >>\nstream\n`),
        streamBytes,
        utf8Bytes("\nendstream"),
      ]),
    );
  }

  const header = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]);
  const outputChunks: Uint8Array[] = [header];
  const offsets = [0];
  let currentLength = header.length;

  objects.forEach((objectBytes, index) => {
    offsets.push(currentLength);
    const block = concatBytes([
      utf8Bytes(`${index + 1} 0 obj\n`),
      objectBytes,
      utf8Bytes("\nendobj\n"),
    ]);
    outputChunks.push(block);
    currentLength += block.length;
  });

  const xrefOffset = currentLength;
  const xrefLines = [`xref`, `0 ${offsets.length}`, "0000000000 65535 f "];
  offsets.slice(1).forEach((offset) => {
    xrefLines.push(`${String(offset).padStart(10, "0")} 00000 n `);
  });
  outputChunks.push(
    utf8Bytes(
      `${xrefLines.join("\n")}\ntrailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`,
    ),
  );
  return concatBytes(outputChunks);
}

export function buildSimplePdfFromText(text: string): Uint8Array {
  return buildSimplePdfBytes(String(text || "").split(/\r?\n/));
}
