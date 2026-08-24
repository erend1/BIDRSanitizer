from __future__ import annotations

from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from typing import Protocol
import warnings
from uuid import uuid4

from PIL import Image

from bidr_sanitizer.review.image_workflow import (
    PlanRevisionConflictError,
    revise_image_review_plan,
)
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewDecision,
    ReviewedImageExportResult,
    ReviewedOutputStatus,
)


SUPPORTED_UPLOADS = {
    "image/png": ("PNG", ".png"),
    "image/jpeg": ("JPEG", ".jpg"),
}


class ReviewSessionState(str, Enum):
    UPLOADED = "uploaded"
    ANALYZED = "analyzed"
    EXPORTED = "exported"


class ReviewSessionError(RuntimeError):
    """Base class for safe review-session failures."""


class ReviewSessionNotFoundError(ReviewSessionError):
    pass


class ReviewSessionStateError(ReviewSessionError):
    pass


class ReviewSessionManagerClosedError(ReviewSessionError):
    pass


class UnsupportedUploadMediaTypeError(ReviewSessionError):
    pass


class UploadTooLargeError(ReviewSessionError):
    pass


class InvalidImageUploadError(ReviewSessionError):
    pass


class ReviewServiceProvider(Protocol):
    def analyze_image_for_review(
        self,
        input_path: str | Path,
        *,
        settings: ImageSanitizerSettings | None = None,
    ) -> ImageReviewPlan:
        ...

    def export_reviewed_image(
        self,
        input_path: str | Path,
        output_path: str | Path,
        plan: ImageReviewPlan,
    ) -> ReviewedImageExportResult:
        ...


@dataclass(frozen=True, slots=True)
class ReviewSessionSnapshot:
    session_id: str
    state: ReviewSessionState
    media_type: str
    image_width: int
    image_height: int
    plan: ImageReviewPlan | None
    export_result: ReviewedImageExportResult | None


@dataclass(slots=True)
class _ReviewSessionRecord:
    session_id: str
    directory: Path
    source_path: Path
    export_path: Path
    media_type: str
    image_width: int
    image_height: int
    state: ReviewSessionState = ReviewSessionState.UPLOADED
    plan: ImageReviewPlan | None = None
    export_result: ReviewedImageExportResult | None = None


