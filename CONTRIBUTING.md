# Contributing to BIDR Sanitizer

Thank you for your interest in improving BIDR Sanitizer.

Because this project processes privacy-sensitive documents, contributions
that affect detection, redaction, verification, file conversion, or model
behavior require additional care.

Please read:

```text
AGENTS.md
docs/ARCHITECTURE.md
docs/PRIVACY_AND_SECURITY.md
docs/DEVELOPMENT.md
docs/TESTING.md
```

before modifying core privacy behavior.

---

# Development Setup

Follow:

```text
docs/INSTALLATION.md
```

for environment and model setup.

Create a virtual environment and install the project in editable
development mode.

---

# Before Making Changes

Run the existing baseline:

```powershell
python scripts\check_public_tree.py
python -m pytest -q
```

This confirms that any later regression was introduced by the new change.

---

# Pull Request Requirements

A contribution affecting behavior should include appropriate tests.

Privacy-sensitive changes should explain:

```text
what changed
why it changed
how recall may be affected
which tests were added
whether thresholds changed
whether model behavior changed
whether output format changed
```

Architecture-affecting changes should update documentation in the same
pull request.

---

# High-Recall Policy

BIDR Sanitizer generally prioritizes recall over visual cleanliness.

Do not reduce false positives by increasing thresholds unless the effect
on difficult sensitive examples has been evaluated.

A cleaner-looking document is not necessarily a safer document.

---

# New Detectors

A new detector should integrate into both:

```text
sanitization
verification
```

It should return the project's internal detection structures rather than
leaking model-specific objects through the codebase.

Add regression tests.

---

# New File Formats

Prefer an adapter into the existing image or text engine.

For example:

```text
new document format
       ↓
safe rendering/conversion
       ↓
existing sanitizer
```

Avoid duplicating privacy recognition code by file format.

---

# Redaction Changes

Do not implement redaction as a removable visual overlay.

The exported output must no longer contain the underlying sensitive
information.

Blur and pixelation are not accepted as default privacy redaction
mechanisms.

---

# Logging

Do not add raw detected PII to logs.

Do not include real PII in test failure messages, diagnostics, examples,
or screenshots.

---

# Test Data

Public contributions must use synthetic or otherwise explicitly safe test
data.

Do not attach real sensitive documents to public issues or pull requests.

---

# Dependency Changes

Changes to foundational ML dependencies should include integration
testing.

PaddlePaddle in particular has known version-sensitive Windows behavior.

See:

```text
docs/MAINTAINER_HANDOFF.md
docs/TROUBLESHOOTING.md
```

before upgrading.

---

# Model Changes

If introducing or replacing an ML model, document:

```text
model name
upstream source
license
purpose
local directory layout
confidence policy
CPU/runtime requirements
offline behavior
```

Update:

```text
models/manifest.json
docs/MODELS.md
THIRD_PARTY_NOTICES.md
```

as applicable.

---

# Public Repository Safety

Before committing:

```powershell
python scripts\check_public_tree.py
```

Before pushing, inspect staged content:

```powershell
git status
git diff --cached --stat
git diff --cached
```

Never assume `.gitignore` alone is sufficient protection against
publishing sensitive material.

---

# Reporting Bugs

When possible, provide:

```text
operating system
Python version
BIDR Sanitizer version/commit
input format
detector involved
safe traceback
minimal synthetic reproduction
```

Do not upload the original private document.

---

# Security Problems

Security-sensitive issues should follow:

```text
SECURITY.md
```

rather than being disclosed publicly before maintainers have an
opportunity to evaluate them.

---

# Code Review Perspective

Review privacy changes by asking:

```text
Can this increase false negatives?
Can original information survive the export?
Can hidden document data survive?
Can sensitive values enter logs?
Can runtime unexpectedly access the network?
Can verification falsely claim success?
```

These questions are more important than cosmetic implementation
differences.