from __future__ import annotations

from dataclasses import dataclass, field

from bidr_sanitizer.models import BoundingBox


@dataclass(frozen=True, slots=True)
class OCRTextItem:
    """
    One OCR-recognized text region.

    The actual text is intentionally excluded from repr() so that
    accidental logging/printing of this object does not expose PII.
    """

    text: str = field(repr=False)
    bbox: BoundingBox
    confidence: float

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("OCR text cannot be empty.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "OCR confidence must be between 0 and 1."
            )


@dataclass(frozen=True, slots=True)
class OCRSearchIndex:
    """
    Temporary searchable text reconstructed from OCR regions.

    text contains potentially sensitive information and therefore
    must remain in memory only.
    """

    text: str = field(repr=False)

    # Character span inside `text` for each OCRTextItem.
    item_spans: tuple[tuple[int, int], ...]