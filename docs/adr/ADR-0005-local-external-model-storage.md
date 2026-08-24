# ADR-0005: Store Runtime Models Outside the Python Package

**Status:** Accepted  
**Date:** 2026-08-24

## Context

BIDR Sanitizer relies on several local machine-learning models for OCR,
semantic PII recognition, face detection, and signature detection.

Model weights are significantly larger than the Python source package.

Bundling model binaries into the Git repository or Python wheel would
increase package size, complicate licensing review, make upgrades harder,
and create a higher risk of accidentally publishing unreviewed binary
artifacts.

The project also requires predictable offline model locations.

## Decision

Runtime model weights are stored outside both the source repository and
the installed Python package.

On Windows, the canonical default model directory is:

    %LOCALAPPDATA%\BIDRSanitizer\models

The expected structure is:

    models/
    ├── paddleocr/
    │   ├── PP-OCRv5_server_det/
    │   └── latin_PP-OCRv5_mobile_rec/
    ├── gliner/
    │   └── gliner_multi_pii_v1/
    ├── yunet/
    │   └── face_detection_yunet_2023mar.onnx
    └── signature/
        └── yolos-small-signature-detection/

Most users should use the default model directory without configuration.

Advanced users may set:

    BIDR_MODELS_DIR

An explicit `BIDR_MODELS_DIR` takes precedence over the default path.

The default PaddleX cache location is separate:

    %LOCALAPPDATA%\BIDRSanitizer\paddlex_cache

An explicit `PADDLE_PDX_CACHE_HOME` may override that cache location.

## Repository policy

Model weights must not be committed to the public repository.

The repository may contain model metadata, expected identities,
installation instructions, manifests, hashes, source references, and
licensing information.

The public-tree safety check enforces this separation.

## Runtime behavior

Missing model files cause an explicit error.

Sanitization does not silently download replacement models.

A future model-installation command may download models only as a
separate explicit user operation.

## Windows path compatibility

Some native inference libraries may handle non-ASCII Windows model paths
unreliably.

The normal default path remains the per-user application-data directory.

Where the resolved Paddle model path contains characters unsupported by
the native runtime, BIDR Sanitizer should fail with a clear diagnostic
and instruct the user to use an ASCII-safe `BIDR_MODELS_DIR`.

This is an interoperability workaround rather than a requirement that
all users configure a custom model directory.

## Consequences

Python wheels remain comparatively small.

Model installation and package installation remain separate concerns.

Models can be updated or audited independently from application code.

Public releases require a maintained model manifest and third-party
license review.

The exact source and licensing status of every distributed or
recommended model must be established before automated model
installation is published.