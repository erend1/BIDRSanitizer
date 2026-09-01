# Installation

This guide describes how to install BIDR Sanitizer for local development
and use.

BIDR Sanitizer is currently developed and validated primarily on Windows.
The image, PDF, and TXT engines are designed to remain independent from
Microsoft Office, while DOC and DOCX input currently requires Microsoft
Word on Windows.

---

## Requirements

BIDR Sanitizer currently requires:

| Requirement | Notes |
| --- | --- |
| Python | `>=3.11,<3.14` |
| Operating system | Windows is the current reference platform |
| Microsoft Word | Required only for `.doc` and `.docx` input |
| Local AI models | Required for full image/document sanitization |
| Internet connection | Required only while initially installing packages/models |

Python 3.13 is used in the current known-good development environment.

---

## 1. Clone the Repository

Once the public repository is available:

```powershell
git clone <repository-url>
cd BIDRSanitizer
```

Until the repository is published, use the local project directory.

---

## 2. Create a Virtual Environment

On Windows PowerShell:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Confirm the interpreter:

```powershell
python --version
```

The version should satisfy:

```text
>=3.11,<3.14
```

---

## 3. Upgrade Packaging Tools

```powershell
python -m pip install --upgrade pip setuptools wheel
```

---

## 4. Install BIDR Sanitizer

For development, install the repository in editable mode.

Use the dependency groups currently defined in `pyproject.toml`.

For example, if the project exposes the development/runtime extras:

```powershell
python -m pip install -e ".[all,dev]"
```

To install the versioned HTTP adapter for a local desktop/web client:

```powershell
python -m pip install -e ".[all,web-api]"
```

The `web-api` extra adds the pinned FastAPI and Uvicorn runtime. It does not
install a JavaScript toolchain or desktop webview.

If the exact extras change in a future release, `pyproject.toml` is the
authoritative source.

A normal packaged release will eventually support installation through
the published Python package.

---

## 5. Important PaddlePaddle Version

The known-good Windows CPU environment uses:

```text
PaddleOCR 3.5.0
PaddlePaddle 3.2.2
```

PaddlePaddle 3.3.0 previously produced a native Windows CPU/PIR/oneDNN
runtime failure in this project.

If dependency resolution installs a different PaddlePaddle version and
OCR fails with an error involving:

```text
ConvertPirAttribute2RuntimeAttribute
```

install the known-good version:

```powershell
python -m pip install --force-reinstall "paddlepaddle==3.2.2"
```

Do not upgrade PaddlePaddle independently of integration testing.

If `import paddle` fails because Windows Application Control blocked
`libpaddle.pyd`, `phi.dll`, or another Paddle native component, the package
version is not the immediate cause: Windows rejected unsigned native code.
The web API reports this as HTTP `503` and does not analyze the document.
Do not disable Smart App Control merely as an application workaround. Use an
organization-approved App Control policy or a trusted build of the native
dependency, then restart the API with a fresh launch token.

---

## 6. PyTorch and Torchvision

The signature detector uses Transformers with PyTorch and Torchvision.

For a CPU-only Windows installation, PyTorch packages may be installed
from the official CPU wheel index if required by the dependency setup.

Example:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

The exact compatible versions should be allowed to follow the project's
pinned dependency configuration once release dependency locking is
finalized.

Torchvision is required by the YOLOS signature image processor.

A missing installation may produce an error similar to:

```text
AutoImageProcessor requires the Torchvision library
```

---

## 7. Install Local Models

BIDR Sanitizer requires local model files for OCR, semantic PII
recognition, face detection, and signature detection.

Install the pinned model set with the explicit setup command:

```powershell
bidr-models install
```

On Windows, the default destination is:

    %LOCALAPPDATA%\BIDRSanitizer\models

No `BIDR_MODELS_DIR` environment variable is required when using this
default location.

The installer downloads only the manifest-selected files from immutable
upstream revisions. Each model is staged, checked for the expected size
and SHA-256 hash, and promoted into its runtime path only after complete
verification.

