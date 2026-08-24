from __future__ import annotations

import os
        
from bidr_sanitizer.config import (
    PADDLE_DETECTION_MODEL_DIR,
    PADDLE_RECOGNITION_MODEL_DIR,
    configure_paddle_environment,
)
        
from pathlib import Path
from typing import Any

from bidr_sanitizer.models import BoundingBox
from bidr_sanitizer.model_check import (
    require_local_model,
)
from bidr_sanitizer.ocr.models import OCRTextItem


def parse_paddle_result(
    result_json: dict[str, Any],
) -> list[OCRTextItem]:
    """
    Convert PaddleOCR's public JSON representation into our own
    internal OCR representation.

    Keeping this conversion isolated prevents PaddleOCR-specific
    structures from leaking into the rest of the application.
    """

    payload = result_json.get("res", result_json)

    texts = payload.get("rec_texts", [])
    scores = payload.get("rec_scores", [])
    boxes = payload.get("rec_boxes", [])

    if not (
        len(texts)
        == len(scores)
        == len(boxes)
    ):
        raise ValueError(
            "Unexpected PaddleOCR result: "
            "texts, scores and boxes have different lengths."
        )

    items: list[OCRTextItem] = []

    for text, score, box in zip(
        texts,
        scores,
        boxes,
        strict=True,
    ):
        text = str(text).strip()

        if not text:
            continue

        if len(box) != 4:
            raise ValueError(
                f"Unexpected OCR bounding box shape: {box!r}"
            )

        x1, y1, x2, y2 = (
            int(value)
            for value in box
        )

        items.append(
            OCRTextItem(
                text=text,
                bbox=BoundingBox(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                ),
                confidence=float(score),
            )
        )

    return items


class PaddleOCRAdapter:
    """
    Thin adapter around PaddleOCR.

    The rest of BIDRSanitizer should never depend directly on
    PaddleOCR result objects.
    """

    def __init__(self) -> None:
        require_local_model(
            "paddle-ocr-detection",
            target_path=(
                PADDLE_DETECTION_MODEL_DIR
            ),
            verify_hashes=False,
        )

        require_local_model(
            "paddle-ocr-recognition",
            target_path=(
                PADDLE_RECOGNITION_MODEL_DIR
            ),
            verify_hashes=False,
        )
        
        # Disable PaddleX's remote model-source
        # connectivity check.
        os.environ[
            "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"
        ] = "True"

        configure_paddle_environment()

        # Important: import AFTER setting the environment
        # variable.
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(
            text_detection_model_name=(
                "PP-OCRv5_server_det"
            ),
            text_detection_model_dir=str(
                PADDLE_DETECTION_MODEL_DIR
            ),
            text_recognition_model_name=(
                "latin_PP-OCRv5_mobile_rec"
            ),
            text_recognition_model_dir=str(
                PADDLE_RECOGNITION_MODEL_DIR
            ),

            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,

            text_rec_score_thresh=0.0,
            
            device="cpu",
            engine="paddle",
        )
            

    def recognize(
        self,
        image_path: str | Path,
    ) -> list[OCRTextItem]:
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(image_path)

        results = list(
            self._ocr.predict(
                str(image_path),
                text_rec_score_thresh=0.0,
            )
        )

        if len(results) != 1:
            raise ValueError(
                "Image OCR was expected to produce exactly "
                f"one result, received {len(results)}."
            )

        result_json = results[0].json

        return parse_paddle_result(result_json)
