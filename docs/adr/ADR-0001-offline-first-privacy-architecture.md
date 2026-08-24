# ADR-0001: Offline-First Privacy Architecture

**Status:** Accepted  
**Date:** 2026-08-24

## Context

BIDR Sanitizer processes documents that may contain personally
identifiable information, confidential evidence, or other sensitive
content.

Supported detection capabilities include textual PII, faces, and
signatures. Processing such material through hosted inference services
would introduce additional disclosure, data-retention, connectivity,
and trust requirements.

The project also needs predictable behavior in environments where
network access is restricted or unavailable.

Privacy-sensitive runtime behavior therefore needs a clear architectural
boundary.

## Decision

Document sanitization and model inference will be offline-first.

Document content, OCR text, detected PII, images, document pages, and
other sensitive source material must not be silently transmitted to
external services during sanitization.

Required inference models are loaded from local storage.

A missing model is treated as an explicit configuration or installation
error. Runtime sanitization must not interpret a missing model as
permission to download it automatically.

Model installation may be implemented as a separate, explicit operation
that uses the network, provided that the operation is clearly initiated
by the user and remains separate from document sanitization.

Logs and audit output must not contain raw detected sensitive values.

## Consequences

BIDR Sanitizer can operate without network connectivity after required
models and dependencies have been installed.

Model installation becomes a separate deployment concern.

The application must provide understandable diagnostics when required
local models are unavailable.

Some dependencies may contain networking capabilities internally.
BIDR Sanitizer must configure and invoke them in a manner consistent
with this decision.

Future integrations with hosted OCR, hosted NER, cloud storage, remote
LLMs, telemetry, or similar services may not be added transparently to
the sanitization pipeline.

Any future network-enabled capability must be explicit, separately
documented, and designed so that local sanitization remains available.

## Security and privacy implications

Offline-first operation reduces the number of systems that receive
sensitive source material.

It does not itself guarantee confidentiality. Local malware, insecure
temporary storage, compromised dependencies, inappropriate filesystem
permissions, or user actions may still expose information.

This ADR defines an architectural boundary, not a complete endpoint
security model.