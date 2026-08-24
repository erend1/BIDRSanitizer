from __future__ import annotations

from pathlib import Path
from typing import Protocol


class WordToPDFConverter(Protocol):
    def convert_to_pdf(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        ...