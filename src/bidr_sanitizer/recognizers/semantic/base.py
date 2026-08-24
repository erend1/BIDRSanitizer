from __future__ import annotations

from typing import Protocol

from bidr_sanitizer.models import TextDetection


class SemanticPIIRecognizer(Protocol):
    def recognize(
        self,
        text: str,
    ) -> list[TextDetection]:
        ...