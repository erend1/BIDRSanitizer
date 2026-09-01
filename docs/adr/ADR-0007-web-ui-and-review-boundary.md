# ADR-0007: Web UI and Review Application Boundary

**Status:** Accepted

**Date:** 2026-08-24

## Context

BIDR Sanitizer needs an interactive review interface that works fully
offline on a desktop first and can later be deployed as a multi-user web
application.

The current service sanitizes a selected file immediately. A review UI
instead needs to display proposed detections, accept manual additions,
record explicit removal of automatic detections, and export only after
the user has reviewed a plan.

Browser preview overlays cannot perform privacy redaction. They are only
a presentation of a proposed plan. Export must continue to use the
deterministic privacy engine and verification must scan the exported
artifact.

The existing OCR, Paddle, PyTorch, OpenCV, PDF, and Microsoft Word COM
components are native Python or platform runtimes. They are not suitable
for moving into a browser WebAssembly bundle.

## Decision

The user interface will be a conventional static web application above a
versioned HTTP application boundary.

The intended implementation is:

```text
React and TypeScript web application
              |
          HTTP /api/v1
              |
      FastAPI application adapter
              |
       review/service layer
              |
    existing privacy-critical core
```

For the offline desktop application, pywebview will host the same web
application using the installed Windows WebView2 runtime. FastAPI will
listen only on loopback. A future hosted deployment will replace the
desktop shell and authentication policy, not the review or sanitizer
contract.

The frontend must not call Python objects through a desktop-only bridge
for ordinary document operations. Upload, analysis, review, export, and
cleanup must use the same HTTP contract in desktop and hosted modes.

## Review contract

The application layer must separate:

```text
source document
      |
automatic analysis
      |
versioned detection plan
      |
human review
      |
final redaction plan
      |
deterministic export
      |
verification of exported output
```

Image regions use original image pixel coordinates. Display scaling,
zooming, and browser coordinates must never become core redaction
coordinates.

A plan must be bound to the exact analyzed source so that coordinates
cannot accidentally be applied to a different file.

Review state must retain:

- whether a region was automatic or manually added;
- whether an automatic region was retained or explicitly removed;
- detection category and confidence when supplied by a detector;
- the plan revision used for export;
- counts of manual additions and automatic removals.

Detected PII strings must not be added to review models, API responses,
logs, receipts, or audit summaries.

## Human overrides and verification

Removing an automatic region is an explicit human override.

Export remediation must not silently re-add a region that the user
explicitly removed. If verification detects information in that removed
region, the result remains review-required.

If the configured verifier reports no remaining detections but the final
plan contains removed automatic regions, the result must be represented
as verified with human overrides. It must not be represented as an
ordinary automatic pass.

Manual additions are privacy-conservative and become normal destructive
redaction regions during export.

## Offline desktop security

The desktop application must:

- bind only to `127.0.0.1` on an operating-system-selected port;
- require a per-launch secret for state-changing API requests;
- serve the frontend and API from the same origin;
- reject unapproved origins and hosts;
- bundle scripts, styles, fonts, and other assets locally;
- prohibit remote navigation and telemetry;
- mark sensitive preview responses as non-cacheable;
- keep uploads and previews in private temporary workspaces;
- clean temporary document data on removal and shutdown;
- keep heavy models in one long-lived worker initially.

Normal desktop processing remains offline. Loading the UI must not add a
model-download or hosted-inference path.

## Hosted deployment consequence

A hosted deployment changes the privacy and operational threat model.
Documents will leave the user's device and reach the selected server.

Before hosted deployment, the project will require a separate security
review covering authentication, authorization, tenant isolation, upload
limits, encrypted transport and storage, retention, cleanup, worker
isolation, abuse controls, and deployment-specific audit policy.

Microsoft Word COM also requires either a controlled Windows server or a
future replacement format adapter.

## Simplicity constraints

The first frontend will use a static JavaScript build, React, TypeScript,
ordinary CSS, and native SVG for image review. The current default build uses
Webpack so Windows application-control policies do not have to permit an
unsigned native bundler binding; Vite remains an optional compatibility
toolchain. The bundler choice does not change the review or privacy boundary.

The initial design will not require server-side rendering, Electron,
Redux, a JavaScript server in production, or a Rust/Tauri shell.

Tauri may replace pywebview later if installer, updater, or stronger
desktop-shell capabilities justify the additional toolchain. The HTTP
boundary allows that change without replacing the UI or privacy engine.

## Consequences

The project gains a stable application contract usable from desktop and
hosted web clients.

The privacy-critical core remains independent of FastAPI, React,
pywebview, and UI widget state.

There are two development toolchains, Python and Node.js, but the shipped
frontend is static and does not require Node.js at runtime.

Interactive review requires temporary sensitive previews. Those previews
must receive the same privacy care as source documents and must never be
mistaken for sanitized output.
