# Changelog

All notable changes to BIDR Sanitizer will be documented in this file.

The project follows Semantic Versioning.

## [Unreleased]

### Added

- Offline-first image sanitization pipeline.
- PNG and JPEG sanitization.
- PDF page rasterization and image-only PDF reconstruction.
- DOC and DOCX conversion through Microsoft Word.
- TXT sanitization.
- Turkish TCKN recognition.
- Turkish telephone-number recognition.
- E-mail recognition.
- Semantic person-name detection.
- Semantic and deterministic address detection.
- Rotation-safe face detection.
- Handwritten signature detection.
- Irreversible opaque redaction.
- Iterative post-redaction verification.
- Local model configuration.
- Explicit `bidr-models install` and `bidr-models check` commands.
- Pinned, manifest-driven model downloads with size and SHA-256 checks.
- Transactional staged model promotion and explicit repair behavior.
- Self-contained offline GLiNER tokenizer and encoder-config installation.
- Command-line and batch-processing foundations.
