# ADR-0002: Separate Detection from Destructive Redaction

**Status:** Accepted  
**Date:** 2026-08-24

## Context

BIDR Sanitizer needs to identify several categories of potentially
sensitive information using different techniques.

These include deterministic structured recognizers, OCR-derived text
recognition, semantic recognition, face detection, and signature
detection.

Detection is inherently probabilistic or heuristic for several of these
categories.

Redaction, however, should not be probabilistic once a target region has
been selected.

Blur, pixelation, transparency, removable document overlays, and similar
presentation-oriented masking techniques may preserve recoverable source
information.

The project therefore requires a strict distinction between deciding
what should be covered and destroying the selected visual content.

## Decision

Detection and redaction are separate responsibilities.

Detection components produce structured detections or text spans.

Detection objects must identify categories and regions without retaining
raw sensitive values unless strictly required transiently during
processing.

Image redaction is deterministic after detection.

The default visual redaction method is an opaque solid replacement with
an expansion margin around the detected region.

Blur, pixelation, semi-transparent masking, and removable overlays are
not accepted as privacy-preserving redaction mechanisms.

TXT sanitization replaces selected textual spans with a fixed marker such
as `[REDACTED]`.

Redaction operates on copies or newly constructed output objects rather
than intentionally modifying source files in place.

Where multiple remediation passes are required for images, subsequent
outputs should be redrawn from the original input using accumulated
detections rather than repeatedly transforming an already recompressed
output.

## Consequences

Detector quality and redaction correctness can be tested independently.

False-positive detections may cause additional content to be removed.
This is acceptable relative to the project's high-recall privacy goal.

False-negative detections remain possible and are addressed through
verification, regression testing, and human review rather than through
reversible masking.

Output images may lose visual information beyond the exact sensitive
region because margins are intentionally applied.

Future UI styles may provide alternative opaque destructive rendering,
such as different solid fills or decorative fully opaque masks, provided
that the selected source pixels remain unrecoverable through the output
representation.

## Manual overrides

A future user interface may allow a human reviewer to add or remove
redaction regions.

Adding a mask is compatible with the standard privacy model.

Removing an automatically generated mask is an explicit human override.

A workflow that intentionally removes an automatic mask must not silently
present the ordinary automatic PASS result as though no privacy decision
had been overridden.

The UI must communicate that distinction clearly.