from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from reportlab.pdfgen.canvas import Canvas

from bidr_sanitizer.api import WebAPISettings, create_app
from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.review import (
    ImageSanitizerSettings,
    analyze_image_for_review,
    export_reviewed_image,
)


API_TOKEN = "synthetic-api-token-00000000000000000000"
ALLOWED_ORIGIN = "http://testserver"


class EmptyOCR:
    def recognize(self, image_path):
        return []


class StaticDetector:
    def __init__(self, detections):
        self._detections = list(detections)

    def detect(self, image_path):
        return list(self._detections)


class FakeReviewService:
    def __init__(self) -> None:
        self.analysis_paths: list[Path] = []
        self.export_paths: list[tuple[Path, Path]] = []

    def analyze_image_for_review(
        self,
        input_path,
        *,
        settings: ImageSanitizerSettings | None = None,
    ):
        input_path = Path(input_path)
        self.analysis_paths.append(input_path)
        face = Detection(
            detection_type=DetectionType.FACE,
            bbox=BoundingBox(10, 10, 30, 30),
            confidence=0.9,
        )
        return analyze_image_for_review(
            input_path,
            ocr=EmptyOCR(),
            face_detector=StaticDetector([face]),
            settings=settings,
        )

    def export_reviewed_image(
        self,
        input_path,
        output_path,
        plan,
        *,
        output_transform=None,
    ):
        input_path = Path(input_path)
        output_path = Path(output_path)
        self.export_paths.append((input_path, output_path))
        return export_reviewed_image(
            input_path,
            output_path,
            plan,
            ocr=EmptyOCR(),
            face_detector=StaticDetector([]),
            output_transform=output_transform,
        )


class FailingAnalysisService(FakeReviewService):
    def analyze_image_for_review(self, input_path, *, settings=None):
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR_VALUE")


class ApplicationControlBlockedService(FakeReviewService):
    def analyze_image_for_review(self, input_path, *, settings=None):
        raise ImportError(
            "DLL load failed while importing private_component: "
            "Uygulama Denetimi ilkesi bu dosyayı engelledi."
        )


