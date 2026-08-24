from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)

from bidr_sanitizer.image_io import read_image
from bidr_sanitizer.config import YUNET_MODEL_PATH
from bidr_sanitizer.model_check import (
    require_local_model,
)


SUPPORTED_ROTATIONS = (0, 90, 180, 270)


def build_expanded_face_bbox(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
    horizontal_margin_ratio: float = 0.25,
    vertical_margin_ratio: float = 0.30,
) -> BoundingBox:
    horizontal_margin = width * horizontal_margin_ratio
    vertical_margin = height * vertical_margin_ratio

    return BoundingBox(
        x1=max(
            0,
            math.floor(x - horizontal_margin),
        ),
        y1=max(
            0,
            math.floor(y - vertical_margin),
        ),
        x2=min(
            image_width,
            math.ceil(
                x + width + horizontal_margin
            ),
        ),
        y2=min(
            image_height,
            math.ceil(
                y + height + vertical_margin
            ),
        ),
    )


def rotate_bbox_back_to_original(
    bbox: BoundingBox,
    *,
    rotation: int,
    original_width: int,
    original_height: int,
) -> BoundingBox:
    """
    Map a bounding box detected in a rotated image back into the
    coordinate system of the original image.

    rotation describes the clockwise rotation applied before
    face detection.
    """

    if rotation not in SUPPORTED_ROTATIONS:
        raise ValueError(
            f"Unsupported rotation: {rotation}"
        )

    if rotation == 0:
        return bbox

    corners = [
        (bbox.x1, bbox.y1),
        (bbox.x2, bbox.y1),
        (bbox.x1, bbox.y2),
        (bbox.x2, bbox.y2),
    ]

    original_points: list[
        tuple[float, float]
    ] = []

    for x, y in corners:

        if rotation == 90:
            # Original -> rotated clockwise:
            # xr = H - y
            # yr = x
            #
            # Therefore inverse:
            # x = yr
            # y = H - xr
            original_x = y
            original_y = (
                original_height - x
            )

        elif rotation == 180:
            original_x = (
                original_width - x
            )
            original_y = (
                original_height - y
            )

        elif rotation == 270:
            # 270° clockwise == 90° CCW.
            #
            # Inverse:
            # x = W - yr
            # y = xr
            original_x = (
                original_width - y
            )
            original_y = x

        else:
            raise AssertionError(
                "Unexpected rotation."
            )

        original_points.append(
            (
                original_x,
                original_y,
            )
        )

    xs = [
        point[0]
        for point in original_points
    ]

    ys = [
        point[1]
        for point in original_points
    ]

    x1 = max(
        0,
        math.floor(min(xs)),
    )

    y1 = max(
        0,
        math.floor(min(ys)),
    )

    x2 = min(
        original_width,
        math.ceil(max(xs)),
    )

    y2 = min(
        original_height,
        math.ceil(max(ys)),
    )

    return BoundingBox(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
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


def merge_face_detections(
    detections: Iterable[Detection],
    *,
    iou_threshold: float = 0.35,
) -> list[Detection]:
    """
    Deduplicate the same physical face found at multiple rotations.

    For privacy, overlapping detections are merged using the union
    of their boxes rather than selecting the smaller box.
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
                    DetectionType.FACE
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


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: str | Path,
        *,
        confidence_threshold: float = 0.45,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        rotations: tuple[int, ...] = (
            0,
            90,
            180,
            270,
        ),
    ) -> None:
        if not (
            0.0
            <= confidence_threshold
            <= 1.0
        ):
            raise ValueError(
                "Confidence threshold must be "
                "between 0 and 1."
            )

        if not rotations:
            raise ValueError(
                "At least one rotation is required."
            )

        for rotation in rotations:
            if (
                rotation
                not in SUPPORTED_ROTATIONS
            ):
                raise ValueError(
                    f"Unsupported rotation: "
                    f"{rotation}"
                )

        self._model_path = Path(
            model_path
        ).resolve()

        if self._model_path == YUNET_MODEL_PATH.resolve():
            require_local_model(
                "yunet-face-detection",
                target_path=(
                    self._model_path.parent
                ),
                verify_hashes=False,
            )

        elif not self._model_path.exists():
            raise FileNotFoundError(
                self._model_path
            )

        self._confidence_threshold = (
            confidence_threshold
        )

        self._nms_threshold = (
            nms_threshold
        )

        self._top_k = top_k

        self._rotations = rotations

    def _rotate_image(
        self,
        image,
        rotation: int,
    ):
        import cv2

        if rotation == 0:
            return image

        if rotation == 90:
            return cv2.rotate(
                image,
                cv2.ROTATE_90_CLOCKWISE,
            )

        if rotation == 180:
            return cv2.rotate(
                image,
                cv2.ROTATE_180,
            )

        if rotation == 270:
            return cv2.rotate(
                image,
                cv2.ROTATE_90_COUNTERCLOCKWISE,
            )

        raise ValueError(
            f"Unsupported rotation: {rotation}"
        )

    def _detect_on_rotated_image(
        self,
        detector,
        image,
        *,
        rotation: int,
        original_width: int,
        original_height: int,
    ) -> list[Detection]:

        rotated = self._rotate_image(
            image,
            rotation,
        )

        rotated_height, rotated_width = (
            rotated.shape[:2]
        )

        detector.setInputSize(
            (
                rotated_width,
                rotated_height,
            )
        )

        _, faces = detector.detect(
            rotated
        )

        if faces is None:
            return []

        detections: list[Detection] = []

        for face in faces:
            x = float(face[0])
            y = float(face[1])
            width = float(face[2])
            height = float(face[3])
            confidence = float(face[14])

            # Expand in the orientation in which YuNet
            # actually detected the face.
            rotated_bbox = (
                build_expanded_face_bbox(
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    image_width=rotated_width,
                    image_height=rotated_height,
                )
            )

            original_bbox = (
                rotate_bbox_back_to_original(
                    rotated_bbox,
                    rotation=rotation,
                    original_width=(
                        original_width
                    ),
                    original_height=(
                        original_height
                    ),
                )
            )

            detections.append(
                Detection(
                    detection_type=(
                        DetectionType.FACE
                    ),
                    bbox=original_bbox,
                    confidence=confidence,
                )
            )

        return detections

    def detect(
        self,
        image_path: str | Path,
    ) -> list[Detection]:
        import cv2

        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(
                image_path
            )

        image = read_image(image_path)

        if image is None:
            raise ValueError(
                "OpenCV could not read image: "
                f"{image_path}"
            )

        original_height, original_width = (
            image.shape[:2]
        )

        detector = (
            cv2.FaceDetectorYN.create(
                model=str(
                    self._model_path
                ),
                config="",
                input_size=(
                    original_width,
                    original_height,
                ),
                score_threshold=(
                    self._confidence_threshold
                ),
                nms_threshold=(
                    self._nms_threshold
                ),
                top_k=self._top_k,
            )
        )

        all_detections: list[
            Detection
        ] = []

        for rotation in self._rotations:
            all_detections.extend(
                self._detect_on_rotated_image(
                    detector,
                    image,
                    rotation=rotation,
                    original_width=(
                        original_width
                    ),
                    original_height=(
                        original_height
                    ),
                )
            )

        return merge_face_detections(
            all_detections
        )
