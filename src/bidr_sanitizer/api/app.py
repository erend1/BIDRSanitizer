from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import secrets

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.trustedhost import TrustedHostMiddleware

from bidr_sanitizer.api.config import WebAPISettings
from bidr_sanitizer.api.schemas import (
    ExportRequest,
    HealthSchema,
    ImageSettingsSchema,
    ReviewSessionSchema,
    RevisePlanRequest,
)
from bidr_sanitizer.api.sessions import (
    AnalysisRuntimeUnavailableError,
    InvalidImageUploadError,
    PDFReviewLimitExceededError,
    ReviewSessionManager,
    ReviewSessionManagerClosedError,
    ReviewSessionNotFoundError,
    ReviewSessionStateError,
    UnsupportedUploadMediaTypeError,
    UploadTooLargeError,
)
from bidr_sanitizer.review.image_workflow import (
    PlanRevisionConflictError,
    PlanSourceMismatchError,
)


API_PREFIX = "/api/v1"
API_TOKEN_HEADER = "X-BIDR-API-Token"
LOGGER = logging.getLogger(__name__)


def _safe_error(detail: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _add_api_security_headers(request: Request, response: Response) -> Response:
    if request.url.path.startswith(API_PREFIX):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
    return response


def create_app(
    *,
    settings: WebAPISettings,
    service=None,
    workspace_root: str | Path | None = None,
) -> FastAPI:
    """Create one secured API process with a private review workspace."""

    if service is None:
        from bidr_sanitizer.service import BIDRSanitizerService

        service = BIDRSanitizerService()

    sessions = ReviewSessionManager(
        service=service,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
        max_pdf_pages=settings.max_pdf_pages,
        pdf_review_dpi=settings.pdf_review_dpi,
        workspace_root=workspace_root,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            sessions.close()
            close_service = getattr(service, "close", None)
            if callable(close_service):
                close_service()

    app = FastAPI(
        title="BIDR Sanitizer API",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.review_sessions = sessions

    @app.middleware("http")
    async def enforce_origin_and_security_headers(request: Request, call_next):
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if origin is not None and origin not in settings.allowed_origins:
            return _add_api_security_headers(
                request,
                _safe_error("Origin is not allowed.", 403),
            )
        if fetch_site == "cross-site":
            return _add_api_security_headers(
                request,
                _safe_error("Cross-site requests are not allowed.", 403),
            )

        try:
            response = await call_next(request)
        except Exception as error:
            LOGGER.error(
                "Unhandled BIDR API exception type=%s",
                type(error).__name__,
            )
            response = _safe_error("Internal server error.", 500)
        return _add_api_security_headers(request, response)

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.allowed_hosts),
    )

    launch_token_header = APIKeyHeader(
        name=API_TOKEN_HEADER,
        scheme_name="BIDRLaunchToken",
        description="Per-launch token supplied by the local application host.",
        auto_error=False,
    )

    def require_api_token(
        supplied_token: str | None = Security(launch_token_header),
    ) -> None:
        if supplied_token is None or not supplied_token.isascii():
            raise HTTPException(status_code=401, detail="API token is required.")

        if not secrets.compare_digest(
            supplied_token,
            settings.api_token,
        ):
            raise HTTPException(status_code=401, detail="API token is required.")

    @app.exception_handler(ReviewSessionNotFoundError)
    async def handle_missing_session(request: Request, error: Exception):
        return _safe_error("Review session was not found.", 404)

    @app.exception_handler(ReviewSessionStateError)
    async def handle_session_state(request: Request, error: Exception):
        return _safe_error("Review session is not ready for this operation.", 409)

    @app.exception_handler(ReviewSessionManagerClosedError)
    async def handle_closed_manager(request: Request, error: Exception):
        return _safe_error("Review service is unavailable.", 503)

    @app.exception_handler(UnsupportedUploadMediaTypeError)
    async def handle_media_type(request: Request, error: Exception):
        return _safe_error("Only PNG, JPEG, and PDF uploads are supported.", 415)

    @app.exception_handler(UploadTooLargeError)
    async def handle_large_upload(request: Request, error: Exception):
        return _safe_error("Upload exceeds the configured size limit.", 413)

    @app.exception_handler(InvalidImageUploadError)
    async def handle_invalid_image(request: Request, error: Exception):
        return _safe_error("The upload is not a valid PNG, JPEG, or PDF document.", 400)

    @app.exception_handler(PDFReviewLimitExceededError)
    async def handle_pdf_review_limit(request: Request, error: Exception):
        return _safe_error(str(error), 413)

    @app.exception_handler(AnalysisRuntimeUnavailableError)
    async def handle_analysis_runtime_unavailable(
        request: Request,
        error: Exception,
    ):
        return _safe_error(
            "Windows Application Control blocked a required local analysis "
            "component. The document was not analyzed.",
            503,
        )

    @app.exception_handler(PlanRevisionConflictError)
    async def handle_revision_conflict(request: Request, error: Exception):
        return _safe_error("Review plan revision conflict.", 409)

    @app.exception_handler(PlanSourceMismatchError)
    async def handle_source_mismatch(request: Request, error: Exception):
        return _safe_error("Review source no longer matches its plan.", 409)

    @app.get(
        f"{API_PREFIX}/health",
        response_model=HealthSchema,
        include_in_schema=False,
    )
    def health() -> HealthSchema:
        return HealthSchema(status="ok", api_version="v1")

    router = APIRouter(
        prefix=API_PREFIX,
        dependencies=[Depends(require_api_token)],
    )

    @router.get("/auth-check", status_code=204, include_in_schema=False)
    def auth_check() -> Response:
        return Response(status_code=204)

    @router.post(
        "/review-sessions",
        response_model=ReviewSessionSchema,
        status_code=201,
    )
    async def create_review_session(request: Request) -> ReviewSessionSchema:
        media_type = request.headers.get("content-type", "").split(";", 1)[0]
        media_type = media_type.strip().lower()

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError as error:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Content-Length header.",
                ) from error

            if declared_size < 0:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Content-Length header.",
                )
            if declared_size > settings.max_upload_bytes:
                raise UploadTooLargeError(
                    "Upload exceeds the configured size limit."
                )

        snapshot = await sessions.create_session(
            media_type=media_type,
            chunks=request.stream(),
        )
        return ReviewSessionSchema.from_snapshot(snapshot)

    @router.get(
        "/review-sessions/{session_id}",
        response_model=ReviewSessionSchema,
    )
    def get_review_session(session_id: str) -> ReviewSessionSchema:
        return ReviewSessionSchema.from_snapshot(sessions.get_session(session_id))

    @router.post(
        "/review-sessions/{session_id}/analysis",
        response_model=ReviewSessionSchema,
    )
    def analyze_review_session(
        session_id: str,
        request: ImageSettingsSchema,
    ) -> ReviewSessionSchema:
        snapshot = sessions.analyze_session(
            session_id,
            settings=request.to_domain(),
        )
        return ReviewSessionSchema.from_snapshot(snapshot)

    @router.patch(
        "/review-sessions/{session_id}/plan",
        response_model=ReviewSessionSchema,
    )
    def revise_review_plan(
        session_id: str,
        request: RevisePlanRequest,
    ) -> ReviewSessionSchema:
        try:
            snapshot = sessions.revise_session(
                session_id,
                expected_revision=request.expected_revision,
                decisions=[decision.to_domain() for decision in request.decisions],
                page_number=request.page_number,
                geometry_updates=[
                    update.to_domain() for update in request.geometry_updates
                ],
                manual_regions=[
                    region.to_domain() for region in request.manual_regions
                ],
            )
        except PlanRevisionConflictError:
            raise
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid review plan update.",
            ) from error
        return ReviewSessionSchema.from_snapshot(snapshot)

    @router.post(
        "/review-sessions/{session_id}/export",
        response_model=ReviewSessionSchema,
    )
    def export_review_session(
        session_id: str,
        request: ExportRequest,
    ) -> ReviewSessionSchema:
        snapshot = sessions.export_session(
            session_id,
            expected_revisions=request.to_revision_map(),
        )
        return ReviewSessionSchema.from_snapshot(snapshot)

    @router.get("/review-sessions/{session_id}/source")
    def get_review_source(session_id: str) -> Response:
        content, media_type = sessions.read_source(session_id)
        extension = (
            "png"
            if media_type == "image/png"
            else "jpg"
            if media_type == "image/jpeg"
            else "pdf"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="BIDR_SOURCE.{extension}"'
            },
        )

    @router.get("/review-sessions/{session_id}/pages/{page_number}/source")
    def get_review_page_source(session_id: str, page_number: int) -> Response:
        content, media_type = sessions.read_page_source(session_id, page_number)
        extension = "png" if media_type == "image/png" else "jpg"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": (
                    f'inline; filename="BIDR_SOURCE_PAGE_{page_number:04d}.{extension}"'
                )
            },
        )

    @router.get("/review-sessions/{session_id}/export")
    def get_review_export(session_id: str) -> Response:
        content, media_type, status = sessions.read_export(session_id)
        extension = (
            "png"
            if media_type == "image/png"
            else "jpg"
            if media_type == "image/jpeg"
            else "pdf"
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="BIDR_REVIEW_RESULT.{extension}"'
                ),
                "X-BIDR-Verification-Status": status.value,
            },
        )

    @router.delete(
        "/review-sessions/{session_id}",
        status_code=204,
        response_class=Response,
    )
    def delete_review_session(session_id: str) -> Response:
        sessions.delete_session(session_id)
        return Response(status_code=204)

    app.include_router(router)
    return app
