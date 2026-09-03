# React Web Client

## Purpose and Scope

The `web/` directory contains the local-first review interface for the
versioned `/api/v1` adapter.

```text
React + TypeScript + native SVG
               |
        same-origin /api/v1
               |
      private review sessions
               |
     deterministic BIDR export
```

The browser displays review geometry but does not redact documents. Automatic
detections, human decisions, and manual regions are saved as a versioned plan.
The Python privacy engine permanently replaces pixels during export and scans
each newly generated page image again.

The client accepts PNG, JPEG, and PDF. PDF pages are reviewed through the same
image-plan contract, then rebuilt by the server as a new image-only PDF. Word
and text review remain future adapters and must continue through the
centralized privacy engines.

PDF upload validates page count and geometry without eagerly rendering every
page. Rendering occurs when a preview is requested and for all pages when
analysis begins. Export keeps the configured 300-DPI pixel dimensions,
adaptively reduces page color depth, verifies those final compact pixels, and
directly embeds their compressed streams into the new PDF. It never overlays
images on the original PDF or preserves the original text layer.

---

## Design Constraints

The client deliberately uses:

- a static Webpack build;
- React and strict TypeScript;
- ordinary CSS;
- native SVG whose view box is the current source page's original pixel space;
- React state rather than a global state framework;
- locally bundled code with no remote fonts, scripts, telemetry, or hosted
  inference.

Source previews and exports are fetched with the authenticated API client and
displayed through short-lived blob URLs. The launch token is held only in
memory. It is not put in a query string, build-time environment variable,
browser storage, or log.

`public/runtime-config.js` is an intentionally empty bootstrap placeholder.
The future desktop host may serve that same path dynamically with a no-store
response such as:

```javascript
window.__BIDR_RUNTIME__ = {
  apiToken: "per-launch-secret"
};
```

An actual token must never be committed to that file. The manual token field is
only a development fallback.

---

## Review Behavior

The client supports:

- drag-and-drop or file selection without uploading the original filename;
- safety margin and maximum verification-pass settings before analysis;
- an authenticated sensitive-source preview;
- authenticated, page-by-page PDF previews and navigation;
- automatic geometry grouped by detector category and confidence;
- manual rectangles drawn in source-image pixel coordinates;
- a keyboard-accessible coordinate form for manual rectangles;
- click-to-select automatic and manual rectangles, drag-to-move editing, and
  four-corner resizing constrained to the page bounds;
- explicit `Keep visible · override` decisions for automatic regions;
- explicit human-override accounting when an automatic rectangle is moved or
  resized;
- independent unsaved review drafts for every PDF page;
- optimistic plan revisions and conflict reloads;
- deterministic per-page export followed by verification and, for PDF, new
  image-only PDF construction plus an extractable-text check;
- distinct `passed`, `verified_with_human_overrides`, and `review_required`
  result views;
- geometry-only receipts and generic download filenames;
- explicit session deletion plus best-effort unload cleanup.

Preview rectangles are not privacy protection. They remain overlays until the
server performs export.

---

## Local Development

Install the Python API and web dependencies:

```powershell
python -m pip install -e ".[all,dev,web-api]"
npm --prefix web ci
```

Normal model installation remains explicit and separate:

```powershell
bidr-models install
bidr-models check
```

Create a fresh token without writing it into the repository, then start the API
in the first terminal:

```powershell
$env:BIDR_DEV_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:BIDR_INFERENCE_DEVICE = "auto"
python scripts\run_web_api_dev.py
```

`auto` uses an installed NVIDIA GPU runtime when available and otherwise uses
CPU. To require the first GPU and receive a clear startup error instead of a
CPU fallback, set `BIDR_INFERENCE_DEVICE=gpu:0`. Install and verify the pinned
Windows GPU packages with `scripts\install_gpu_runtime.ps1` as described in
`docs/INSTALLATION.md`. Restart the API after changing packages or device
selection.

Start the web client in a second terminal:

```powershell
npm --prefix web run dev
```

Open `http://127.0.0.1:4173`, then paste the current value of
`BIDR_DEV_API_TOKEN` into the development token field. The Webpack development
server proxies `/api` to the loopback API on port `8765`, so browser requests
remain same-origin.

The connection screen checks both the public health endpoint and an
authenticated token-check endpoint. Restarting the API invalidates the prior
launch token; paste the newly printed token instead of reusing the old one.

The development server uses a fixed port because the API origin allowlist is
exact. Do not bind either process to a public interface.

The API accepts PDFs with up to 100 pages by default. Documents above the
configured page or rendered-pixel limit are reported as resource-limit errors,
not as malformed PDFs.

The default `dev`, `build`, and `test` scripts use Webpack and Jest, whose
normal execution does not require an unsigned native Node binding. This keeps
the development workflow usable when Windows Smart App Control blocks
Rolldown's native module. The optional `dev:vite`, `build:vite`, and
`test:vitest` compatibility scripts remain available for environments where
that binding is permitted. Do not disable Windows security controls merely to
run the optional scripts.

Smart App Control can also block unsigned native Python modules required by
PaddleOCR or Pandas. In that case upload can succeed but analysis returns HTTP
`503` and states that Windows Application Control blocked a local component.
Do not disable Windows security controls as an application workaround. Resolve
the machine policy or use an approved, trusted build of the required native
dependencies, then restart the API and use its new launch token.

---

## Validation

Run the client checks from the repository root:

```powershell
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
```

The tests cover original-pixel coordinate conversion, bounded box movement and
corner resizing, conservative bounding boxes, authenticated no-store
transport, filename isolation, PDF page navigation, review status language,
explicit human overrides, revision-safe plan updates, and the main
upload-to-export interaction.

Python/API validation remains required as well:

```powershell
python scripts\check_public_tree.py
python -m pytest -v
```

---

## Desktop and Hosted Follow-up

The next desktop slice will serve the static build and runtime bootstrap from
the same loopback origin, start the API on an operating-system-selected port,
inject a fresh launch token, restrict webview navigation, and own process and
temporary-workspace cleanup.

The current token boundary is not hosted user authentication. Deploying this
client as a multi-user web service still requires authentication,
authorization, tenant isolation, encrypted transport/storage, retention and
cleanup policy, abuse controls, worker isolation, and a separate privacy and
security review. The desktop-only “runs on this device” copy must also be
revisited before hosted release.
