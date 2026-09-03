from __future__ import annotations

from collections.abc import Iterable
import tempfile
from pathlib import Path

import img2pdf
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw, ImageStat

from bidr_sanitizer.pdf.base import (
    ImageSanitizerProvider,
)
from bidr_sanitizer.pdf.models import (
    PDFPageSanitizationResult,
    PDFSanitizationResult,
)
from bidr_sanitizer.redaction import RedactionRegion


DEFAULT_PDF_DPI = 300
PDF_PALETTE_SIZES = (16, 32, 64, 128, 256)
PDF_MAX_MEAN_CHANNEL_RMS = 6.0


def _mean_channel_rms(first: Image.Image, second: Image.Image) -> float:
    difference = ImageChops.difference(first, second)
    return sum(ImageStat.Stat(difference).rms) / 3.0


def _exact_black_palette_index(image: Image.Image) -> int:
    palette = list(image.getpalette() or ())
    if len(palette) < 768:
        palette.extend([0] * (768 - len(palette)))

    get_flattened_data = getattr(image, "get_flattened_data", None)
    if get_flattened_data is None:
        used_indices = set(image.getdata())
    else:
        used_indices = set(get_flattened_data())
    for index in used_indices:
        offset = index * 3
        if palette[offset : offset + 3] == [0, 0, 0]:
            return index

    unused_index = next(
        (index for index in range(256) if index not in used_indices),
        None,
    )
    if unused_index is None:
        unused_index = min(
            used_indices,
            key=lambda index: sum(palette[index * 3 : index * 3 + 3]),
        )

    offset = unused_index * 3
    palette[offset : offset + 3] = [0, 0, 0]
    image.putpalette(palette)
    return unused_index


def compact_redacted_pdf_page(
    image: Image.Image,
    redaction_regions: tuple[RedactionRegion, ...],
    margin: int,
) -> Image.Image:
    """Keep page dimensions while selecting a compact indexed-color image."""

    rgb = image.convert("RGB")
    compact = None

    for color_count in PDF_PALETTE_SIZES:
        candidate = rgb.quantize(
            colors=color_count,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )
        reconstructed = candidate.convert("RGB")
        error = _mean_channel_rms(rgb, reconstructed)
        reconstructed.close()

        if error <= PDF_MAX_MEAN_CHANNEL_RMS or color_count == 256:
            compact = candidate
            break

        candidate.close()

    assert compact is not None

    black_index = _exact_black_palette_index(compact)
    draw = ImageDraw.Draw(compact)
    for region in redaction_regions:
        bbox = region.bbox.expand(
            margin=margin,
            image_width=compact.width,
            image_height=compact.height,
        )
        draw.rectangle(
            [(bbox.x1, bbox.y1), (bbox.x2, bbox.y2)],
            fill=black_index,
        )

    return compact


def _render_page_to_png(
    page,
    output_path: Path,
    *,
    dpi: int,
) -> tuple[float, float]:
    """
    Render a PDF page to an RGB PNG.

    Returns the original PDF page dimensions in points.
    """

    if dpi <= 0:
        raise ValueError(
            "PDF rendering DPI must be positive."
        )

    width_pt, height_pt = page.get_size()

    scale = dpi / 72.0

    bitmap = page.render(
        scale=scale,
        rotation=0,

        # Include visible form fields when a form environment
        # was initialized on the document.
        may_draw_forms=True,

        # Include annotations in the rendered pixels.
        draw_annots=True,
    )

    try:
        image = (
            bitmap
            .to_pil()
            .convert("RGB")
            .copy()
        )

        image.save(
            output_path,
            format="PNG",
            dpi=(dpi, dpi),
        )

    finally:
        bitmap.close()

    return (
        float(width_pt),
        float(height_pt),
    )


def _build_image_only_pdf(
    pages: list[
        tuple[
            Path,
            float,
            float,
        ]
    ],
    output_path: Path,
) -> None:
    """
    Construct an entirely new PDF whose only page content consists
    of sanitized raster images.
    """

    if not pages:
        raise ValueError(
            "Cannot create a PDF with zero pages."
        )

    page_sizes = [
        (width_pt, height_pt)
        for _, width_pt, height_pt in pages
    ]
    layout_index = 0

    def exact_page_layout(
        image_width_px,
        image_height_px,
        image_dpi,
    ):
        nonlocal layout_index
        if layout_index >= len(page_sizes):
            raise RuntimeError("PDF encoder requested an unexpected page layout.")
        width_pt, height_pt = page_sizes[layout_index]
        layout_index += 1
        return width_pt, height_pt, width_pt, height_pt

    with output_path.open("wb") as output_stream:
        img2pdf.convert(
            *(str(image_path) for image_path, _, _ in pages),
            outputstream=output_stream,
            layout_fun=exact_page_layout,
            engine=img2pdf.Engine.internal,
            nodate=True,
            creator="BIDRSanitizer",
            producer="BIDRSanitizer",
        )

    if layout_index != len(page_sizes):
        output_path.unlink(missing_ok=True)
        raise RuntimeError("PDF encoder did not consume every sanitized page.")


