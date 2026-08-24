## 1. What the system needs to detect

Your seven requirements naturally split into three groups:

| Type | Sensitive element | Best detection approach |
|---|---|---|
| Structured text | T.C. Identity No. | Regex + validation/context |
| Structured text | Phone | Regex |
| Structured text | E-mail | Regex |
| Semantic text | Person name | NER model |
| Semantic text | Home address | NER + rules |
| Visual | Human face | Face detector |
| Visual | Signature | Vision/object detector |

That distinction is important.

For example, using an LLM to detect `0532 123 45 67` would actually make the system **less reliable**. Regex is substantially more deterministic for that job.

On the other hand, regex cannot reliably distinguish:

> Prof. Dr. Ahmet Yılmaz

from ordinary Turkish text. That is a Named Entity Recognition problem.

So my preferred architecture is:

```text
                    ┌──────────────────────┐
                    │    INPUT DOCUMENT    │
                    │ PDF/DOCX/TXT/JPG/PNG │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ DOCUMENT NORMALIZER  │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
             TEXT ANALYSIS         IMAGE ANALYSIS
                    │                     │
        ┌───────────┼──────────┐     ┌────┴─────┐
        │           │          │     │          │
       REGEX       NER        OCR   FACES    SIGNATURES
        │           │          │     │          │
        └───────────┴──────────┴─────┴──────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ REDACTION BOX MERGER │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ IRREVERSIBLE MASKING │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ SECOND-PASS CHECKER  │
                    └──────────┬───────────┘
                               │
                               ▼
                         SAFE OUTPUT
```

This can remain quite small as a Python project.

---

# 2. The most important architectural decision

For the **first version**, I strongly recommend that we do **not try to preserve DOCX/PDF internals**.

Instead:

```text
DOCX ─┐
PDF  ─┼──► Render pages ─► Detect ─► Redact pixels ─► NEW PDF
      │
JPG ──┼──► Detect ─► Redacted JPG/PNG
PNG ──┘

TXT ─────► Detect text ─► Replace sensitive strings ─► TXT
```

Why?

Imagine a PDF containing:

> Ahmet Yılmaz  
> 0532 111 22 33

and we simply draw:

```text
██████████████
██████████████
```

over the text.

Visually everything looks fine.

But depending on how the PDF was modified, selecting/copying the text could still reveal:

```text
Ahmet Yılmaz
0532 111 22 33
```

That is exactly the kind of failure we want to eliminate.

PyMuPDF does provide actual PDF redaction operations that physically remove covered text, graphics and pixels when properly applied and saved.  But for our **MVP**, rasterizing the page, modifying the pixels, and constructing a brand-new PDF gives us an even easier security model.

The trade-off is:

**Original PDF → rasterized sanitized PDF**

means the output may be somewhat larger and will no longer have normal selectable text.

For BIDR/KIDR evidence files, I think that is an excellent trade-off.

---

# 3. Text detection

I would use two complementary mechanisms.

### Layer A — deterministic recognizers

These should detect:

```text
T.C. Identity Number
Phone
Email
```

Examples:

```text
12345678901
T.C.: 12345678901
TC Kimlik No: 12345678901

0532 123 45 67
+90 532 123 45 67
0212 555 44 33
+90 (212) 555 44 33

eren@example.com
name.surname@rumeli.edu.tr
```

This is where Microsoft Presidio is attractive.

Presidio is specifically designed around custom recognizers, regex, NER, rule-based detection and checksums, and allows external PII models to be connected. 

So instead of inventing our own entire PII framework, we could define things like:

```text
TR_TCKN
TR_PHONE
EMAIL
PERSON
ADDRESS
```

inside Presidio.

For the Turkish ID recognizer, we can combine:

```text
11-digit pattern
+
TCKN validation logic
+
context words:
"T.C."
"TC"
"TCKN"
"Kimlik No"
"Kimlik Numarası"
```

For compliance-style processing I would bias the detector toward **false positives rather than false negatives**.

Masking an unrelated number is inconvenient.

Missing someone's T.C. number is much worse.

---

# 4. Names and addresses require AI

This is where I would introduce the first actual NLP model.

A particularly interesting option is **GLiNER**.

GLiNER supports zero-shot Named Entity Recognition, is intended to run on CPUs/consumer hardware, can be fine-tuned, and its current project explicitly includes multilingual PII detection. 

We could ask it to detect labels such as:

```python
[
    "person name",
    "residential address"
]
```

or potentially:

```text
person
address
location
```

Then:

```text
Ahmet Mehmet Yılmaz
```

becomes:

```text
██████████████████
```

while:

```text
İstanbul Rumeli Üniversitesi
```

should ideally remain because it is an organization rather than a person.

That's one reason I don't recommend simply masking every capitalized sequence.

---

# 5. OCR

Images and scanned PDFs won't necessarily contain machine-readable text.

For those we need:

```text
IMAGE
   ↓
OCR
   ↓
word + bounding box
```

For example:

```text
OCR result:

"Özge"        → [122, 300, 181, 329]
"İlhan"       → [188, 300, 244, 329]
"0532..."     → [122, 340, 293, 370]
```

