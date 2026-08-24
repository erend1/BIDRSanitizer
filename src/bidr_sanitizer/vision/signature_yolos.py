from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image

from bidr_sanitizer.config import (
    SIGNATURE_MODEL_DIR,
)
from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)
from bidr_sanitizer.model_check import (
    require_local_model,
)


def expand_signature_bbox(
    bbox: BoundingBox,
    *,
    image_width: int,
    image_height: int,
    horizontal_ratio: float = 0.10,
    vertical_ratio: float = 0.20,
) -> BoundingBox:
    """
    Expand a signature detection conservatively.

    Signatures commonly contain thin strokes extending slightly beyond
    the detector's most confident region, so privacy redaction should
    deliberately cover some surrounding pixels.
    """

    horizontal_margin = (
        bbox.width
        * horizontal_ratio
    )

    vertical_margin = (
        bbox.height
        * vertical_ratio
    )

    return BoundingBox(
        x1=max(
            0,
            math.floor(
                bbox.x1
                - horizontal_margin
            ),
        ),
        y1=max(
            0,
            math.floor(
                bbox.y1
                - vertical_margin
            ),
        ),
        x2=min(
            image_width,
            math.ceil(
                bbox.x2
                + horizontal_margin
            ),
        ),
        y2=min(
            image_height,
            math.ceil(
                bbox.y2
                + vertical_margin
            ),
        ),
    )


def _intersection_over_union(
    first: BoundingBox,
    second: BoundingBox,
) -> float:
    x1 = max(
        first.x1,
        second.x1,
    )

    y1 = max(
        first.y1,
        second.y1,
    )

    x2 = min(
        first.x2,
        second.x2,
    )

    y2 = min(
        first.y2,
        second.y2,
    )

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (
        (x2 - x1)
        * (y2 - y1)
    )

    first_area = (
        first.width
        * first.height
    )

    second_area = (
        second.width
        * second.height
    )

    union = (
        first_area
        + second_area
        - intersection
    )

    if union <= 0:
        return 0.0

    return intersection / union


def _union_bbox(
    first: BoundingBox,
    second: BoundingBox,
) -> BoundingBox:
    return BoundingBox(
        x1=min(
            first.x1,
            second.x1,
        ),
        y1=min(
            first.y1,
            second.y1,
        ),
        x2=max(
            first.x2,
            second.x2,
        ),
        y2=max(
            first.y2,
            second.y2,
        ),
    )


def merge_signature_detections(
    detections: list[Detection],
    *,
    iou_threshold: float = 0.50,
) -> list[Detection]:
    """
    Merge duplicate detections of the same signature.

    For privacy, overlapping boxes are replaced with their union,
    ensuring that merging never reduces the redacted region.
    """

    merged: list[Detection] = []

    for detection in sorted(
        detections,
        key=lambda item: item.confidence,
        reverse=True,
    ):
        was_merged = False

        for index, existing in enumerate(
            merged
        ):
            iou = _intersection_over_union(
                detection.bbox,
                existing.bbox,
            )

            if iou < iou_threshold:
                continue

            merged[index] = Detection(
                detection_type=(
                    DetectionType.SIGNATURE
                ),
                bbox=_union_bbox(
                    existing.bbox,
                    detection.bbox,
                ),
                confidence=max(
                    existing.confidence,
                    detection.confidence,
                ),
            )

            was_merged = True
            break

        if not was_merged:
            merged.append(
                detection
            )

    return merged


class YOLOSSignatureDetector:
    """
    Local handwritten-signature detector.

    No input image or inference data is sent over the network.
    """

    def __init__(
        self,
        model_path: str | Path = (
            SIGNATURE_MODEL_DIR
        ),
        *,
        confidence_threshold: float = 0.25,
    ) -> None:

        if not (
            0.0
            <= confidence_threshold
            <= 1.0
        ):
            raise ValueError(
                "Confidence threshold must "
                "be between 0 and 1."
            )

        model_path = Path(
            model_path
        ).resolve()

        if model_path == SIGNATURE_MODEL_DIR.resolve():
            require_local_model(
                "signature-detection",
                target_path=model_path,
                verify_hashes=False,
            )

        elif not model_path.exists():
            raise FileNotFoundError(
                "Local signature model "
                "was not found: "
                f"{model_path}"
            )

        # Enforce local/offline Hugging Face operation.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ[
            "HF_HUB_DISABLE_TELEMETRY"
        ] = "1"

        from transformers import (
            AutoImageProcessor,
            AutoModelForObjectDetection,
        )

        self._confidence_threshold = (
            confidence_threshold
        )

        self._processor = (
            AutoImageProcessor
            .from_pretrained(
                str(model_path),
                local_files_only=True,
            )
        )

        self._model = (
            AutoModelForObjectDetection
            .from_pretrained(
                str(model_path),
                local_files_only=True,
            )
        )

        self._model.eval()

    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:

        import torch

        image_path = Path(
            image_path
        )

        if not image_path.exists():
            raise FileNotFoundError(
                image_path
            )

        with Image.open(
            image_path
        ) as source:
            image = source.convert(
                "RGB"
            )

        image_width, image_height = (
            image.size
        )

        inputs = self._processor(
            images=image,
            return_tensors="pt",
        )

        with torch.no_grad():
            outputs = self._model(
                **inputs
            )

        target_sizes = torch.tensor(
            [
                [
                    image_height,
                    image_width,
                ]
            ]
        )

        processed = (
            self._processor
            .post_process_object_detection(
                outputs,
                threshold=(
                    self._confidence_threshold
                ),
                target_sizes=target_sizes,
            )
        )

        if not processed:
            return []

        result = processed[0]

        detections: list[
            Detection
        ] = []

        for score, box in zip(
            result["scores"],
            result["boxes"],
            strict=True,
        ):
            confidence = float(
                score.item()
            )

            x1, y1, x2, y2 = [
                float(value)
                for value in box.tolist()
            ]

            # Guard against degenerate model output.
            x1_i = max(
                0,
                math.floor(x1),
            )

            y1_i = max(
                0,
                math.floor(y1),
            )

            x2_i = min(
                image_width,
                math.ceil(x2),
            )

            y2_i = min(
                image_height,
                math.ceil(y2),
            )

            if (
                x2_i <= x1_i
                or y2_i <= y1_i
            ):
                continue

            bbox = BoundingBox(
                x1=x1_i,
                y1=y1_i,
                x2=x2_i,
                y2=y2_i,
            )

            bbox = expand_signature_bbox(
                bbox,
                image_width=image_width,
                image_height=image_height,
            )

            detections.append(
                Detection(
                    detection_type=(
                        DetectionType.SIGNATURE
                    ),
                    bbox=bbox,
                    confidence=confidence,
                )
            )

        return merge_signature_detections(
            detections
        )