def pdf_has_extractable_text(
    pdf_path: str | Path,
) -> bool:
    """
    Return True when the generated PDF contains machine-extractable
    page text.

    Our sanitized image-only PDF should return False.
    """

    pdf_path = Path(
        pdf_path
    )

    pdf = pdfium.PdfDocument(
        str(pdf_path)
    )

    try:
        for page_index in range(
            len(pdf)
        ):
            page = pdf[
                page_index
            ]

            try:
                text_page = (
                    page.get_textpage()
                )

                try:
                    text = (
                        text_page
                        .get_text_bounded()
                    )

                    if text.strip():
                        return True

                finally:
                    text_page.close()

            finally:
                page.close()

        return False

    finally:
        pdf.close()


def sanitize_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    sanitizer: ImageSanitizerProvider,
    dpi: int = DEFAULT_PDF_DPI,
    margin: int = 5,
    max_redaction_passes: int = 3,
    password: str | None = None,
) -> PDFSanitizationResult:
    """
    Convert a PDF into a brand-new rasterized, sanitized PDF.

    Each page:
        PDF
        -> RGB PNG
        -> image sanitizer
        -> verified sanitized PNG

    Then:
        sanitized PNG pages
        -> completely new image-only PDF
    """

    input_path = Path(
        input_path
    )

    output_path = Path(
        output_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            input_path
        )

    if (
        input_path.resolve()
        == output_path.resolve()
    ):
        raise ValueError(
            "Input and output PDF paths "
            "must be different."
        )

    if dpi <= 0:
        raise ValueError(
            "DPI must be positive."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    page_results: list[
        PDFPageSanitizationResult
    ] = []

    sanitized_pages: list[
        tuple[
            Path,
            float,
            float,
        ]
    ] = []

    with tempfile.TemporaryDirectory(
        prefix="bidr_pdf_"
    ) as temp_dir_string:

        temp_dir = Path(
            temp_dir_string
        )

        pdf = pdfium.PdfDocument(
            str(input_path),
            password=password,
        )

        try:
            # Important:
            # initialize form rendering BEFORE retrieving page
            # handles.
            pdf.init_forms()

            page_count = len(pdf)

            if page_count == 0:
                raise ValueError(
                    "Input PDF contains no pages."
                )

            for page_index in range(
                page_count
            ):
                page = pdf[
                    page_index
                ]

                try:
                    raw_page_path = (
                        temp_dir
                        / (
                            f"page_"
                            f"{page_index + 1:04d}"
                            f"_RAW.png"
                        )
                    )

                    safe_page_path = (
                        temp_dir
                        / (
                            f"page_"
                            f"{page_index + 1:04d}"
                            f"_SAFE.png"
                        )
                    )

                    (
                        width_pt,
                        height_pt,
                    ) = _render_page_to_png(
                        page,
                        raw_page_path,
                        dpi=dpi,
                    )

                finally:
                    page.close()

                sanitization = (
                    sanitizer.sanitize(
                        raw_page_path,
                        safe_page_path,
                        margin=margin,
                        max_redaction_passes=(
                            max_redaction_passes
                        ),
                        output_transform=compact_redacted_pdf_page,
                    )
                )

                page_result = (
                    PDFPageSanitizationResult(
                        page_number=(
                            page_index + 1
                        ),
                        width_pt=width_pt,
                        height_pt=height_pt,
                        sanitization=(
                            sanitization
                        ),
                    )
                )

                page_results.append(
                    page_result
                )

                sanitized_pages.append(
                    (
                        safe_page_path,
                        width_pt,
                        height_pt,
                    )
                )

            # Do not create a PDF that we already know failed.
            failed_pages = [
                page
                for page in page_results
                if not page.passed
            ]

            if failed_pages:
                failed_numbers = [
                    str(
                        page.page_number
                    )
                    for page
                    in failed_pages
                ]

                raise RuntimeError(
                    "PDF sanitization failed "
                    "verification on page(s): "
                    + ", ".join(
                        failed_numbers
                    )
                )

            _build_image_only_pdf(
                sanitized_pages,
                output_path,
            )

        finally:
            pdf.close()

    text_layer_empty = (
        not pdf_has_extractable_text(
            output_path
        )
    )

    return PDFSanitizationResult(
        output_path=output_path,
        pages=tuple(
            page_results
        ),
        text_layer_empty=(
            text_layer_empty
        ),
    )
