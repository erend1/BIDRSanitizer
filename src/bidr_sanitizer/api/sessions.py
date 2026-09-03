from __future__ import annotations

from collections.abc import AsyncIterable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
import math
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
from typing import Protocol
import warnings
from uuid import uuid4

from PIL import Image

from bidr_sanitizer.api.config import (
    DEFAULT_MAX_PDF_PAGES,
    DEFAULT_PDF_REVIEW_DPI,
)
from bidr_sanitizer.review.image_workflow import (
    PlanRevisionConflictError,
    revise_image_review_plan,
)
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewDecision,
    ReviewGeometryUpdate,
    ReviewedImageExportResult,
    ReviewedOutputStatus,
)
from bidr_sanitizer.redaction import ImageOutputTransform


SUPPORTED_UPLOADS = {
    "image/png": ("image", "PNG", ".png"),
    "image/jpeg": ("image", "JPEG", ".jpg"),
    "application/pdf": ("pdf", None, ".pdf"),
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


class PDFReviewLimitExceededError(ReviewSessionError):
    """The PDF is valid but exceeds a configured review resource limit."""


class InvalidImageUploadError(ReviewSessionError):
    """The uploaded image or PDF cannot be safely used for review."""


class AnalysisRuntimeUnavailableError(ReviewSessionError):
    """A required local analysis runtime component cannot be loaded."""


def _is_windows_application_control_block(error: BaseException) -> bool:
    """Recognize the bounded OS loader error without exposing its file path."""

    current: BaseException | None = error
    for _ in range(6):
        if current is None:
            break
        message = str(current).casefold()
        blocked = "blocked" in message or "engelledi" in message
        application_control = (
            "application control" in message or "uygulama denetimi" in message
        )
        if blocked and application_control:
            return True
        current = current.__cause__ or current.__context__
    return False


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
        *,
        output_transform: ImageOutputTransform | None = None,
    ) -> ReviewedImageExportResult:
        ...


@dataclass(frozen=True, slots=True)
class ReviewPageSnapshot:
    page_number: int
    image_width: int
    image_height: int
    plan: ImageReviewPlan | None
    export_result: ReviewedImageExportResult | None


@dataclass(frozen=True, slots=True)
class ReviewedDocumentExportResult:
    output_path: Path
    media_type: str
    pages: tuple[ReviewedImageExportResult, ...]
    text_layer_empty: bool | None = None

    @property
    def detectors_clear(self) -> bool:
        return all(page.detectors_clear for page in self.pages)

    @property
    def status(self) -> ReviewedOutputStatus:
        if not self.detectors_clear or self.text_layer_empty is False:
            return ReviewedOutputStatus.REVIEW_REQUIRED

        if any(
            page.status is ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES
            for page in self.pages
        ):
            return ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES

        return ReviewedOutputStatus.PASSED

    @property
    def passed(self) -> bool:
        return self.status is ReviewedOutputStatus.PASSED


@dataclass(frozen=True, slots=True)
class ReviewSessionSnapshot:
    session_id: str
    state: ReviewSessionState
    media_type: str
    pages: tuple[ReviewPageSnapshot, ...]
    export_result: ReviewedDocumentExportResult | None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    # Compatibility conveniences for the original one-image API consumers.
    @property
    def image_width(self) -> int:
        return self.pages[0].image_width

    @property
    def image_height(self) -> int:
        return self.pages[0].image_height

    @property
    def plan(self) -> ImageReviewPlan | None:
        return self.pages[0].plan if len(self.pages) == 1 else None


@dataclass(slots=True)
class _ReviewPageRecord:
    page_number: int
    source_path: Path
    image_width: int
    image_height: int
    width_pt: float
    height_pt: float
    plan: ImageReviewPlan | None = None
    export_result: ReviewedImageExportResult | None = None


