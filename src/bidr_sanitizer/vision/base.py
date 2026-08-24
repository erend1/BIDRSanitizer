from __future__ import annotations

from pathlib import Path
from typing import Protocol

from bidr_sanitizer.models import Detection


class FaceDetectorProvider(Protocol):
    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:
        ...


class SignatureDetectorProvider(Protocol):
    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:
        ...