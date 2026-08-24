from collections import deque
from pathlib import Path

from PIL import Image

from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)
from bidr_sanitizer.ocr.models import OCRTextItem
from bidr_sanitizer.pipeline import (
    verify_image,
    sanitize_and_verify_image,
)


class FakeOCRProvider:
    def __init__(
        self,
        items: list[OCRTextItem],
    ) -> None:
        self._items = items

    def recognize(
        self,
        image_path: str | Path,
    ) -> list[OCRTextItem]:
        return self._items


class SequentialFakeOCRProvider:
    """
    Returns different OCR results on consecutive calls.

    Useful for testing:
        first OCR call  -> original image
        second OCR call -> sanitized image
    """

    def __init__(
        self,
        responses: list[list[OCRTextItem]],
    ) -> None:
        self._responses = deque(responses)

    def recognize(
        self,
        image_path: str | Path,
    ) -> list[OCRTextItem]:
        if not self._responses:
            raise RuntimeError(
                "Unexpected extra OCR invocation."
            )

        return self._responses.popleft()


class SequentialFakeFaceDetector:
    def __init__(
        self,
        responses: list[list[Detection]],
    ) -> None:
        self._responses = deque(
            responses
        )

    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:
        if not self._responses:
            raise RuntimeError(
                "Unexpected face-detector call."
            )

        return self._responses.popleft()


class SequentialFakeSignatureDetector:
    def __init__(
        self,
        responses: list[
            list[Detection]
        ],
    ) -> None:
        self._responses = deque(
            responses
        )

    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:

        if not self._responses:
            raise RuntimeError(
                "Unexpected signature "
                "detector call."
            )

        return (
            self._responses
            .popleft()
        )


def test_verification_passes_when_no_pii_remains(
    tmp_path,
):
    image_path = tmp_path / "safe.png"

    Image.new(
        "RGB",
        (300, 200),
        color="white",
    ).save(image_path)

    ocr = FakeOCRProvider(
        [
            OCRTextItem(
                text="İstanbul Rumeli Üniversitesi",
                bbox=BoundingBox(
                    x1=10,
                    y1=10,
                    x2=250,
                    y2=40,
                ),
                confidence=0.99,
            )
        ]
    )

    report = verify_image(
        image_path,
        ocr=ocr,
    )

    assert report.passed
    assert report.remaining_count == 0


def test_complete_sanitize_and_verify_pipeline(
    tmp_path,
):
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"

    Image.new(
        "RGB",
        (400, 200),
        color="white",
    ).save(input_path)

    original_ocr = [
        OCRTextItem(
            text="Telefon: 0532 123 45 67",
            bbox=BoundingBox(
                x1=30,
                y1=40,
                x2=300,
                y2=80,
            ),
            confidence=0.99,
        )
    ]

    sanitized_ocr = [
        OCRTextItem(
            text="Telefon:",
            bbox=BoundingBox(
                x1=30,
                y1=40,
                x2=100,
                y2=80,
            ),
            confidence=0.99,
        )
    ]

    ocr = SequentialFakeOCRProvider(
        [
            original_ocr,
            sanitized_ocr,
        ]
    )

    result = sanitize_and_verify_image(
        input_path=input_path,
        output_path=output_path,
        ocr=ocr,
    )

    assert output_path.exists()

    assert len(
        result.applied_detections
    ) == 1

    assert (
        result.applied_detections[0].detection_type
        == DetectionType.PHONE
    )

    assert result.passed


def test_verification_fails_when_phone_remains(
    tmp_path,
):
    image_path = tmp_path / "unsafe.png"

    Image.new(
        "RGB",
        (300, 200),
        color="white",
    ).save(image_path)

    ocr = FakeOCRProvider(
        [
            OCRTextItem(
                text="Telefon: 0532 123 45 67",
                bbox=BoundingBox(
                    x1=10,
                    y1=10,
                    x2=250,
                    y2=40,
                ),
                confidence=0.99,
            )
        ]
    )

    report = verify_image(
        image_path,
        ocr=ocr,
    )

    assert not report.passed
    assert report.remaining_count == 1

    assert (
        report.remaining_detections[0].detection_type
        == DetectionType.PHONE
    )


def test_empty_ocr_result_is_safe(
    tmp_path,
):
    image_path = tmp_path / "blank.png"

    Image.new(
        "RGB",
        (300, 200),
        color="white",
    ).save(image_path)

    ocr = FakeOCRProvider([])

    report = verify_image(
        image_path,
        ocr=ocr,
    )

    assert report.passed


def test_face_is_redacted_and_verification_passes(
    tmp_path,
):
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"

    Image.new(
        "RGB",
        (400, 300),
        color="white",
    ).save(input_path)

    face = Detection(
        detection_type=DetectionType.FACE,
        bbox=BoundingBox(
            x1=100,
            y1=70,
            x2=220,
            y2=220,
        ),
        confidence=0.96,
    )

    ocr = SequentialFakeOCRProvider(
        [
            [],
            [],
        ]
    )

    face_detector = (
        SequentialFakeFaceDetector(
            [
                [face],
                [],
            ]
        )
    )

    result = sanitize_and_verify_image(
        input_path=input_path,
        output_path=output_path,
        ocr=ocr,
        face_detector=face_detector,
    )

    assert len(
        result.applied_detections
    ) == 1

    assert (
        result.applied_detections[0]
        .detection_type
        == DetectionType.FACE
    )

    assert result.passed


def test_signature_is_redacted_and_verified(
    tmp_path,
):
    input_path = (
        tmp_path
        / "input.png"
    )

    output_path = (
        tmp_path
        / "output.png"
    )

    Image.new(
        "RGB",
        (500, 300),
        color="white",
    ).save(input_path)

    signature = Detection(
        detection_type=(
            DetectionType.SIGNATURE
        ),
        bbox=BoundingBox(
            x1=150,
            y1=150,
            x2=350,
            y2=220,
        ),
        confidence=0.92,
    )

    ocr = (
        SequentialFakeOCRProvider(
            [
                [],
                [],
            ]
        )
    )

    signature_detector = (
        SequentialFakeSignatureDetector(
            [
                [signature],
                [],
            ]
        )
    )

    result = (
        sanitize_and_verify_image(
            input_path=input_path,
            output_path=output_path,
            ocr=ocr,
            signature_detector=(
                signature_detector
            ),
        )
    )

    assert any(
        detection.detection_type
        == DetectionType.SIGNATURE
        for detection
        in result.applied_detections
    )

    assert result.passed