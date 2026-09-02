from __future__ import annotations

import subprocess
import sys

from bidr_sanitizer.service import BIDRSanitizerService


def test_service_import_does_not_load_pdf_runtime():
    code = """
import sys
import bidr_sanitizer.service

if "pypdfium2" in sys.modules:
    raise SystemExit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )


def test_service_import_is_runtime_lazy():
    code = """
import sys
import bidr_sanitizer.service

forbidden = (
    "pypdfium2",
    "paddleocr",
    "gliner",
    "torch",
    "fastapi",
)

loaded = [
    name
    for name in forbidden
    if name in sys.modules
]

if loaded:
    print(",".join(loaded))
    raise SystemExit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Heavy runtime dependencies were loaded: "
        + result.stdout
        + result.stderr
    )


def test_web_api_import_does_not_initialize_ml_runtimes():
    code = """
import sys
import bidr_sanitizer.api

forbidden = (
    "paddleocr",
    "pypdfium2",
    "gliner",
    "torch",
)

loaded = [
    name
    for name in forbidden
    if name in sys.modules
]

if loaded:
    print(",".join(loaded))
    raise SystemExit(1)
"""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "API import initialized heavy runtime dependencies: "
        + result.stdout
        + result.stderr
    )


def test_service_close_releases_initialized_image_runtime():
    calls = []

    class FakeImageSanitizer:
        def close(self):
            calls.append("close")

    service = BIDRSanitizerService()
    service._image_sanitizer = FakeImageSanitizer()

    service.close()

    assert calls == ["close"]
