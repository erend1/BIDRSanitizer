# Versioned Web API

## Purpose and Scope

The FastAPI adapter exposes the PNG/JPEG review workflow through a stable
same-origin HTTP contract:

```text
React client or desktop webview
              |
          /api/v1
              |
     private review sessions
              |
    BIDRSanitizerService
              |
      privacy-critical core
```

The adapter does not contain detection or redaction logic. It owns HTTP
validation, local session workspaces, DTO conversion, request authentication,
and cleanup.

The initial API is synchronous. Model-backed analysis and export operations
are serialized through one long-lived service because the current local ML
runtimes are expensive and are not assumed to be thread-safe.

---

## Installation

Install the API runtime separately from the base sanitizer:

```powershell
python -m pip install "bidr-sanitizer[web-api]"
```

The pinned API runtime uses FastAPI and Uvicorn. It does not add a hosted AI
service or any runtime model-download path.

---

## Application Factory

The caller must generate and retain a strong per-launch token:

```python
import secrets

from bidr_sanitizer.api import WebAPISettings, create_app


token = secrets.token_urlsafe(32)

app = create_app(
    settings=WebAPISettings(
        api_token=token,
        allowed_hosts=("127.0.0.1",),
        allowed_origins=("http://127.0.0.1:8765",),
    )
)
```

The future desktop host will pass this token to the bundled frontend through
an in-memory bootstrap mechanism. It must not place the token in a URL or
persistent log.

An ASGI server must bind this app to `127.0.0.1`, not every network interface.
For example, a development host may call:

```python
import uvicorn

uvicorn.run(
    app,
    host="127.0.0.1",
    port=8765,
    access_log=False,
)
```

Port selection and desktop lifecycle ownership belong to the upcoming
pywebview host rather than the API package.

---

## Authentication and Browser Boundary

Every review-session request requires:

```text
X-BIDR-API-Token: <per-launch secret>
```

The API additionally:

- permits only configured HTTP `Host` values;
- rejects unapproved browser `Origin` values;
- rejects requests marked `Sec-Fetch-Site: cross-site`;
- does not enable cross-origin resource sharing;
- disables Swagger UI, ReDoc, and runtime OpenAPI routes so no documentation
  page loads CDN assets;
- returns `Cache-Control: no-store` and other defensive headers on API
  responses.

Unexpected service exceptions become a generic non-cacheable HTTP `500`.
The API boundary logs only the exception class name, not the exception message,
request body, token, OCR text, or document values.

The per-launch token is a local desktop request boundary. It is not a hosted,
multi-user authentication system. Hosted deployment still requires real user
authentication, authorization, tenant isolation, retention policy, and a
separate security review.

The app can still generate an OpenAPI dictionary in a trusted build process
through `app.openapi()`. This supports future TypeScript client generation
without publishing a runtime schema endpoint.

---

## Upload Contract

The client creates a session by posting the raw file body:

```http
POST /api/v1/review-sessions
Content-Type: image/png
X-BIDR-API-Token: ...

<PNG bytes>
```

Accepted media types are:

```text
image/png
image/jpeg
```

Multipart parsing is intentionally unnecessary. The original filename is not
sent as part of the contract and is not persisted. The server stores a source
under a random session directory using a generic name such as `source.png`.

Uploads are streamed and constrained by configurable byte and decoded-pixel
limits. Image bytes must match the declared media type.

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Minimal process health check; no document state. |
| `POST` | `/api/v1/review-sessions` | Stream and validate a PNG/JPEG source. |
| `GET` | `/api/v1/review-sessions/{id}` | Read geometry-only session state. |
| `POST` | `/api/v1/review-sessions/{id}/analysis` | Run automatic analysis with typed settings. |
| `PATCH` | `/api/v1/review-sessions/{id}/plan` | Apply decisions/manual regions to an expected revision. |
| `POST` | `/api/v1/review-sessions/{id}/export` | Export and verify an expected plan revision. |
| `GET` | `/api/v1/review-sessions/{id}/source` | Retrieve the sensitive source for authenticated preview. |
| `GET` | `/api/v1/review-sessions/{id}/export` | Retrieve the completed review result. |
| `DELETE` | `/api/v1/review-sessions/{id}` | Remove the private session workspace. |

The source endpoint returns the original sensitive image. It is a preview
resource, not sanitized output.

---

## State and Revisions

```text
uploaded
   |
analysis
   v
analyzed (plan revision 0..N)
   |
export
   v
exported
```

A plan update after export removes the stale exported file and returns the
session to `analyzed`.

Both plan updates and export require `expected_revision`. Stale operations
return HTTP `409` without changing state.

The HTTP plan representation deliberately excludes:

- source paths;
- source SHA-256 fingerprints;
- original filenames;
- OCR text;
- detected PII strings.

It includes only IDs, revisions, dimensions, settings, bounding boxes,
provenance, actions, categories, and confidence.

---

## Export Results

The export response preserves the three review statuses:

```text
passed
verified_with_human_overrides
review_required
```

Remaining and remediation detections are returned as geometry/category data
so the client can present them without receiving a detected PII string.

The binary download also carries:

```text
X-BIDR-Verification-Status
```

An exported artifact with `review_required` exists for continued review. It
must not be labeled or shared as verified safe output.

---

## Workspace Lifecycle

Each session uses a random private directory containing generic source and
review-result names. No endpoint returns those filesystem paths.

The directory is removed when the client deletes the session. All remaining
session directories are removed during application shutdown. Updating a plan
also removes any stale prior export.

Normal deletion is cleanup, not guaranteed secure erasure on SSDs or modern
filesystems. Operating-system account and disk protection remain important for
highly sensitive documents.
