import AppKit
import Foundation
import PDFKit
import Vision

struct OcrPage: Encodable {
    let page: Int
    let text: String
}

func usage() -> Never {
    fputs("usage: industry-vision-ocr --input <pdf-path>\n", stderr)
    exit(64)
}

let arguments = CommandLine.arguments
guard let inputIndex = arguments.firstIndex(of: "--input"), inputIndex + 1 < arguments.count else {
    usage()
}

let input = URL(fileURLWithPath: arguments[inputIndex + 1])
guard let document = PDFDocument(url: input) else {
    fputs("cannot open pdf\n", stderr)
    exit(2)
}

let encoder = JSONEncoder()
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let image = page.thumbnail(of: NSSize(width: 1800, height: 2400), for: .mediaBox)
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        continue
    }
    let text = (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
        .trimmingCharacters(in: .whitespacesAndNewlines)
    guard !text.isEmpty, let data = try? encoder.encode(OcrPage(page: index + 1, text: text)) else { continue }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
}