Our text detection subsystem says:

```text
Özge İlhan → PERSON
0532...     → PHONE
```

And now we know precisely which pixels to black out.

PaddleOCR is a strong candidate here. Its current toolkit supports 100+ languages and is designed for extracting structured information from PDFs and images. 

So conceptually:

```python
ocr.detect(page_image)

↓

[
    OCRWord(text="Özge", bbox=...),
    OCRWord(text="İlhan", bbox=...),
    OCRWord(text="0532", bbox=...)
]
```

Those coordinates are extremely valuable for our redaction pipeline.

---

# 6. Faces are actually one of the easier requirements

For this I would **not use a huge AI model**.

MediaPipe Face Detector is sufficient for our use case.

It takes an image and returns face locations/bounding boxes and facial key points. 

We don't care:

> Whose face is this?

We only care:

> Is there a face here?

So:

```text
┌─────────────────────────┐
│ Meeting - 14 March      │
│                         │
│    ┌──────┐ ┌──────┐    │
│    │ FACE │ │ FACE │    │
│    └──────┘ └──────┘    │
│                         │
└─────────────────────────┘
```

becomes:

```text
┌─────────────────────────┐
│ Meeting - 14 March      │
│                         │
│    ████████ ████████    │
│    ████████ ████████    │
│                         │
└─────────────────────────┘
```

I would additionally enlarge every detected face box by perhaps roughly 10–20% so that forehead, ears, chin, etc. aren't partially exposed.

---

# 7. Signatures are the hardest requirement

This is the only part where I would initially experiment.

Signatures vary enormously:

```text
normal handwritten signature
initials
scanned wet signature
black signature
blue signature
signature over stamp
very small signature
digital handwritten signature
```

A traditional face detector has a clearly defined object to detect.

A signature doesn't.

For the first prototype I would try an **open-vocabulary object detector such as Grounding DINO** with prompts along the lines of:

```text
handwritten signature.
human signature.
wet ink signature.
signed name.
```

Grounding DINO accepts an image plus text and produces candidate bounding boxes corresponding to concepts supplied in the textual prompt. It also supports CPU-only operation, although GPU inference would naturally be faster. 

So our initial model stack might be:

```text
OCR              → PaddleOCR
Text PII         → Presidio
Name/address NER → GLiNER
Faces            → MediaPipe
Signatures       → Grounding DINO
```

That's already quite powerful while remaining completely local.

If Grounding DINO's signature recall turns out insufficient, I would then collect perhaps several hundred signature examples from **synthetic/non-sensitive documents** and fine-tune a small dedicated detector.

But I wouldn't start there.

---

# 8. Everything should run locally

This matters a lot.

I would design version 1 such that:

```text
NO document
NO OCR text
NO photograph
NO name
NO identity number
```

ever gets sent to:

```text
OpenAI API
Google API
Azure AI
AWS
HuggingFace hosted inference
etc.
```

The models should be downloaded once and executed locally.

That gives us:

```text
Evidence
   ↓
Your computer/server
   ↓
Local models
   ↓
Sanitized evidence
```

instead of:

```text
Evidence → external server → analysis → result
```

That substantially simplifies the privacy architecture.

It doesn't by itself constitute a legal determination of KVKK compliance, but technically it is a much more appropriate default for sensitive institutional documents.

---

# 9. I would introduce a `strict` philosophy

Because this is compliance-related evidence, our optimization target should be:

```text
RECALL >>> PRECISION
```

In other words:

> When uncertain, redact.

For example, suppose the NER model gives:

```text
PERSON:
"Mehmet Kaya"    confidence=0.97
"Rumeli"         confidence=0.41
"Dr. Ayşe Demir" confidence=0.84
```

A normal NLP application might use:

```text
threshold = 0.8
```

But for our sanitizer we might choose:

```text
threshold = 0.55
```

and accept a few extra boxes.

Same with faces and signatures.

A little over-redaction is acceptable.

A privacy leak isn't.

---

# 10. Every redaction should have margin

Suppose OCR reports:

```text
x1=100
y1=200
x2=250
y2=225
```

I don't want our box to be exactly:

```text
[100, 200, 250, 225]
```

I'd expand it:

```text
[95, 195, 255, 230]
```

Conceptually:

```text
Detected:
        ┌─────────────┐
        │ Ahmet Yılmaz│
        └─────────────┘

Redacted:
    █████████████████████
    █████████████████████
```

This prevents tiny letter edges from surviving OCR or rasterization.

---

# 11. Blur should not be used

For these documents I recommend only:

```text
solid black rectangle
```

or possibly:

```text
solid white rectangle
```

Not:

```text
blur
pixelation
semi-transparent overlay
```

Blur is still image information.

We don't need aesthetically pleasing anonymization.

We want destruction of the information.

So internally our operation should simply be:

```python
image.rectangle(bbox, fill="black")
```

on the actual page pixels.

---

# 12. The second-pass verifier is essential

This is one of the features I would consider **mandatory**, despite keeping the project simple.

After producing:

```text
evidence_SAFE.pdf
```

we process it **again from scratch**.

