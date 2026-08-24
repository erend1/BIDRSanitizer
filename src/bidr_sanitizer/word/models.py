from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.pdf.models import (
    PDFSanitizationResult,
)


@dataclass(frozen=True, slots=True)
class WordSanitizationResult:
    input_path: Path
    output_path: Path
    source_format: str
    pdf_result: PDFSanitizationResult

    @property
    def passed(self) -> bool:
        return self.pdf_result.passed

    @property
    def page_count(self) -> int:
        return self.pdf_result.page_count