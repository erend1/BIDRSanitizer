from __future__ import annotations

import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from bidr_sanitizer.pdf.base import (
    ImageSanitizerProvider,
)
from bidr_sanitizer.pdf.models import (
    PDFPageSanitizationResult,
    PDFSanitizationResult,
)


DEFAULT_PDF_DPI = 300


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

    first_path, first_width, first_height = (
        pages[0]
    )

    canvas = Canvas(
        str(output_path),
        pagesize=(
            first_width,
            first_height,
        ),
        pageCompression=1,
    )

    # Do not copy any original PDF metadata.
    canvas.setAuthor("")
    canvas.setTitle("")
    canvas.setSubject("")
    canvas.setKeywords("")
    canvas.setCreator(
        "BIDRSanitizer"
    )

    for (
        image_path,
        width_pt,
        height_pt,
    ) in pages:

        canvas.setPageSize(
            (
                width_pt,
                height_pt,
            )
        )

        canvas.drawImage(
            ImageReader(
                str(image_path)
            ),
            0,
            0,
            width=width_pt,
            height=height_pt,
            preserveAspectRatio=False,
            mask="auto",
        )

        canvas.showPage()

    canvas.save()


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