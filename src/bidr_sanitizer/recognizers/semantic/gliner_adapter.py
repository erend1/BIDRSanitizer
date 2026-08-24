from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bidr_sanitizer.config import (
    GLINER_MODEL_DIR,
)
from bidr_sanitizer.models import (
    DetectionType,
    TextDetection,
    TextSpan,
)


LABEL_MAPPING = {
    "person": DetectionType.PERSON,
    "address": DetectionType.ADDRESS,
}


class GLiNERPIIRecognizer:
    def __init__(
        self,
        *,
        model_path: str | Path = (
            GLINER_MODEL_DIR
        ),
        person_threshold: float = 0.35,
        address_threshold: float = 0.30,
    ) -> None:

        if not (
            0.0
            <= person_threshold
            <= 1.0
        ):
            raise ValueError(
                "Person threshold must be "
                "between 0 and 1."
            )

        if not (
            0.0
            <= address_threshold
            <= 1.0
        ):
            raise ValueError(
                "Address threshold must be "
                "between 0 and 1."
            )

        model_path = Path(
            model_path
        ).resolve()

        if not model_path.exists():
            raise FileNotFoundError(
                "Local GLiNER model "
                "was not found: "
                f"{model_path}"
            )

        # Absolutely no Hugging Face network access
        # during sanitizer operation.
        os.environ.setdefault(
            "HF_HUB_OFFLINE",
            "1",
        )

        os.environ.setdefault(
            "HF_HUB_DISABLE_TELEMETRY",
            "1",
        )

        from gliner import GLiNER

        self._person_threshold = (
            person_threshold
        )

        self._address_threshold = (
            address_threshold
        )

        self._model = (
            GLiNER.from_pretrained(
                str(model_path),
                local_files_only=True,
            )
        )

        self._model.eval()

    def recognize(
        self,
        text: str,
    ) -> list[TextDetection]:

        if not text.strip():
            return []

        minimum_threshold = min(
            self._person_threshold,
            self._address_threshold,
        )

        entities: list[dict[str, Any]] = (
            self._model.predict_entities(
                text,
                labels=[
                    "person",
                    "address",
                ],
                threshold=minimum_threshold,
            )
        )

        detections: list[TextDetection] = []

        for entity in entities:
            label = str(
                entity["label"]
            ).lower()

            detection_type = LABEL_MAPPING.get(
                label
            )

            if detection_type is None:
                continue

            score = float(
                entity.get("score", 1.0)
            )

            if (
                detection_type
                == DetectionType.PERSON
                and score < self._person_threshold
            ):
                continue

            if (
                detection_type
                == DetectionType.ADDRESS
                and score < self._address_threshold
            ):
                continue

            start = int(entity["start"])
            end = int(entity["end"])

            if end <= start:
                continue

            detections.append(
                TextDetection(
                    detection_type=detection_type,
                    span=TextSpan(
                        start=start,
                        end=end,
                    ),
                    confidence=score,
                )
            )

        return sorted(
            detections,
            key=lambda detection: (
                detection.span.start,
                detection.span.end,
            ),
        )