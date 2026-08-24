# BIDR Sanitizer Models


BIDR Sanitizer uses several local machine-learning models.


Model weights are intentionally **not stored in this Git repository**.


The normal runtime model root is configured through:


`BIDR_MODELS_DIR`


A recommended Windows installation path is:


`C:\BIDRModels`


Example layout:


```text
C:\BIDRModels\
├── paddleocr\
│   ├── PP-OCRv5_server_det\
│   └── latin_PP-OCRv5_mobile_rec\
├── gliner\
│   └── gliner_multi_pii_v1\
├── yunet\
│   └── face_detection_yunet_2023mar.onnx
└── signature\
    └── yolos-small-signature-detection\
```

## Why models are kept outside the repository

Keeping model weights separate:

prevents very large Git repositories;
allows models to be installed once and shared between environments;
makes offline deployment explicit;
prevents accidental redistribution of third-party model artifacts;
avoids native-library path problems encountered on Windows.

### Local models

BIDR Sanitizer performs model inference locally. Required model files
are not silently downloaded during sanitization.

The default Windows model directory is:

    %LOCALAPPDATA%\BIDRSanitizer\models

Most users do not need to configure a model path. Advanced users may
override the location with `BIDR_MODELS_DIR`.

See `docs/MODELS.md` for setup details.

### Windows path requirement

For maximum compatibility with Paddle's native inference runtime,
use an ASCII-only model path.

Recommended:

C:\BIDRModels

Avoid paths containing characters such as Turkish İ, ş, ğ, etc.

During development, Paddle's Python layer could see models stored under a
Unicode path while Paddle's native inference layer reported the existing
inference.json file as missing.

### Offline operation

After required models have been installed locally, normal document
sanitization is designed to perform inference without downloading models
or sending document contents to hosted AI services.

Missing models should be treated as an installation error rather than
silently downloaded during normal application runtime.

See manifest.json for the model inventory.

A model setup/check utility will be provided under scripts/.