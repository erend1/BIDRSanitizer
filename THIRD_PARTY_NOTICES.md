# Third-Party Notices

BIDR Sanitizer is licensed under the Apache License 2.0.

This project depends on third-party software and locally installed
machine-learning models. Third-party components remain subject to their
respective licenses.

BIDR Sanitizer does not bundle the listed model weights in its source
repository or Python distribution.

## Runtime software

### FastAPI

Upstream: fastapi/fastapi
License: MIT

### Uvicorn

Upstream: Kludex/uvicorn
License: BSD-3-Clause

FastAPI uses Starlette and Pydantic, which remain subject to their respective
BSD-3-Clause and MIT licenses.

### React and React DOM

Upstream: facebook/react
License: MIT

### Vite

Upstream: vitejs/vite
License: MIT

Vite, TypeScript, Vitest, Testing Library, and jsdom are used to build and test
the static web client. Their direct and transitive packages remain subject to
the licenses distributed with the locked npm dependencies.

### PaddleOCR

Upstream: PaddlePaddle/PaddleOCR  
License: Apache-2.0

### PaddlePaddle

Upstream: PaddlePaddle/Paddle  
License: Apache-2.0

### GLiNER

Upstream: urchade/GLiNER  
License: Apache-2.0

### Hugging Face Hub

Upstream: huggingface/huggingface_hub
License: Apache-2.0

### Transformers

Upstream: huggingface/transformers  
License: Apache-2.0

### PyTorch

Upstream: pytorch/pytorch

PyTorch uses a BSD-style project license and its distributed packages
contain additional third-party components subject to their respective
licenses. Refer to the license and notice material distributed with the
installed PyTorch package.

### OpenCV / opencv-contrib-python

Upstream: opencv/opencv and opencv/opencv-python

OpenCV 4.5 and later use Apache-2.0. The Python distributions may bundle
additional third-party components with separate notices. Refer to the
license material distributed with the installed wheel.

### pypdfium2 / PDFium

Upstream: pypdfium2-team/pypdfium2

pypdfium2 is distributed under Apache-2.0 / BSD-3-Clause terms.
Binary distributions also contain PDFium and associated dependency
licenses. Refer to the license material distributed with the installed
pypdfium2 package.

### img2pdf

Upstream: josch/img2pdf
License: LGPL-3.0-or-later

img2pdf depends on pikepdf (MPL-2.0) and lxml (BSD-3-Clause). Refer to
the license material distributed with those installed packages for their
complete terms and bundled-component notices.

### ReportLab

Upstream: ReportLab
License: BSD

### pywin32

Upstream: mhammond/pywin32

pywin32 contains multiple upstream license notices. Refer to the license
material distributed with the installed pywin32 package.

## External model assets

The following models are installed separately and are not included in
the BIDR Sanitizer wheel or source repository.

### PP-OCRv5_server_det

Provider: PaddlePaddle  
License: Apache-2.0

### latin_PP-OCRv5_mobile_rec

Provider: PaddlePaddle  
License: Apache-2.0

### gliner_multi_pii-v1

Provider: urchade  
License: Apache-2.0

### mDeBERTa-v3-base tokenizer and configuration assets

Model: microsoft/mdeberta-v3-base
Provider: Microsoft
License: MIT

BIDR Sanitizer installs only the tokenizer files and encoder configuration
required by GLiNER, not the separate mDeBERTa model weights.

### YuNet face detection

Model: face_detection_yunet_2023mar.onnx  
Provider: OpenCV Zoo / Shiqi Yu  
License: MIT

### YOLOS signature detection

Model: mdefrance/yolos-small-signature-detection  
License: Apache-2.0

## Model redistribution

BIDR Sanitizer v0.1.0 does not redistribute model weights.

The explicit `bidr-models install` command retrieves pinned assets directly
from their upstream Hugging Face repositories. Users remain responsible
for complying with the applicable upstream license terms.

The installer does not place model weights in the Python package, source
repository, or wheel.
