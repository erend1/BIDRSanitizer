## Summary

Describe the purpose of this change and the problem it addresses.

## Changes

- 
- 
- 

## Testing

Describe the tests performed.

Examples:

- `python -m pytest -q`
- `python scripts/check_public_tree.py`
- synthetic fixture validation
- clean-wheel installation
- manual integration test

## Privacy and security impact

Answer each item briefly.

- Does this change affect detection behavior?
- Does this change affect redaction behavior?
- Does this change affect verification behavior?
- Does this change affect temporary-file handling?
- Does this change affect logging?
- Does this change introduce or modify network access?
- Does this change alter model loading or model locations?
- Could this change cause raw sensitive values to appear in logs, exceptions, filenames, or audit output?

If none apply, state:

> No privacy or security behavior is changed.

## Offline behavior

Confirm whether runtime document sanitization remains local and offline-first.

- [ ] This change does not silently transmit document content or detected PII.
- [ ] This change does not silently download models during sanitization.

## Redaction guarantees

- [ ] Destructive redaction semantics are preserved.
- [ ] No blur, pixelation, removable overlay, or reversible masking was introduced.
- [ ] Any intentional change to redaction semantics is clearly documented.

## Verification

- [ ] Verification behavior is preserved or intentionally updated.
- [ ] Tests cover any verifier changes.
- [ ] Documentation does not describe `PASS` as a legal, regulatory, or absolute privacy guarantee.

## Models and dependencies

- [ ] No model weights or large binary model files are included in the repository.
- [ ] New dependencies are documented and justified.
- [ ] New models include source and license information.
- [ ] Model files remain outside the source package.

## Repository safety

- [ ] No private documents or real sensitive evidence are included.
- [ ] No credentials, API keys, secrets, or local environment files are included.
- [ ] Generated outputs and local model files are not committed.

## Documentation

- [ ] Documentation was updated where behavior changed.
- [ ] No documentation update is required.

## Checklist

- [ ] Tests pass locally.
- [ ] Public-tree check passes.
- [ ] The change is scoped and does not include unrelated modifications.