class ClosableReviewService(FakeReviewService):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _png_bytes(
    *,
    size: tuple[int, int] = (100, 100),
    color: str = "white",
) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_bytes(*, size: tuple[int, int] = (100, 100)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color="white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _pdf_bytes(*, page_count: int = 2) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(144, 144))
    for page_number in range(1, page_count + 1):
        canvas.drawString(20, 100, f"Synthetic page {page_number}")
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _settings(**overrides) -> WebAPISettings:
    values = {
        "api_token": API_TOKEN,
        "allowed_hosts": ("testserver",),
        "allowed_origins": (ALLOWED_ORIGIN,),
        "max_upload_bytes": 1024 * 1024,
        "max_image_pixels": 1_000_000,
    }
    values.update(overrides)
    return WebAPISettings(**values)


def _authorized_headers(*, media_type: str | None = None) -> dict[str, str]:
    headers = {
        "X-BIDR-API-Token": API_TOKEN,
        "Origin": ALLOWED_ORIGIN,
    }
    if media_type is not None:
        headers["Content-Type"] = media_type
    return headers


def _create_client(tmp_path, *, settings=None, service=None):
    service = service or FakeReviewService()
    app = create_app(
        settings=settings or _settings(),
        service=service,
        workspace_root=tmp_path / "sessions",
    )
    return TestClient(app), app, service


def _upload_png(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/review-sessions",
        content=_png_bytes(),
        headers=_authorized_headers(media_type="image/png"),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_web_api_settings_hide_token_and_validate_security_values():
    settings = _settings()

    assert API_TOKEN not in repr(settings)

    with pytest.raises(ValueError, match="at least 32"):
        _settings(api_token="too-short")

    with pytest.raises(ValueError, match="ASCII"):
        _settings(api_token="ş" * 32)

    with pytest.raises(ValueError, match="complete HTTP"):
        _settings(allowed_origins=("javascript:alert(1)",))

    with pytest.raises(ValueError, match="positive integer"):
        _settings(max_upload_bytes=0)


def test_api_lifespan_closes_the_analysis_service(tmp_path):
    service = ClosableReviewService()
    client, _, _ = _create_client(tmp_path, service=service)

    with client:
        assert client.get("/api/v1/health").status_code == 200

    assert service.closed is True


def test_api_requires_token_and_rejects_cross_origin_and_untrusted_host(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        missing_token = client.post(
            "/api/v1/review-sessions",
            content=_png_bytes(),
            headers={"Content-Type": "image/png", "Origin": ALLOWED_ORIGIN},
        )
        assert missing_token.status_code == 401

        non_ascii_token = client.get(
            "/api/v1/review-sessions/unknown",
            headers=[(b"X-BIDR-API-Token", b"\xff" * 32)],
        )
        assert non_ascii_token.status_code == 401

        wrong_origin = client.post(
            "/api/v1/review-sessions",
            content=_png_bytes(),
            headers={
                "Content-Type": "image/png",
                "Origin": "https://attacker.example",
                "X-BIDR-API-Token": API_TOKEN,
            },
        )
        assert wrong_origin.status_code == 403
        assert wrong_origin.headers["cache-control"] == "no-store, max-age=0"

        cross_site = client.get(
            "/api/v1/health",
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert cross_site.status_code == 403

        untrusted_host = client.get(
            "/api/v1/health",
            headers={"Host": "attacker.example"},
        )
        assert untrusted_host.status_code == 400


def test_api_disables_remote_asset_docs_and_sets_privacy_headers(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        health = client.get(
            "/api/v1/health",
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "api_version": "v1"}
        assert health.headers["cache-control"] == "no-store, max-age=0"
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["cross-origin-resource-policy"] == "same-origin"
        assert "access-control-allow-origin" not in health.headers

        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404

        build_schema = app.openapi()
        assert "/api/v1/review-sessions" in build_schema["paths"]
        assert build_schema["components"]["securitySchemes"]["BIDRLaunchToken"] == {
            "type": "apiKey",
            "description": (
                "Per-launch token supplied by the local application host."
            ),
            "in": "header",
            "name": "X-BIDR-API-Token",
        }
        assert build_schema["paths"]["/api/v1/review-sessions"]["post"][
            "security"
        ] == [{"BIDRLaunchToken": []}]


def test_auth_check_rejects_stale_tokens_and_accepts_current_token(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        missing = client.get(
            "/api/v1/auth-check",
            headers={"Origin": ALLOWED_ORIGIN},
        )
        stale = client.get(
            "/api/v1/auth-check",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "X-BIDR-API-Token": "stale-token-000000000000000000000000",
            },
        )
        current = client.get(
            "/api/v1/auth-check",
            headers=_authorized_headers(),
        )

        assert missing.status_code == 401
        assert stale.status_code == 401
        assert current.status_code == 204
        assert current.content == b""
        assert current.headers["cache-control"] == "no-store, max-age=0"


@pytest.mark.parametrize(
    ("content", "media_type", "expected_status"),
    [
        (b"", "image/png", 400),
        (b"not an image", "image/png", 400),
        (_png_bytes(), "image/jpeg", 400),
        (_png_bytes(), "application/pdf", 400),
    ],
    ids=("empty", "invalid", "mismatched", "unsupported"),
)
def test_upload_rejects_empty_invalid_mismatched_and_unsupported_content(
    tmp_path,
    content,
    media_type,
    expected_status,
):
    client, app, service = _create_client(tmp_path)
    with client:
        response = client.post(
            "/api/v1/review-sessions",
            content=content,
            headers=_authorized_headers(media_type=media_type),
        )
        assert response.status_code == expected_status
        assert list((tmp_path / "sessions").iterdir()) == []


def test_upload_enforces_byte_and_pixel_limits(tmp_path):
    image = _png_bytes(size=(20, 20))

    byte_client, app, service = _create_client(
        tmp_path / "bytes",
        settings=_settings(max_upload_bytes=len(image) - 1),
    )
    with byte_client:
        response = byte_client.post(
            "/api/v1/review-sessions",
            content=image,
            headers=_authorized_headers(media_type="image/png"),
        )
        assert response.status_code == 413

    pixel_client, app, service = _create_client(
        tmp_path / "pixels",
        settings=_settings(max_image_pixels=399),
    )
    with pixel_client:
        response = pixel_client.post(
            "/api/v1/review-sessions",
            content=image,
            headers=_authorized_headers(media_type="image/png"),
        )
        assert response.status_code == 400


def test_pdf_review_session_analyzes_pages_updates_geometry_and_rebuilds_pdf(
    tmp_path,
):
    from bidr_sanitizer.pdf.sanitizer import pdf_has_extractable_text

    client, app, service = _create_client(tmp_path)
    with client:
        uploaded_response = client.post(
            "/api/v1/review-sessions",
            content=_pdf_bytes(page_count=2),
            headers=_authorized_headers(media_type="application/pdf"),
        )
        assert uploaded_response.status_code == 201, uploaded_response.text
        uploaded = uploaded_response.json()
        assert uploaded["media_type"] == "application/pdf"
        assert uploaded["page_count"] == 2
        assert [page["page_number"] for page in uploaded["pages"]] == [1, 2]
        session_id = uploaded["session_id"]
        assert not list(
            app.state.review_sessions.workspace_root.rglob("source_page_*.png")
        )

        preview = client.get(
            f"/api/v1/review-sessions/{session_id}/pages/2/source",
            headers=_authorized_headers(),
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/png")
        rendered_previews = list(
            app.state.review_sessions.workspace_root.rglob("source_page_*.png")
        )
        assert [path.name for path in rendered_previews] == [
            "source_page_0002.png"
        ]

        analyzed_response = client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={"redaction_margin": 0, "max_redaction_passes": 2},
            headers=_authorized_headers(),
        )
        assert analyzed_response.status_code == 200, analyzed_response.text
        analyzed = analyzed_response.json()
        assert analyzed["plan"] is None
        assert all(page["plan"] is not None for page in analyzed["pages"])
        assert len(
            list(app.state.review_sessions.workspace_root.rglob("source_page_*.png"))
        ) == 2

        revised_response = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={
                "page_number": 1,
                "expected_revision": 0,
                "decisions": [],
                "geometry_updates": [
                    {
                        "region_id": "auto-0001",
                        "bbox": {"x1": 12, "y1": 12, "x2": 35, "y2": 35},
                    }
                ],
                "manual_regions": [],
            },
            headers=_authorized_headers(),
        )
        assert revised_response.status_code == 200, revised_response.text
        revised = revised_response.json()
        first_region = revised["pages"][0]["plan"]["regions"][0]
        assert first_region["geometry_modified"] is True
        assert first_region["bbox"] == {"x1": 12, "y1": 12, "x2": 35, "y2": 35}

        incomplete_export = client.post(
            f"/api/v1/review-sessions/{session_id}/export",
            json={
                "expected_revisions": [
                    {"page_number": 1, "revision": 1},
                ]
            },
            headers=_authorized_headers(),
        )
        assert incomplete_export.status_code == 409

        export_response = client.post(
            f"/api/v1/review-sessions/{session_id}/export",
            json={
                "expected_revisions": [
                    {"page_number": 1, "revision": 1},
                    {"page_number": 2, "revision": 0},
                ]
            },
            headers=_authorized_headers(),
        )
        assert export_response.status_code == 200, export_response.text
        exported = export_response.json()["export"]
        assert exported["page_count"] == 2
        assert exported["text_layer_empty"] is True
        assert exported["automatic_geometry_adjustment_count"] == 1
        assert exported["status"] == "verified_with_human_overrides"

        download = client.get(
            f"/api/v1/review-sessions/{session_id}/export",
            headers=_authorized_headers(),
        )
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("application/pdf")
        assert download.headers["x-bidr-verification-status"] == (
            "verified_with_human_overrides"
        )
        output_path = tmp_path / "reviewed.pdf"
        output_path.write_bytes(download.content)
        assert not pdf_has_extractable_text(output_path)


def test_pdf_upload_enforces_page_and_rendered_pixel_limits(tmp_path):
    page_client, app, service = _create_client(
        tmp_path / "pages",
        settings=_settings(max_pdf_pages=1),
    )
    with page_client:
        response = page_client.post(
            "/api/v1/review-sessions",
            content=_pdf_bytes(page_count=2),
            headers=_authorized_headers(media_type="application/pdf"),
        )
        assert response.status_code == 413
        assert response.json() == {
            "detail": "The PDF has 2 pages; the configured maximum is 1."
        }

    pixel_client, app, service = _create_client(
        tmp_path / "pixels",
        settings=_settings(max_image_pixels=359_999),
    )
    with pixel_client:
        response = pixel_client.post(
            "/api/v1/review-sessions",
            content=_pdf_bytes(page_count=1),
            headers=_authorized_headers(media_type="application/pdf"),
        )
        assert response.status_code == 413
        assert response.json() == {
            "detail": "A rendered PDF page exceeds the configured pixel limit."
        }


def test_default_pdf_page_limit_accepts_an_81_page_document(tmp_path):
    client, app, service = _create_client(
        tmp_path,
        settings=_settings(pdf_review_dpi=72),
    )
    with client:
        response = client.post(
            "/api/v1/review-sessions",
            content=_pdf_bytes(page_count=81),
            headers=_authorized_headers(media_type="application/pdf"),
        )

        assert response.status_code == 201, response.text
        assert response.json()["page_count"] == 81


def test_valid_jpeg_upload_uses_a_generic_server_side_name(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        response = client.post(
            "/api/v1/review-sessions",
            content=_jpeg_bytes(),
            headers={
                **_authorized_headers(media_type="image/jpeg"),
                "X-Original-Filename": "do-not-persist-this-name.jpeg",
            },
        )
        assert response.status_code == 201
        session_id = response.json()["session_id"]
        session_directory = tmp_path / "sessions" / session_id
        assert sorted(path.name for path in session_directory.iterdir()) == [
            "source.jpg"
        ]
        assert "do-not-persist-this-name" not in response.text


def test_complete_api_review_workflow_keeps_sensitive_state_server_side(tmp_path):
    service = FakeReviewService()
    client, app, service = _create_client(tmp_path, service=service)

    with client:
        uploaded = _upload_png(client)
        session_id = uploaded["session_id"]
        assert uploaded["state"] == "uploaded"
        assert uploaded["plan"] is None
        assert uploaded["image_width"] == 100
        assert uploaded["image_height"] == 100

        session_directory = tmp_path / "sessions" / session_id
        assert sorted(path.name for path in session_directory.iterdir()) == [
            "source.png"
        ]

        source_response = client.get(
            f"/api/v1/review-sessions/{session_id}/source",
            headers=_authorized_headers(),
        )
        assert source_response.status_code == 200
        assert source_response.content == _png_bytes()
        assert source_response.headers["cache-control"] == "no-store, max-age=0"
        assert "BIDR_SOURCE.png" in source_response.headers["content-disposition"]

        premature_export = client.post(
            f"/api/v1/review-sessions/{session_id}/export",
            json={"expected_revision": 0},
            headers=_authorized_headers(),
        )
        assert premature_export.status_code == 409

        analyzed_response = client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={"redaction_margin": 0, "max_redaction_passes": 3},
            headers=_authorized_headers(),
        )
        assert analyzed_response.status_code == 200, analyzed_response.text
        analyzed = analyzed_response.json()
        assert analyzed["state"] == "analyzed"
        assert analyzed["plan"]["revision"] == 0
        assert analyzed["plan"]["regions"][0]["detection_type"] == "face"
        assert "source_sha256" not in analyzed_response.text
        assert service.analysis_paths[0].name == "source.png"

        revised_response = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={
                "expected_revision": 0,
                "decisions": [
                    {"region_id": "auto-0001", "action": "remove"}
                ],
                "manual_regions": [
                    {"bbox": {"x1": 40, "y1": 40, "x2": 55, "y2": 55}}
                ],
            },
            headers=_authorized_headers(),
        )
        assert revised_response.status_code == 200, revised_response.text
        revised = revised_response.json()
        assert revised["plan"]["revision"] == 1
        assert revised["plan"]["regions"][0]["action"] == "remove"
        assert revised["plan"]["regions"][1]["provenance"] == "manual"

        stale_revision = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={"expected_revision": 0},
            headers=_authorized_headers(),
        )
        assert stale_revision.status_code == 409

        export_response = client.post(
            f"/api/v1/review-sessions/{session_id}/export",
            json={"expected_revision": 1},
            headers=_authorized_headers(),
        )
        assert export_response.status_code == 200, export_response.text
        exported = export_response.json()
        assert exported["state"] == "exported"
        assert exported["export"]["status"] == "verified_with_human_overrides"
        assert exported["export"]["detectors_clear"] is True
        assert exported["export"]["passed"] is False
        assert exported["export"]["automatic_removal_count"] == 1
        assert exported["export"]["manual_addition_count"] == 1
        assert service.export_paths[0][0].name == "source.png"
        assert service.export_paths[0][1].name == "reviewed.png"

        download = client.get(
            f"/api/v1/review-sessions/{session_id}/export",
            headers=_authorized_headers(),
        )
        assert download.status_code == 200
        assert download.headers["x-bidr-verification-status"] == (
            "verified_with_human_overrides"
        )
        assert "BIDR_REVIEW_RESULT.png" in download.headers["content-disposition"]
        with Image.open(BytesIO(download.content)) as output:
            assert output.getpixel((20, 20)) == (255, 255, 255)
            assert output.getpixel((45, 45)) == (0, 0, 0)

        delete = client.delete(
            f"/api/v1/review-sessions/{session_id}",
            headers=_authorized_headers(),
        )
        assert delete.status_code == 204
        assert not session_directory.exists()

        missing = client.get(
            f"/api/v1/review-sessions/{session_id}",
            headers=_authorized_headers(),
        )
        assert missing.status_code == 404


def test_plan_update_invalidates_previous_export(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        session_id = _upload_png(client)["session_id"]
        client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={},
            headers=_authorized_headers(),
        )
        exported = client.post(
            f"/api/v1/review-sessions/{session_id}/export",
            json={"expected_revision": 0},
            headers=_authorized_headers(),
        )
        assert exported.status_code == 200

        revised = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={
                "expected_revision": 0,
                "decisions": [
                    {"region_id": "auto-0001", "action": "remove"}
                ],
            },
            headers=_authorized_headers(),
        )
        assert revised.status_code == 200
        assert revised.json()["state"] == "analyzed"
        assert revised.json()["export"] is None

        stale_download = client.get(
            f"/api/v1/review-sessions/{session_id}/export",
            headers=_authorized_headers(),
        )
        assert stale_download.status_code == 409


def test_invalid_review_geometry_is_rejected_without_changing_plan(tmp_path):
    client, app, service = _create_client(tmp_path)
    with client:
        session_id = _upload_png(client)["session_id"]
        client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={},
            headers=_authorized_headers(),
        )

        invalid_order = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={
                "expected_revision": 0,
                "manual_regions": [
                    {"bbox": {"x1": 50, "y1": 10, "x2": 40, "y2": 20}}
                ],
            },
            headers=_authorized_headers(),
        )
        assert invalid_order.status_code == 422

        outside_image = client.patch(
            f"/api/v1/review-sessions/{session_id}/plan",
            json={
                "expected_revision": 0,
                "manual_regions": [
                    {"bbox": {"x1": 90, "y1": 90, "x2": 110, "y2": 110}}
                ],
            },
            headers=_authorized_headers(),
        )
        assert outside_image.status_code == 422

        current = client.get(
            f"/api/v1/review-sessions/{session_id}",
            headers=_authorized_headers(),
        )
        assert current.json()["plan"]["revision"] == 0