class ReviewSessionManager:
    """Own private source/preview state for the synchronous review API."""

    def __init__(
        self,
        *,
        service: ReviewServiceProvider,
        max_upload_bytes: int,
        max_image_pixels: int,
        workspace_root: str | Path | None = None,
    ) -> None:
        self._service = service
        self._max_upload_bytes = max_upload_bytes
        self._max_image_pixels = max_image_pixels
        self._state_lock = RLock()
        self._workflow_lock = RLock()
        self._records: dict[str, _ReviewSessionRecord] = {}
        self._closed = False

        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        if workspace_root is None:
            self._temporary_directory = tempfile.TemporaryDirectory(
                prefix="bidr_review_sessions_"
            )
            root = Path(self._temporary_directory.name)
        else:
            root = Path(workspace_root)
            root.mkdir(parents=True, exist_ok=True)

        self._workspace_root = root.resolve()
        os.chmod(self._workspace_root, 0o700)

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    def _ensure_open(self) -> None:
        if self._closed:
            raise ReviewSessionManagerClosedError(
                "The review-session manager is closed."
            )

    def _record(self, session_id: str) -> _ReviewSessionRecord:
        record = self._records.get(session_id)
        if record is None:
            raise ReviewSessionNotFoundError("Review session was not found.")
        return record

    @staticmethod
    def _snapshot(record: _ReviewSessionRecord) -> ReviewSessionSnapshot:
        return ReviewSessionSnapshot(
            session_id=record.session_id,
            state=record.state,
            media_type=record.media_type,
            image_width=record.image_width,
            image_height=record.image_height,
            plan=record.plan,
            export_result=record.export_result,
        )

    def _validate_session_directory(self, directory: Path) -> None:
        if directory.parent.resolve() != self._workspace_root:
            raise RuntimeError("Refusing to remove a path outside the workspace.")

    def _remove_session_directory(self, directory: Path) -> None:
        self._validate_session_directory(directory)

        if directory.is_symlink():
            directory.unlink(missing_ok=True)
            return

        is_junction = getattr(directory, "is_junction", lambda: False)
        if is_junction():
            os.rmdir(directory)
            return

        if directory.exists():
            shutil.rmtree(directory)

    def _discard_export(self, record: _ReviewSessionRecord) -> None:
        if record.export_path.parent.resolve() != record.directory.resolve():
            raise RuntimeError("Invalid review export path.")

        record.export_path.unlink(missing_ok=True)
        record.export_result = None

    def _validate_uploaded_image(
        self,
        path: Path,
        *,
        expected_format: str,
    ) -> tuple[int, int]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    width, height = image.size
                    if width * height > self._max_image_pixels:
                        raise InvalidImageUploadError(
                            "Image dimensions exceed the configured limit."
                        )

                    if image.format != expected_format:
                        raise InvalidImageUploadError(
                            "Image bytes do not match the declared media type."
                        )

                    image.verify()
        except InvalidImageUploadError:
            raise
        except (
            OSError,
            SyntaxError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as error:
            raise InvalidImageUploadError("The upload is not a valid image.") from error

        return width, height

    async def create_session(
        self,
        *,
        media_type: str,
        chunks: AsyncIterable[bytes],
    ) -> ReviewSessionSnapshot:
        upload = SUPPORTED_UPLOADS.get(media_type)
        if upload is None:
            raise UnsupportedUploadMediaTypeError(
                "Only image/png and image/jpeg uploads are supported."
            )

        with self._state_lock:
            self._ensure_open()
            session_id = uuid4().hex

        expected_format, extension = upload
        session_directory = self._workspace_root / session_id
        self._validate_session_directory(session_directory)
        session_directory.mkdir(mode=0o700)
        source_path = session_directory / f"source{extension}"
        export_path = session_directory / f"reviewed{extension}"

        try:
            size = 0
            with source_path.open("xb") as destination:
                async for chunk in chunks:
                    if not chunk:
                        continue

                    size += len(chunk)
                    if size > self._max_upload_bytes:
                        raise UploadTooLargeError(
                            "Upload exceeds the configured size limit."
                        )
                    destination.write(chunk)

            if size == 0:
                raise InvalidImageUploadError("The uploaded image is empty.")

            width, height = self._validate_uploaded_image(
                source_path,
                expected_format=expected_format,
            )

            record = _ReviewSessionRecord(
                session_id=session_id,
                directory=session_directory,
                source_path=source_path,
                export_path=export_path,
                media_type=media_type,
                image_width=width,
                image_height=height,
            )

            with self._state_lock:
                self._ensure_open()
                self._records[session_id] = record

            return self._snapshot(record)
        except BaseException:
            self._remove_session_directory(session_directory)
            raise

    def get_session(self, session_id: str) -> ReviewSessionSnapshot:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            return self._snapshot(self._record(session_id))

    def analyze_session(
        self,
        session_id: str,
        *,
        settings: ImageSanitizerSettings,
    ) -> ReviewSessionSnapshot:
        with self._workflow_lock:
            with self._state_lock:
                self._ensure_open()
                record = self._record(session_id)

            plan = self._service.analyze_image_for_review(
                record.source_path,
                settings=settings,
            )

            with self._state_lock:
                self._discard_export(record)
                record.plan = plan
                record.state = ReviewSessionState.ANALYZED
                return self._snapshot(record)

    def revise_session(
        self,
        session_id: str,
        *,
        expected_revision: int,
        decisions: Iterable[ReviewDecision],
        manual_regions: Iterable[ManualRegionRequest],
    ) -> ReviewSessionSnapshot:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            if record.plan is None:
                raise ReviewSessionStateError(
                    "The review session has not been analyzed."
                )

            revised = revise_image_review_plan(
                record.plan,
                expected_revision=expected_revision,
                decisions=decisions,
                manual_regions=manual_regions,
            )
            self._discard_export(record)
            record.plan = revised
            record.state = ReviewSessionState.ANALYZED
            return self._snapshot(record)

    def export_session(
        self,
        session_id: str,
        *,
        expected_revision: int,
    ) -> ReviewSessionSnapshot:
        with self._workflow_lock:
            with self._state_lock:
                self._ensure_open()
                record = self._record(session_id)
                plan = record.plan

            if plan is None:
                raise ReviewSessionStateError(
                    "The review session has not been analyzed."
                )

            if expected_revision != plan.revision:
                raise PlanRevisionConflictError(
                    f"Expected plan revision {expected_revision}, current revision is "
                    f"{plan.revision}."
                )

            result = self._service.export_reviewed_image(
                record.source_path,
                record.export_path,
                plan,
            )
            if result.output_path.resolve() != record.export_path.resolve():
                raise RuntimeError("The sanitizer returned an unexpected output path.")

            with self._state_lock:
                record.export_result = result
                record.state = ReviewSessionState.EXPORTED
                return self._snapshot(record)

    def read_source(self, session_id: str) -> tuple[bytes, str]:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            return record.source_path.read_bytes(), record.media_type

    def read_export(
        self,
        session_id: str,
    ) -> tuple[bytes, str, ReviewedOutputStatus]:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            if record.export_result is None or not record.export_path.exists():
                raise ReviewSessionStateError(
                    "The review session does not have an exported image."
                )
            return (
                record.export_path.read_bytes(),
                record.media_type,
                record.export_result.status,
            )

    def delete_session(self, session_id: str) -> None:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            self._remove_session_directory(record.directory)
            del self._records[session_id]

    def close(self) -> None:
        with self._workflow_lock, self._state_lock:
            if self._closed:
                return

            records = tuple(self._records.values())
            for record in records:
                self._remove_session_directory(record.directory)
            self._records.clear()
            self._closed = True

            if self._temporary_directory is not None:
                self._temporary_directory.cleanup()