```text
SAFE PDF
   ↓
OCR again
   ↓
PII detector again
   ↓
Face detector again
   ↓
Signature detector again
```

The result should be:

```text
TCKN       : 0
PHONE      : 0
EMAIL      : 0
PERSON     : 0
ADDRESS    : 0
FACE       : 0
SIGNATURE  : 0
```

If something is found:

```text
STATUS = REVIEW_REQUIRED
```

rather than:

```text
STATUS = SUCCESS
```

This addresses an important limitation of automated privacy detection: even Presidio itself explicitly warns that automated detection cannot guarantee that every piece of sensitive information will be found and recommends additional protections. 

Our verification pass is one of those protections.

---

# 13. I also want an audit report

For every processed document, something like this:

```text
Input:
A.4.1_Kurul_Karari.pdf

Pages:
7

Detections:
TCKN       3
PHONE      1
EMAIL      4
PERSON     12
ADDRESS    0
FACE       5
SIGNATURE  7

Total redactions:
32

Verification pass:
TCKN       0
PHONE      0
EMAIL      0
PERSON     0
ADDRESS    0
FACE       0
SIGNATURE  0

STATUS:
PASSED
```

But importantly **do not put the original PII in the log**.

Bad:

```text
Detected name: Ahmet Yılmaz
Detected phone: 0532...
```

Good:

```text
PERSON page=2 bbox=(...)
PHONE page=3 bbox=(...)
```

Otherwise we'd just create a second privacy problem in our logs.

---

# 14. Metadata must also be handled

There is another less obvious category.

Suppose we sanitize `Evidence.docx`, but its Word metadata says:

```text
Author:
Mehmet Yılmaz

Last Modified By:
Ayşe Demir
```

That's also identifying information.

DOCX core properties can contain fields including author and last-modified-by. 

So before producing an output we should remove metadata such as:

```text
author
creator
last_modified_by
company
comments
EXIF GPS
camera metadata
```

This further supports my recommendation that the safest MVP is:

```text
Original document
       ↓
render
       ↓
sanitize raster representation
       ↓
build completely new PDF
```

rather than modifying the original file.

---

# 15. Proposed project structure

When we start implementing, I'd keep it approximately this simple:

```text
bidr_sanitizer/
│
├── main.py
│
├── config.py
│
├── models/
│
├── detectors/
│   ├── tckn.py
│   ├── phone.py
│   ├── email.py
│   ├── ner.py
│   ├── face.py
│   └── signature.py
│
├── document/
│   ├── pdf.py
│   ├── image.py
│   ├── docx.py
│   └── text.py
│
├── redaction/
│   ├── bbox.py
│   └── redact.py
│
├── verification/
│   └── verifier.py
│
└── tests/
```

But we don't actually need to create all of this immediately.

---

# 16. I suggest developing it incrementally

The sequence I would follow is:

1. **PNG/JPEG sanitizer first.** Implement OCR + TCKN/phone/email + names + face detection + black-box redaction.
2. Add the **verification pass**.
3. Add **PDF support** by rendering each page → sanitizing it → rebuilding a completely new sanitized PDF.
4. Add **DOCX input** by rendering DOCX → PDF → using exactly the same pipeline.
5. Add **signature detection** and tune thresholds using representative BIDR/KIDR evidence.
6. Add address NER and improve Turkish person-name detection.
7. Add batch processing such as `python sanitize.py ./evidences/ --output ./safe/`.
8. Finally add an optional preview/review mode before export.

This sequence gives us a functioning system very early rather than building six file handlers before we know whether our detection quality is acceptable.

---

## The architecture I recommend

So, putting everything together, our eventual command could be as simple as:

```bash
python sanitize.py evidence.pdf
```

producing:

```text
output/
├── evidence_REDACTED.pdf
└── evidence_REDACTION_REPORT.json
```

with a pipeline like:

```text
                 BIDR / KIDR Evidence
                          │
                          ▼
                 Local Document Loader
                          │
                          ▼
                    Page Rendering
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
     PaddleOCR                       MediaPipe
          │                               │
          ▼                               ▼
     Text + boxes                     Face boxes
          │
     ┌────┴───────────────┐
     ▼                    ▼
 Presidio               GLiNER
 │    │    │             │    │
TC  Phone Email        Name Address
     │
     └─────────────┬───────────────────────┐
                   │                       │
                   │                Grounding DINO
                   │                       │
                   │                 Signature boxes
                   │                       │
                   └──────────┬────────────┘
                              ▼
                       Merge/expand boxes
                              ▼
                       BLACK REDACTION
                              ▼
                       Brand-new output
                              ▼
                       Run everything again
                              │
                    ┌─────────┴────────┐
                    ▼                  ▼
                  PASS           REVIEW REQUIRED
```

And one principle should govern the entire project:

> **AI finds where sensitive information probably is; deterministic code actually destroys it.**

That separation will make the solution considerably safer, easier to test, and easier to maintain.

For the next step, I would start with the **core data model and PNG/JPEG prototype**, because once `Detection → BoundingBox → Redaction → Verification` is correct, PDF and DOCX become mostly input/output adapters rather than entirely separate problems.