def test_unexpected_service_error_does_not_echo_internal_values(tmp_path, caplog):
    app = create_app(
        settings=_settings(),
        service=FailingAnalysisService(),
        workspace_root=tmp_path / "sessions",
    )
    with TestClient(app) as client, caplog.at_level("ERROR"):
        session_id = _upload_png(client)["session_id"]
        response = client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={},
            headers=_authorized_headers(),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error."}
        assert "SYNTHETIC_PRIVATE_ERROR_VALUE" not in response.text
        assert response.headers["cache-control"] == "no-store, max-age=0"
        assert "SYNTHETIC_PRIVATE_ERROR_VALUE" not in caplog.text
        assert "RuntimeError" in caplog.text


def test_application_control_block_returns_safe_actionable_error(tmp_path):
    app = create_app(
        settings=_settings(),
        service=ApplicationControlBlockedService(),
        workspace_root=tmp_path / "sessions",
    )
    with TestClient(app) as client:
        session_id = _upload_png(client)["session_id"]
        response = client.post(
            f"/api/v1/review-sessions/{session_id}/analysis",
            json={},
            headers=_authorized_headers(),
        )

        assert response.status_code == 503
        assert response.json() == {
            "detail": (
                "Windows Application Control blocked a required local analysis "
                "component. The document was not analyzed."
            )
        }
        assert "private_component" not in response.text
        assert response.headers["cache-control"] == "no-store, max-age=0"


def test_shutdown_removes_all_sensitive_session_files(tmp_path):
    client, app, service = _create_client(tmp_path)
    workspace = tmp_path / "sessions"

    with client:
        session_id = _upload_png(client)["session_id"]
        assert (workspace / session_id / "source.png").exists()

    assert workspace.exists()
    assert list(workspace.iterdir()) == []


def test_owned_temporary_workspace_is_removed_on_shutdown():
    app = create_app(settings=_settings(), service=FakeReviewService())
    workspace = app.state.review_sessions.workspace_root

    with TestClient(app) as client:
        _upload_png(client)
        assert workspace.exists()

    assert not workspace.exists()
