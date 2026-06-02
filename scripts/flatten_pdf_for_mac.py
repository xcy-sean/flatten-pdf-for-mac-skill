#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SIZE_TOLERANCE_PT = 1.0


@dataclass(frozen=True)
class PageSize:
    width: float
    height: float


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def import_pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return None, None
    return PdfReader, PdfWriter


def displayed_page_sizes(pdf_path: Path) -> list[PageSize]:
    PdfReader, _ = import_pypdf()
    if PdfReader is None:
        raise RuntimeError("Missing Python package: pypdf. Install it with: python3 -m pip install pypdf")

    reader = PdfReader(str(pdf_path))
    sizes: list[PageSize] = []
    for page in reader.pages:
        box = page.cropbox if page.cropbox is not None else page.mediabox
        width = float(box.width)
        height = float(box.height)
        rotate = int(page.get("/Rotate", 0) or 0) % 360
        if rotate in (90, 270):
            width, height = height, width
        sizes.append(PageSize(width, height))
    return sizes


def find_ghostscript() -> str | None:
    for exe in ("gs", "/opt/homebrew/bin/gs", "/usr/local/bin/gs"):
        found = shutil.which(exe) if "/" not in exe else (exe if Path(exe).exists() else None)
        if found:
            return found
    return None


def render_with_pymupdf(pdf_path: Path, render_dir: Path, dpi: int) -> list[Path]:
    import fitz

    render_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    out: list[Path] = []
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
        image_path = render_dir / f"page-{index:04d}.png"
        pix.save(str(image_path))
        out.append(image_path)
    doc.close()
    return out


def render_with_ghostscript(pdf_path: Path, render_dir: Path, dpi: int) -> list[Path]:
    gs = find_ghostscript()
    if not gs:
        raise RuntimeError(
            "Missing Ghostscript. Install it on macOS with: brew install ghostscript"
        )

    render_dir.mkdir(parents=True, exist_ok=True)
    pattern = render_dir / "page-%04d.png"
    cmd = [
        gs,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=png16m",
        f"-r{dpi}",
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        f"-sOutputFile={pattern}",
        str(pdf_path),
    ]
    subprocess.run(cmd, check=True)
    pages = sorted(render_dir.glob("page-*.png"))
    if not pages:
        raise RuntimeError("Ghostscript did not render any pages.")
    return pages


def images_to_pdf(image_paths: list[Path], sizes: list[PageSize], out_pdf: Path) -> None:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    if len(image_paths) != len(sizes):
        raise RuntimeError(f"Rendered {len(image_paths)} pages, expected {len(sizes)} pages.")

    pdf = canvas.Canvas(str(out_pdf), pagesize=(sizes[0].width, sizes[0].height))
    for image_path, size in zip(image_paths, sizes):
        pdf.setPageSize((size.width, size.height))
        # Draw the rendered full-page raster exactly over the PDF page box.
        pdf.drawImage(ImageReader(str(image_path)), 0, 0, width=size.width, height=size.height)
        pdf.showPage()
    pdf.save()


def validate_output(src_sizes: list[PageSize], out_pdf: Path) -> None:
    PdfReader, _ = import_pypdf()
    if PdfReader is None:
        raise RuntimeError("Missing Python package: pypdf. Install it with: python3 -m pip install pypdf")

    reader = PdfReader(str(out_pdf))
    out_sizes = displayed_page_sizes(out_pdf)
    if len(out_sizes) != len(src_sizes):
        raise RuntimeError(f"Validation failed: output has {len(out_sizes)} pages, expected {len(src_sizes)}.")

    for index, (page, src, out) in enumerate(zip(reader.pages, src_sizes, out_sizes), start=1):
        width_delta = abs(src.width - out.width)
        height_delta = abs(src.height - out.height)
        if width_delta > SIZE_TOLERANCE_PT or height_delta > SIZE_TOLERANCE_PT:
            raise RuntimeError(
                "Validation failed on page "
                f"{index}: source={src.width:.2f}x{src.height:.2f} pt, "
                f"output={out.width:.2f}x{out.height:.2f} pt."
            )

        xobjects = (page.get("/Resources") or {}).get("/XObject") or {}
        if len(xobjects) != 1:
            raise RuntimeError(f"Validation failed: page {index} should contain exactly one flattened image.")
        image = next(iter(xobjects.values())).get_object()
        if image.get("/Subtype") != "/Image" or image.get("/ColorSpace") != "/DeviceRGB" or image.get("/SMask"):
            raise RuntimeError(f"Validation failed: page {index} is not a plain RGB image-only page.")


