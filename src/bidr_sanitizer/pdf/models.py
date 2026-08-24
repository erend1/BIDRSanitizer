from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.pipeline import (
    SanitizationResult,
)


@dataclass(frozen=True, slots=True)
class PDFPageSanitizationResult:
    page_number: int
    width_pt: float
    height_pt: float
    sanitization: SanitizationResult

    @property
    def passed(self) -> bool:
        return self.sanitization.passed


@dataclass(frozen=True, slots=True)
class PDFSanitizationResult:
    output_path: Path
    pages: tuple[
        PDFPageSanitizationResult,
        ...
    ]
    text_layer_empty: bool

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def passed(self) -> bool:
        return (
            self.text_layer_empty
            and all(
                page.passed
                for page in self.pages
            )
        )