@dataclass(slots=True)
class _ReviewSessionRecord:
    session_id: str
    directory: Path
    source_path: Path
    export_path: Path
    media_type: str
    pages: list[_ReviewPageRecord]
    state: ReviewSessionState = ReviewSessionState.UPLOADED
    export_result: ReviewedDocumentExportResult | None = None


class ReviewSessionManager:
    """Own private source, page-preview, plan, and export state for the API."""

    def __init__(
        self,
        *,
        service: ReviewServiceProvider,
        max_upload_bytes: int,
        max_image_pixels: int,
        max_pdf_pages: int = DEFAULT_MAX_PDF_PAGES,
        pdf_review_dpi: int = DEFAULT_PDF_REVIEW_DPI,
        workspace_root: str | Path | None = None,
    ) -> None:
        self._service = service
        self._max_upload_bytes = max_upload_bytes
        self._max_image_pixels = max_image_pixels
        self._max_pdf_pages = max_pdf_pages
        self._pdf_review_dpi = pdf_review_dpi
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
    def _page(record: _ReviewSessionRecord, page_number: int) -> _ReviewPageRecord:
        if page_number < 1 or page_number > len(record.pages):
            raise ReviewSessionNotFoundError("Review page was not found.")
        return record.pages[page_number - 1]

    @staticmethod
    def _snapshot(record: _ReviewSessionRecord) -> ReviewSessionSnapshot:
        return ReviewSessionSnapshot(
            session_id=record.session_id,
            state=record.state,
            media_type=record.media_type,
            pages=tuple(
                ReviewPageSnapshot(
                    page_number=page.page_number,
                    image_width=page.image_width,
                    image_height=page.image_height,
                    plan=page.plan,
                    export_result=page.export_result,
                )
                for page in record.pages
            ),
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
        for candidate in record.directory.glob("reviewed_page_*.png"):
            candidate.unlink(missing_ok=True)
        for page in record.pages:
            page.export_result = None
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

    def _render_uploaded_pdf(
        self,
        path: Path,
        session_directory: Path,
    ) -> list[_ReviewPageRecord]:
        import pypdfium2 as pdfium

        pages: list[_ReviewPageRecord] = []
        try:
            document = pdfium.PdfDocument(str(path))
            try:
                document.init_forms()
                page_count = len(document)
                if page_count < 1:
                    raise InvalidImageUploadError("The PDF contains no pages.")
                if page_count > self._max_pdf_pages:
                    raise PDFReviewLimitExceededError(
                        f"The PDF has {page_count} pages; the configured maximum is "
                        f"{self._max_pdf_pages}."
                    )

                for page_index in range(page_count):
                    page = document[page_index]
                    try:
                        width_pt, height_pt = page.get_size()
                        pixel_width = math.ceil(width_pt * self._pdf_review_dpi / 72.0)
                        pixel_height = math.ceil(height_pt * self._pdf_review_dpi / 72.0)
                        if pixel_width * pixel_height > self._max_image_pixels:
                            raise PDFReviewLimitExceededError(
                                "A rendered PDF page exceeds the configured pixel limit."
                            )

                        page_path = session_directory / (
                            f"source_page_{page_index + 1:04d}.png"
                        )
                    finally:
                        page.close()

                    pages.append(
                        _ReviewPageRecord(
                            page_number=page_index + 1,
                            source_path=page_path,
                            image_width=pixel_width,
                            image_height=pixel_height,
                            width_pt=float(width_pt),
                            height_pt=float(height_pt),
                        )
                    )
            finally:
                document.close()
        except (InvalidImageUploadError, PDFReviewLimitExceededError):
            raise
        except Exception as error:
            raise InvalidImageUploadError(
                "The upload is not a readable, unencrypted PDF."
            ) from error

        return pages

    def _ensure_pages_rendered(
        self,
        record: _ReviewSessionRecord,
        pages: Iterable[_ReviewPageRecord],
    ) -> None:
        if record.media_type != "application/pdf":
            return

        missing_pages = [page for page in pages if not page.source_path.exists()]
        if not missing_pages:
            return

        import pypdfium2 as pdfium

        from bidr_sanitizer.pdf.sanitizer import _render_page_to_png

        created_paths: list[Path] = []
        try:
            document = pdfium.PdfDocument(str(record.source_path))
            try:
                document.init_forms()
                for page_record in missing_pages:
                    page = document[page_record.page_number - 1]
                    try:
                        width_pt, height_pt = _render_page_to_png(
                            page,
                            page_record.source_path,
                            dpi=self._pdf_review_dpi,
                        )
                        created_paths.append(page_record.source_path)
                    finally:
                        page.close()

                    with Image.open(page_record.source_path) as rendered:
                        rendered_width, rendered_height = rendered.size
                        rendered.verify()

                    if (
                        rendered_width != page_record.image_width
                        or rendered_height != page_record.image_height
                        or not math.isclose(
                            width_pt,
                            page_record.width_pt,
                            abs_tol=1e-6,
                        )
                        or not math.isclose(
                            height_pt,
                            page_record.height_pt,
                            abs_tol=1e-6,
                        )
                    ):
                        raise InvalidImageUploadError(
                            "A rendered PDF page does not match its inspected geometry."
                        )
            finally:
                document.close()
        except BaseException:
            for created_path in created_paths:
                created_path.unlink(missing_ok=True)
            raise

    async def create_session(
        self,
        *,
        media_type: str,
        chunks: AsyncIterable[bytes],
    ) -> ReviewSessionSnapshot:
        upload = SUPPORTED_UPLOADS.get(media_type)
        if upload is None:
            raise UnsupportedUploadMediaTypeError(
                "Only image/png, image/jpeg, and application/pdf uploads are supported."
            )

        with self._state_lock:
            self._ensure_open()
            session_id = uuid4().hex

        document_kind, expected_format, extension = upload
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
                raise InvalidImageUploadError("The uploaded document is empty.")

            if document_kind == "image":
                assert expected_format is not None
                width, height = self._validate_uploaded_image(
                    source_path,
                    expected_format=expected_format,
                )
                pages = [
                    _ReviewPageRecord(
                        page_number=1,
                        source_path=source_path,
                        image_width=width,
                        image_height=height,
                        width_pt=float(width),
                        height_pt=float(height),
                    )
                ]
            else:
                pages = self._render_uploaded_pdf(source_path, session_directory)

            record = _ReviewSessionRecord(
                session_id=session_id,
                directory=session_directory,
                source_path=source_path,
                export_path=export_path,
                media_type=media_type,
                pages=pages,
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

            try:
                self._ensure_pages_rendered(record, record.pages)
                plans = [
                    self._service.analyze_image_for_review(
                        page.source_path,
                        settings=settings,
                    )
                    for page in record.pages
                ]
            except (ImportError, OSError) as error:
                if _is_windows_application_control_block(error):
                    raise AnalysisRuntimeUnavailableError(
                        "Windows Application Control blocked a required local "
                        "analysis component."
                    ) from error
                raise

            with self._state_lock:
                self._discard_export(record)
                for page, plan in zip(record.pages, plans, strict=True):
                    page.plan = plan
                record.state = ReviewSessionState.ANALYZED
                return self._snapshot(record)

    def revise_session(
        self,
        session_id: str,
        *,
        page_number: int = 1,
        expected_revision: int,
        decisions: Iterable[ReviewDecision],
        geometry_updates: Iterable[ReviewGeometryUpdate] = (),
        manual_regions: Iterable[ManualRegionRequest],
    ) -> ReviewSessionSnapshot:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            page = self._page(record, page_number)
            if page.plan is None:
                raise ReviewSessionStateError(
                    "The review session has not been analyzed."
                )

            revised = revise_image_review_plan(
                page.plan,
                expected_revision=expected_revision,
                decisions=decisions,
                geometry_updates=geometry_updates,
                manual_regions=manual_regions,
            )
            self._discard_export(record)
            page.plan = revised
            record.state = ReviewSessionState.ANALYZED
            return self._snapshot(record)

    def export_session(
        self,
        session_id: str,
        *,
        expected_revisions: Mapping[int, int],
    ) -> ReviewSessionSnapshot:
        with self._workflow_lock:
            with self._state_lock:
                self._ensure_open()
                record = self._record(session_id)
                expected_pages = {page.page_number for page in record.pages}
                if set(expected_revisions) != expected_pages:
                    raise PlanRevisionConflictError(
                        "Expected revisions must include every review page."
                    )
                for page in record.pages:
                    if page.plan is None:
                        raise ReviewSessionStateError(
                            "The review session has not been analyzed."
                        )
                    if expected_revisions[page.page_number] != page.plan.revision:
                        raise PlanRevisionConflictError(
                            "A PDF page plan revision is stale."
                        )

            page_results: list[ReviewedImageExportResult] = []
            if record.media_type == "application/pdf":
                from bidr_sanitizer.pdf.sanitizer import (
                    _build_image_only_pdf,
                    compact_redacted_pdf_page,
                    pdf_has_extractable_text,
                )

                safe_pages: list[tuple[Path, float, float]] = []
                candidate_pdf = record.directory / ".reviewed_candidate.pdf"
                candidate_pdf.unlink(missing_ok=True)
                try:
                    for page in record.pages:
                        assert page.plan is not None
                        safe_path = record.directory / (
                            f"reviewed_page_{page.page_number:04d}.png"
                        )
                        result = self._service.export_reviewed_image(
                            page.source_path,
                            safe_path,
                            page.plan,
                            output_transform=compact_redacted_pdf_page,
                        )
                        if result.output_path.resolve() != safe_path.resolve():
                            raise RuntimeError(
                                "The sanitizer returned an unexpected page output path."
                            )
                        page_results.append(result)
                        safe_pages.append((safe_path, page.width_pt, page.height_pt))

                    _build_image_only_pdf(safe_pages, candidate_pdf)
                    if pdf_has_extractable_text(candidate_pdf):
                        raise RuntimeError(
                            "Reviewed PDF unexpectedly contains extractable text."
                        )
                    os.replace(candidate_pdf, record.export_path)
                except BaseException:
                    candidate_pdf.unlink(missing_ok=True)
                    raise
                text_layer_empty: bool | None = True
            else:
                page = record.pages[0]
                assert page.plan is not None
                result = self._service.export_reviewed_image(
                    page.source_path,
                    record.export_path,
                    page.plan,
                )
                if result.output_path.resolve() != record.export_path.resolve():
                    raise RuntimeError("The sanitizer returned an unexpected output path.")
                page_results.append(result)
                text_layer_empty = None

            document_result = ReviewedDocumentExportResult(
                output_path=record.export_path,
                media_type=record.media_type,
                pages=tuple(page_results),
                text_layer_empty=text_layer_empty,
            )

            with self._state_lock:
                for page, result in zip(record.pages, page_results, strict=True):
                    page.export_result = result
                record.export_result = document_result
                record.state = ReviewSessionState.EXPORTED
                return self._snapshot(record)

    def read_source(self, session_id: str) -> tuple[bytes, str]:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            return record.source_path.read_bytes(), record.media_type

    def read_page_source(self, session_id: str, page_number: int) -> tuple[bytes, str]:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            page = self._page(record, page_number)
            self._ensure_pages_rendered(record, (page,))
            media_type = record.media_type if record.media_type != "application/pdf" else "image/png"
            return page.source_path.read_bytes(), media_type

    def read_export(
        self,
        session_id: str,
    ) -> tuple[bytes, str, ReviewedOutputStatus]:
        with self._workflow_lock, self._state_lock:
            self._ensure_open()
            record = self._record(session_id)
            if record.export_result is None or not record.export_path.exists():
                raise ReviewSessionStateError(
                    "The review session does not have an exported document."
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
