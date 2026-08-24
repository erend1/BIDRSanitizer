from __future__ import annotations

import numpy as np

from bidr_sanitizer.image_io import (
    read_image,
    write_image,
)


def test_image_io_supports_unicode_paths(
    tmp_path,
):
    directory = (
        tmp_path
        / "RUMELİ_kanıt_şğüöç"
    )

    directory.mkdir()

    path = (
        directory
        / "örnek_İ.png"
    )

    original = np.zeros(
        (
            32,
            48,
            3,
        ),
        dtype=np.uint8,
    )

    original[
        5:20,
        10:30,
    ] = 255

    write_image(
        path,
        original,
    )

    restored = read_image(
        path
    )

    assert path.exists()

    assert (
        restored.shape
        == original.shape
    )

    assert np.array_equal(
        restored,
        original,
    )