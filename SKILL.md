---
name: flatten-pdf-for-mac
description: Flatten PDF pages to remove transparent stamp, seal, watermark, image-mask, soft-mask, overprint, or blend-mode rendering problems that appear in macOS Preview, Quartz, Adobe Acrobat printing on Mac, or physical Mac printouts. Use when a PDF looks correct on Windows but shows white boxes, translucent backgrounds, missing transparency, or wrong stamp backgrounds on macOS, especially for certificates, invoices, official seals, scanned documents, and PDFs containing PNG stamps or transparent overlays.
---

# Flatten PDF for Mac Printing

## Core Workflow

Use the bundled script first:

```bash
python3 /Users/xcy/.codex/skills/flatten-pdf-for-mac/scripts/flatten_pdf_for_mac.py INPUT.pdf OUTPUT.pdf
```

The script:
- Checks dependencies before conversion.
- Prefers PyMuPDF (`fitz`) when installed.
- Falls back to Ghostscript plus ReportLab when PyMuPDF is unavailable.
- Renders each page to an RGB image, then writes a new image-only PDF.
- Preserves the source PDF's displayed page size, including `/Rotate`.
- Verifies page count, per-page output size, full-page image placement, and image-only RGB structure after writing.
- Re-renders source and output at low resolution and compares pixels to catch accidental cropping.

## Stability Guardrails

Never generate a PDF by writing an oversized raster page and then using pypdf to shrink or rewrite only `/MediaBox` or `/CropBox`. That failure mode produces a PDF whose page size validates correctly but whose image content is not scaled with the page, so macOS Preview/printing shows only a cropped corner of the certificate.

Always create each output page at the final displayed source size first, then draw the rendered full-page image into that exact rectangle:

```text
page size = source displayed size
image placement = x=0, y=0, width=page width, height=page height
```

Treat size-only validation as insufficient. A successful run must also pass visual equivalence validation between source rendering and output rendering. If visual validation fails, do not deliver or batch-package the output.

## Output Rules

Always write final PDFs to the user's requested destination, or to the current task's `outputs/` directory when no destination is given.

Use a descriptive suffix such as:

```text
原文件名_mac打印扁平化.pdf
```

Do not overwrite the source PDF unless the user explicitly asks.

## Conversion Choices

Default to full-page flattening. This is intentionally conservative: it removes the original PDF object graph that can trigger Quartz or Acrobat transparency differences.

Use `--dpi 400` unless the user requests otherwise:
- `300`: smaller file, usually enough for office printing.
- `400`: default balance for certificates and stamps.
- `600`: sharper but much larger.

Use `--engine auto` by default. Use `--engine pymupdf` only when `fitz` is installed and produces correct output. Use `--engine ghostscript` when PyMuPDF is missing or suspected to interpret transparency differently from print output.

## Dependency Handling

Run the script and let it report missing dependencies. If conversion cannot proceed:
- For PyMuPDF path: install `PyMuPDF`.
- For Ghostscript fallback: install Ghostscript, ReportLab, and Pillow.
- On macOS, Ghostscript is commonly available through Homebrew: `brew install ghostscript`.

If the active Python lacks packages but Codex workspace dependencies are available, prefer the bundled Python runtime before asking the user to install anything.

## Verification

After conversion, inspect script output. It must report:
- Same page count.
- Same displayed page size for every page within tolerance.
- The flattened image covers the whole page, not a cropped corner.
- Visual comparison passes between source rendering and output rendering.
- A successful output path.

For important documents, render or open a preview image of the output and inspect the stamp area for white boxes or unexpected backgrounds before final delivery.

For batch jobs, run one representative rendered preview check after the batch completes, especially when the source PDFs use `/Rotate` or landscape certificate layout.

## User-Facing Summary

When finished, tell the user:
- Where the output PDF was saved.
- Which engine and DPI were used.
- That the output is image-only RGB pages intended to avoid macOS transparency printing issues.
- Whether page size verification passed.
