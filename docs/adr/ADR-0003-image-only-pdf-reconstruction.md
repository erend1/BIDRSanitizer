# ADR-0003: Image-Only PDF Reconstruction

**Status:** Accepted  
**Date:** 2026-08-24

## Context

PDF documents can contain substantially more information than the
visible page appearance.

Potentially sensitive information may remain in searchable text,
invisible OCR layers, annotations, forms, attachments, metadata, or
other PDF objects even after visible rectangles are placed over page
content.

Attempting to modify the original PDF object graph while proving that
all hidden representations have been removed would significantly
increase implementation complexity and privacy risk.

BIDR Sanitizer prioritizes privacy-oriented destruction over preservation
of document internals.

## Decision

PDF sanitization uses rasterization and reconstruction.

Each source PDF page is rendered to an image.

The rendered page is processed through the standard image sanitization
pipeline.

The sanitized raster is adaptively converted to an indexed-color image without
changing its pixel dimensions. Opaque black redaction regions are reapplied
after this conversion, and verification runs on those final compact pixels.

A new PDF is then created by directly embedding the compact sanitized image
streams, without decoding and re-encoding them during assembly.

The reconstructed PDF preserves the intended page dimensions but does
not preserve the original PDF object graph.

Original searchable text, hidden OCR layers, annotations, forms,
attachments, embedded document objects, and original metadata are not
intentionally copied into the sanitized output.

The final reconstructed PDF must not contain an extractable text layer
introduced by BIDR Sanitizer.

## Consequences

Sanitized PDFs are intentionally image-only.

Searchability, text selection, semantic accessibility, editable form
fields, hyperlinks, annotations, and similar source-PDF capabilities may
be lost.

Image-only reconstruction cannot mathematically guarantee an output no larger
than every possible source vector PDF. Adaptive color reduction and direct
stream embedding minimize that cost while retaining the configured spatial
resolution and privacy architecture.

Rasterization quality and DPI become relevant to both readability and
detector performance.

The approach significantly reduces the risk that visually covered text
remains recoverable from the original PDF structure.

The reconstructed file is a new document rather than a modified version
of the original PDF internals.

Placing replacement images only over source coordinates was rejected: the
original selectable or hidden content would remain underneath and the visual
cover could be removed.

## Verification

PDF verification includes the page-level privacy pipeline and a final
check that BIDR Sanitizer has not produced an extractable text layer.

This does not imply that every possible PDF parser, exploit technique,
or forensic technique has been formally proven incapable of extracting
information.

The security benefit comes primarily from discarding the original object
graph and reconstructing the document from sanitized raster content.
