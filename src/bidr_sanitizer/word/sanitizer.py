from __future__ import annotations

import tempfile
from pathlib import Path

from bidr_sanitizer.pdf.base import (
    ImageSanitizerProvider,
)
from bidr_sanitizer.pdf.sanitizer import (
    sanitize_pdf,
)
from bidr_sanitizer.word.base import (
    WordToPDFConverter,
)
from bidr_sanitizer.word.models import (
    WordSanitizationResult,
)


def sanitize_word_document(
    input_path: str | Path,
    output_path: str | Path,
    *,
    converter: WordToPDFConverter,
    sanitizer: ImageSanitizerProvider,
    dpi: int = 300,
    margin: int = 5,
    max_redaction_passes: int = 3,
) -> WordSanitizationResult:

    input_path = Path(
        input_path
    ).resolve()

    output_path = Path(
        output_path
    ).resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            input_path
        )

    extension = (
        input_path
        .suffix
        .lower()
    )

    if extension not in {
        ".doc",
        ".docx",
    }:
        raise ValueError(
            "Expected a .doc or .docx file."
        )

    if output_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Sanitized Word output must "
            "currently be a PDF."
        )

    with tempfile.TemporaryDirectory(
        prefix="bidr_word_"
    ) as temp_dir_string:

        temp_dir = Path(
            temp_dir_string
        )

        intermediate_pdf = (
            temp_dir
            / "word_rendered.pdf"
        )

        converter.convert_to_pdf(
            input_path,
            intermediate_pdf,
        )

        pdf_result = sanitize_pdf(
            intermediate_pdf,
            output_path,
            sanitizer=sanitizer,
            dpi=dpi,
            margin=margin,
            max_redaction_passes=(
                max_redaction_passes
            ),
        )

    return WordSanitizationResult(
        input_path=input_path,
        output_path=output_path,
        source_format=extension,
        pdf_result=pdf_result,
    )