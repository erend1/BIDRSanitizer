from __future__ import annotations

from pathlib import Path
from typing import Protocol

from bidr_sanitizer.ocr.models import OCRTextItem


class OCRProvider(Protocol):
    def recognize(
        self,
        image_path: str | Path,
    ) -> list[OCRTextItem]:
        ...