Verify the result:

```powershell
bidr-models check
```

If only the base package was installed, add the installer dependency with:

```powershell
python -m pip install "bidr-sanitizer[model-install]"
```

See `docs/MODELS.md` for the required directory structure and exact model
identities.

Runtime sanitization does not silently download missing models.

---

## 8. Configure the Model Directory

For the current PowerShell session:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

Verify:

```powershell
python -c "import os; print(os.environ.get('BIDR_MODELS_DIR'))"
```

Expected:

```text
C:\BIDRModels
```

To configure the value for the current Windows user:

```powershell
[Environment]::SetEnvironmentVariable(
    "BIDR_MODELS_DIR",
    "C:\BIDRModels",
    "User"
)
```

Open a new terminal after setting a persistent user environment variable.

The environment variable is optional. If omitted, BIDR Sanitizer uses
its platform-specific external default model directory.

Explicit configuration is recommended for predictable deployments.

The model installer can target a custom directory for one invocation:

```powershell
bidr-models install --models-dir C:\BIDRModels
```

Set `BIDR_MODELS_DIR` to the same directory before running the sanitizer.

---

## 9. Why an ASCII-Only Model Path Is Recommended on Windows

During development, Paddle's native inference runtime failed when model
files were stored below a project path containing the Turkish capital
letter `İ`.

Python could see the files, but Paddle's native layer reported an
existing `inference.json` file as missing.

Using:

```text
C:\BIDRModels
```

resolved the problem.

For Windows installations, an ASCII-only model path is therefore strongly
recommended. The installer rejects a non-ASCII Windows destination before
downloading and explains how to select an ASCII-safe custom path.

---

## 10. Verify PaddleOCR Model Loading

After installing the models:

```powershell
python -c "from bidr_sanitizer.ocr.paddle_adapter import PaddleOCRAdapter; PaddleOCRAdapter(); print('External Paddle models OK')"
```

A successful installation should show model creation from the configured
external model directory and end with:

```text
External Paddle models OK
```

No model should be downloaded during this command when the local
installation is complete.

---

## 11. Run Unit Tests

```powershell
python -m pytest -v
```

Unit tests intentionally avoid requiring the full external model set
where possible.

Integration/manual tests exercise the actual ML models separately.

---

## 12. Run the Public-Tree Safety Check

Before committing or publishing:

```powershell
python scripts\check_public_tree.py
```

A clean tree reports:

```text
=== BIDR SANITIZER PUBLIC TREE CHECK ===

Summary:
  Sensitive directories: 0
  Forbidden binary/model files: 0
  Other problems: 0

PUBLIC TREE CHECK PASSED
```

---

## 13. Verify the CLI

If the project has been installed in editable mode and the console script
is configured:

```powershell
bidr-sanitize --help
```

Alternatively:

```powershell
python -m bidr_sanitizer --help
```

---

## DOC and DOCX Support

DOC and DOCX currently use Microsoft Word through Windows COM automation.

Microsoft Word must therefore be installed and activated.

Word files are not edited in place.

The document is opened read-only and exported to a temporary PDF. That
temporary PDF is then passed through the normal PDF privacy pipeline.

LibreOffice is not required.

---

## PDF Support

PDF rendering uses PDFium through `pypdfium2`.

Sanitized PDFs are reconstructed as new image-only PDFs.

This intentionally sacrifices original text searchability in favor of a
stronger sanitization boundary.

---

## Offline Use

Once Python packages and all required models have been installed, the
normal sanitizer inference path is designed to function without network
access.

For high-assurance environments, disconnect or block network access and
run a complete integration document through the sanitizer.

Normal processing should not display model downloading/fetching behavior.

A local model initialization message such as:

```text
Loading weights: 100%
```

does not by itself mean that the application accessed the network.

---

## Installation Problems

See:

```text
docs/TROUBLESHOOTING.md
```

for known Paddle, Transformers, Word, PDF, and Windows issues.
