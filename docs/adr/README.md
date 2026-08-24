# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for
BIDR Sanitizer.

ADRs document significant architectural decisions that affect privacy,
security, portability, maintainability, or the interpretation of
sanitization results.

They complement `docs/ARCHITECTURE.md`.

The architecture document describes how BIDR Sanitizer currently works.
ADRs explain why important design choices were made and which properties
must be preserved when the implementation evolves.

## Status values

An ADR may use one of the following statuses:

- Proposed
- Accepted
- Superseded
- Deprecated

An accepted ADR should not be edited merely because the implementation
changes internally.

If an architectural decision changes materially, create a new ADR and
mark the previous ADR as superseded.

## Current decisions

| ADR | Decision | Status |
| --- | --- | --- |
| ADR-0001 | Offline-first privacy architecture | Accepted |
| ADR-0002 | Detection separated from destructive redaction | Accepted |
| ADR-0003 | Image-only PDF reconstruction | Accepted |
| ADR-0004 | Microsoft Word COM conversion strategy | Accepted |
| ADR-0005 | Local external model storage | Accepted |
| ADR-0006 | Verification semantics and limitations | Accepted |

## Contributor expectation

Changes that materially affect any of the following should be evaluated
against the ADRs before implementation:

- document or image content leaving the local machine
- automatic network access during sanitization
- redaction reversibility
- PDF reconstruction
- DOC/DOCX conversion
- model storage or loading
- logging of detected values
- verifier meaning
- PASS semantics
- manual removal of automatically generated masks