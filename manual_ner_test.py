from bidr_sanitizer.recognizers.semantic.gliner_adapter import (
    GLiNERPIIRecognizer,
)


recognizer = GLiNERPIIRecognizer()


samples = [
    "Toplantıya Prof. Dr. Ahmet Yılmaz katılmıştır.",

    "Belge Ayşe Demir tarafından hazırlanmıştır.",

    (
        "İkamet adresi Atatürk Mahallesi "
        "Gül Sokak No: 12 Daire: 4 "
        "Maltepe İstanbul'dur."
    ),

    "İstanbul Rumeli Üniversitesi toplantısı yapılmıştır.",

    "Mühendislik ve Doğa Bilimleri Fakültesi Dekanlığı",

    "İstanbul adresindeki toplantıya katılım sağlandı.",
]


for index, text in enumerate(
    samples,
    start=1,
):
    print()
    print(f"--- SAMPLE {index} ---")

    detections = recognizer.recognize(
        text
    )

    print(
        "Detection count:",
        len(detections),
    )

    for detection in detections:
        print(
            detection.detection_type.value,
            detection.span,
            round(
                detection.confidence,
                4,
            ),
        )