def validate_visual_equivalence(src_pdf: Path, out_pdf: Path, tmp_dir: Path, engine: str) -> None:
    from PIL import Image, ImageChops, ImageStat

    src_dir = tmp_dir / "validate-src"
    out_dir = tmp_dir / "validate-out"
    dpi = 96
    if engine == "pymupdf":
        src_pages = render_with_pymupdf(src_pdf, src_dir, dpi)
        out_pages = render_with_pymupdf(out_pdf, out_dir, dpi)
    else:
        src_pages = render_with_ghostscript(src_pdf, src_dir, dpi)
        out_pages = render_with_ghostscript(out_pdf, out_dir, dpi)

    if len(src_pages) != len(out_pages):
        raise RuntimeError(f"Visual validation failed: source renders {len(src_pages)} pages, output renders {len(out_pages)}.")

    for index, (src_page, out_page) in enumerate(zip(src_pages, out_pages), start=1):
        with Image.open(src_page).convert("RGB") as src_img, Image.open(out_page).convert("RGB") as out_img:
            if src_img.size != out_img.size:
                raise RuntimeError(f"Visual validation failed: page {index} render size {out_img.size} != {src_img.size}.")
            diff = ImageChops.difference(src_img, out_img)
            mean = sum(ImageStat.Stat(diff).mean) / 3.0
            if mean > 6.0:
                raise RuntimeError(f"Visual validation failed: page {index} mean pixel difference {mean:.2f} is too high.")


def choose_engine(requested: str) -> str:
    if requested in ("pymupdf", "ghostscript"):
        return requested
    if module_exists("fitz"):
        return "pymupdf"
    return "ghostscript"


def check_dependencies(engine: str) -> None:
    missing: list[str] = []
    if not module_exists("reportlab"):
        missing.append("reportlab")
    if not module_exists("PIL"):
        missing.append("Pillow")
    if import_pypdf()[0] is None:
        missing.append("pypdf")
    if engine == "pymupdf" and not module_exists("fitz"):
        missing.append("PyMuPDF")
    if engine == "ghostscript" and not find_ghostscript():
        missing.append("Ghostscript")

    if missing:
        raise RuntimeError(
            "Missing dependencies: "
            + ", ".join(missing)
            + ". For Python packages use: "
            + "python3 -m pip install reportlab Pillow pypdf PyMuPDF"
            + ". For Ghostscript on macOS use: brew install ghostscript"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flatten PDF pages to RGB images for reliable macOS Preview/Quartz printing."
    )
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--dpi", type=int, default=400, help="Render DPI. Default: 400.")
    parser.add_argument(
        "--engine",
        choices=("auto", "pymupdf", "ghostscript"),
        default="auto",
        help="Rendering engine. Default: auto.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep rendered page images next to the output for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    src = args.input_pdf.expanduser().resolve()
    dst = args.output_pdf.expanduser().resolve()

    if not src.exists():
        raise RuntimeError(f"Input PDF does not exist: {src}")
    if src == dst:
        raise RuntimeError("Refusing to overwrite the source PDF. Choose a different output path.")
    if args.dpi < 72:
        raise RuntimeError("--dpi must be at least 72.")

    engine = choose_engine(args.engine)
    check_dependencies(engine)
    dst.parent.mkdir(parents=True, exist_ok=True)

    src_sizes = displayed_page_sizes(src)
    temp_owner = tempfile.TemporaryDirectory(prefix="flatten-pdf-") if not args.keep_temp else None
    render_dir = (
        Path(temp_owner.name)
        if temp_owner
        else dst.parent / f"{dst.stem}_rendered_pages"
    )

    try:
        if engine == "pymupdf":
            rendered = render_with_pymupdf(src, render_dir, args.dpi)
        else:
            rendered = render_with_ghostscript(src, render_dir, args.dpi)

        images_to_pdf(rendered, src_sizes, dst)
        validate_output(src_sizes, dst)
        validate_visual_equivalence(src, dst, render_dir, engine)
    finally:
        if temp_owner:
            temp_owner.cleanup()

    print(f"output={dst}")
    print(f"engine={engine}")
    print(f"dpi={args.dpi}")
    print(f"pages={len(src_sizes)}")
    for index, size in enumerate(src_sizes, start=1):
        print(f"page_{index}_size_pt={size.width:.2f}x{size.height:.2f}")
    print("validation=passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {' '.join(exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
