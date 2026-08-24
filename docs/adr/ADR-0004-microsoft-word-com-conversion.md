# ADR-0004: Microsoft Word COM Conversion for DOC and DOCX

**Status:** Accepted  
**Date:** 2026-08-24

## Context

DOC and DOCX documents may contain text, shapes, images, headers,
footers, fields, equations, embedded objects, and other structures that
would require substantial format-specific sanitization logic.

BIDR Sanitizer already has a privacy-oriented PDF pipeline that
rasterizes pages and reconstructs sanitized output.

A reliable method is therefore needed to obtain a high-fidelity rendered
representation of Microsoft Word documents before applying the PDF
pipeline.

## Decision

On Windows, BIDR Sanitizer uses installed Microsoft Word through COM
automation to export DOC and DOCX inputs to a temporary PDF.

The temporary PDF is treated as untrusted intermediate data.

The exported PDF is passed through the same PDF sanitization pipeline
used for native PDF input.

The final sanitized Word-document output is therefore a reconstructed,
image-only PDF rather than a modified DOC or DOCX file.

Word is opened through an isolated automation instance where practical.

Documents are opened read-only.

Interactive alerts are disabled.

Macro automation is disabled or restricted using the available Word
automation controls before opening untrusted documents.

Temporary Word-exported PDFs are removed during normal cleanup.

## Consequences

DOC and DOCX sanitization is Windows-specific.

Microsoft Word must be installed and available to the current user.

LibreOffice is not treated as an interchangeable rendering backend for
this architecture because fidelity and rendering differences could
change privacy-sensitive output.

The Word COM adapter is appropriate for controlled desktop or operator
workflows.

It is not considered an appropriate unattended server architecture.

Word automation can fail because of Office installation state, COM
registration, interactive Office prompts, document corruption, user
profile configuration, or operating-system policy.

The sanitizer must surface such failures rather than silently bypassing
the conversion stage.

## Temporary files

Temporary PDFs contain untrusted rendered representations of potentially
sensitive documents.

Normal file deletion is performed during cleanup.

BIDR Sanitizer does not claim that ordinary deletion constitutes
forensic secure erasure from storage media.

Systems with stronger residual-data requirements must apply appropriate
host-level storage and media controls.

## Future alternatives

A different Word-rendering backend may be introduced only if its output
fidelity and privacy behavior are explicitly evaluated.

Such a change should be documented in a new ADR rather than silently
replacing the Word COM strategy.