from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def read_image(
    path: str | Path,
) -> np.ndarray:
    path = Path(path)

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise OSError(
            f"Could not read image file: {path}"
        ) from exc

    encoded = np.frombuffer(
        data,
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        encoded,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            f"OpenCV could not decode image: {path}"
        )

    return image


def write_image(
    path: str | Path,
    image: np.ndarray,
) -> None:
    path = Path(path)

    extension = path.suffix.lower()

    if not extension:
        raise ValueError(
            f"Output image has no extension: {path}"
        )

    success, encoded = cv2.imencode(
        extension,
        image,
    )

    if not success:
        raise ValueError(
            f"OpenCV could not encode image: {path}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        path.write_bytes(
            encoded.tobytes()
        )
    except OSError as exc:
        raise OSError(
            f"Could not write image file: {path}"
        ) from exc