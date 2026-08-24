from __future__ import annotations

from pathlib import Path

from bidr_sanitizer.models import (
    TextDetection,
)
from bidr_sanitizer.recognizers.semantic.base import (
    SemanticPIIRecognizer,
)
from bidr_sanitizer.text.models import (
    TextSanitizationResult,
    TextVerificationReport,
)
from bidr_sanitizer.text_recognition import (
    detect_pii_in_text,
)


REDACTION_TOKEN = "[REDACTED]"


def _merge_overlapping_spans(
    detections: list[TextDetection],
) -> list[tuple[int, int]]:
    """
    Merge overlapping sensitive character spans.

    We only need physical spans here; the original typed detections
    are retained separately for audit counts.
    """

    if not detections:
        return []

    spans = sorted(
        (
            (
                detection.span.start,
                detection.span.end,
            )
            for detection in detections
        ),
        key=lambda item: (
            item[0],
            item[1],
        ),
    )

    merged: list[
        tuple[int, int]
    ] = []

    current_start, current_end = (
        spans[0]
    )

    for start, end in spans[1:]:
        if start <= current_end:
            current_end = max(
                current_end,
                end,
            )
            continue

        merged.append(
            (
                current_start,
                current_end,
            )
        )

        current_start = start
        current_end = end

    merged.append(
        (
            current_start,
            current_end,
        )
    )

    return merged


def redact_text(
    text: str,
    detections: list[
        TextDetection
    ],
) -> str:
    """
    Replace sensitive spans irreversibly.

    Replacement occurs from right to left so earlier character
    offsets remain valid.
    """

    spans = _merge_overlapping_spans(
        detections
    )

    output = text

    for start, end in reversed(
        spans
    ):
        output = (
            output[:start]
            + REDACTION_TOKEN
            + output[end:]
        )

    return output


def sanitize_text(
    text: str,
    *,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
    max_redaction_passes: int = 3,
) -> tuple[
    str,
    tuple[TextDetection, ...],
    TextVerificationReport,
    int,
]:
    if max_redaction_passes < 1:
        raise ValueError(
            "max_redaction_passes "
            "must be at least 1."
        )

    current_text = text

    all_detections: list[
        TextDetection
    ] = []

    redaction_passes = 0

    for _ in range(
        max_redaction_passes
    ):
        detections = (
            detect_pii_in_text(
                current_text,
                semantic_recognizer=(
                    semantic_recognizer
                ),
            )
        )

        if not detections:
            verification = (
                TextVerificationReport(
                    remaining_detections=()
                )
            )

            return (
                current_text,
                tuple(all_detections),
                verification,
                redaction_passes,
            )

        all_detections.extend(
            detections
        )

        current_text = redact_text(
            current_text,
            detections,
        )

        redaction_passes += 1

    remaining = detect_pii_in_text(
        current_text,
        semantic_recognizer=(
            semantic_recognizer
        ),
    )

    return (
        current_text,
        tuple(all_detections),
        TextVerificationReport(
            remaining_detections=tuple(
                remaining
            )
        ),
        redaction_passes,
    )


def sanitize_text_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
    max_redaction_passes: int = 3,
) -> TextSanitizationResult:

    input_path = Path(
        input_path
    ).resolve()

    output_path = Path(
        output_path
    ).resolve()

    if not input_path.exists():
        raise FileNotFoundError(
            input_path
        )

    if input_path.suffix.lower() != ".txt":
        raise ValueError(
            "Expected a .txt file."
        )

    if (
        input_path
        == output_path
    ):
        raise ValueError(
            "Input and output paths "
            "must be different."
        )

    text = input_path.read_text(
        encoding="utf-8-sig",
    )

    (
        sanitized_text,
        detections,
        verification,
        redaction_passes,
    ) = sanitize_text(
        text,
        semantic_recognizer=(
            semantic_recognizer
        ),
        max_redaction_passes=(
            max_redaction_passes
        ),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        sanitized_text,
        encoding="utf-8",
    )

    return TextSanitizationResult(
        output_path=output_path,
        applied_detections=(
            detections
        ),
        verification=verification,
        redaction_passes=(
            redaction_passes
        ),
    )