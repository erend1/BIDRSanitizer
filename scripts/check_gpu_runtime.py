from __future__ import annotations

import argparse
import os
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check BIDR Sanitizer's PaddleOCR and PyTorch GPU runtimes "
            "without printing document text."
        )
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Optional local image for a one-pass OCR smoke test.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="BIDR inference device setting (default: auto).",
    )
    parser.add_argument(
        "--full-analysis",
        action="store_true",
        help="Initialize every detector and analyze --image once.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    os.environ["BIDR_INFERENCE_DEVICE"] = args.device

    from bidr_sanitizer.inference_device import resolve_torch_device
    from bidr_sanitizer.ocr.paddle_adapter import PaddleOCRAdapter

    with PaddleOCRAdapter() as ocr:
        import torch

        torch_device = resolve_torch_device(torch)
        probe = torch.ones(1, device=torch_device) + 1
        if float(probe.item()) != 2.0:
            raise RuntimeError("PyTorch device calculation returned a bad result.")

        print(f"PaddleOCR device: {ocr.device}")
        print(f"PyTorch device: {torch_device}")
        if torch_device.startswith("cuda"):
            print(f"PyTorch GPU: {torch.cuda.get_device_name(torch_device)}")

        if args.image is not None:
            items = ocr.recognize(args.image)
            print(f"OCR smoke detections: {len(items)}")

    if args.full_analysis:
        if args.image is None:
            raise ValueError("--full-analysis requires --image.")

        from bidr_sanitizer.engine import OfflineImageSanitizer

        with OfflineImageSanitizer() as sanitizer:
            plan = sanitizer.analyze_for_review(args.image)
            print(f"Full analysis detections: {len(plan.regions)}")

    print("Inference runtime check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
