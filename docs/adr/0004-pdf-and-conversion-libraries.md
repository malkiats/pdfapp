# ADR-0004: PDF, conversion and OCR libraries (with licensing)

Status: accepted, amended 2026-11-01 · Date: 2026-10-31 · Not legal advice: confirm with counsel before launch.

## Amendment 2026-11-01 (all-Vercel, lightweight scope, ADR-0006)
The **in-scope set** is pure Python wheels that run in-process on the Vercel Python runtime:
- pypdf and pikepdf: merge, split, rotate, reorder, compress, protect/unlock.
- pypdfium2: PDF → image, and page previews. It is the only renderer, so it stays in scope even though it was not on the coordinator's list.
- Pillow and img2pdf: image conversion, resizing, image → PDF.
- pdfplumber: text and table extraction.
- pyHanko: basic signatures.
- httpx and BeautifulSoup: webpage comparison.
- httpx client to Groq: AI tools (ADR-0007).

**Dropped from scope**: WeasyPrint (HTML → PDF, by user decision), LibreOffice, Tesseract, ocrmypdf, PaddleOCR, Ghostscript, Playwright. PyMuPDF and pdf2docx stay excluded (AGPL). With no AGPL and no subprocess binaries left, the open Ghostscript licensing question is closed. Redaction, PDF/A and Office conversions are out of scope. The table below is kept for history.

## Context
This is a commercial, closed-source SaaS. Licence risk depends on **how** a component is used:
- **In-process library** (imported into our Python process): a copyleft licence's conditions can extend to the combined program.
- **Separate unmodified executable** called as a subprocess: generally an independent work.

Licence type matters as follows:
- **GPL** obligations trigger on *distribution*. A SaaS does not distribute.
- **AGPL §13** extends obligations to users interacting over a network with a *modified* program.
- Many vendors still treat any AGPL dependency as unacceptable without a commercial licence.

## Licence summary and decision

| Component | Licence | Use | Decision |
|---|---|---|---|
| pypdf | BSD-3 | in-process | **Default**: merge, split, rotate, metadata, simple forms |
| pikepdf (+ libqpdf) | MPL-2.0 (qpdf: Apache-2.0) | in-process | **Default**: repair, linearise, encrypt/decrypt, object-level edits, image recompression, metadata/JS/attachment stripping |
| qpdf CLI | Apache-2.0 | subprocess | Optional (pikepdf covers it) |
| pypdfium2 (PDFium) | Apache-2.0 / BSD-3 | in-process | **Default renderer**: page → image (OCR input, thumbnails, rasterised redaction, PDF → image) |
| Pillow | MIT-CMU (HPND) | in-process | **Default**: image handling, recompression |
| img2pdf | LGPL-3.0 | in-process, unmodified | **Default** for lossless image → PDF. LGPL conditions are met by using it unmodified, with no distribution. |
| LibreOffice | MPL-2.0 | subprocess, unmodified | **Default**: Word/PPT/Excel → PDF (incl. PDF/A-2b export from office docs) |
| Tesseract | Apache-2.0 | subprocess | **Default OCR** (`hocr` + text-only PDF layer, merged with pikepdf) |
| ocrmypdf | MPL-2.0 | in-process/CLI | Optional. Several features depend on Ghostscript, so it is adopted only when Ghostscript is approved (below). |
| PaddleOCR | Apache-2.0 | in-process | Optional, later. Heavy (PaddlePaddle). Separate worker image if adopted. |
| pyHanko | MIT | in-process | **Default**: cryptographic (PAdES) signatures, validation |
| pdfplumber / pdfminer.six | MIT | in-process | Text/table extraction (PDF → Excel candidate, spike S4) |
| WeasyPrint | BSD-3 | in-process | **Default HTML → PDF**, with a custom `url_fetcher` that goes through the SSRF guard |
| Playwright + Chromium | Apache-2.0 / BSD | subprocess | Deferred. Only if JS-rendered pages are required. Needs a dedicated egress-restricted worker. |
| **PyMuPDF (fitz)** | **AGPL-3.0** or commercial (Artifex) | in-process | **Not used.** In-process AGPL would cover our backend. Revisit only with a purchased commercial licence (it would simplify true redaction and PDF → Word). |
| pdf2docx | MIT, but depends on PyMuPDF | in-process | **Not used** (AGPL via dependency) |
| **Ghostscript** | **AGPL-3.0** or commercial (Artifex) | subprocess | **Not in the default build.** Needed for best-in-class compression and PDF → PDF/A. Adopt only as (a) an unmodified binary in an isolated subprocess, with a source offer and licence notice published, after counsel review, or (b) under an Artifex commercial licence. Open question Q3. |
| Poppler utils | GPL-2/3 | subprocess | Avoid (pypdfium2 covers rendering). Acceptable as an unmodified subprocess in SaaS if ever needed. |

## Feature mapping without AGPL
- Compress: pikepdf object streams + Pillow image downsampling/recompression. This is good but weaker than Ghostscript on some files.
- **Redaction that truly removes content**: affected pages are rendered with pypdfium2, boxes are burned in, and each page is rebuilt as an image (optionally with a re-OCR'd text layer). The whole document has metadata, XMP, annotations, attachments, JavaScript and form fields stripped. Every output is **verified** by text extraction to confirm redacted strings are absent. Vector-preserving redaction is spike S3.
- PDF/A: from office sources through LibreOffice export. PDF → PDF/A needs Ghostscript (Q3), so it stays `coming_soon` until then.
- PDF → Word/PPT: quality is uncertain without PyMuPDF (spike S4). PDF → Excel: pdfplumber tables → openpyxl (MIT).
- Signatures: "image signature" is a visual stamp only, labelled as such in the UI. "Digital signature" uses pyHanko with a user-supplied certificate or a later CA integration.

## Consequences
- (+) No AGPL code in the default image. The backend can stay closed-source.
- (−) Compression and PDF/A trail competitors until Ghostscript (or a commercial SDK) is decided.
- CI produces a licence inventory (`pip-licenses`, plus `apt` package list for images) and fails on any new AGPL/GPL entry not on the allowlist.
