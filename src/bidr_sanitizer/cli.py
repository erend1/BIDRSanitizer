from __future__ import annotations


import sys
import argparse
from pathlib import Path
from collections.abc import (
    Callable,
    Sequence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidr-sanitize",
        description=(
            "Offline-first document privacy sanitizer."
        ),
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input file or directory.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file or directory.",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help=(
            "Recursively process supported files "
            "when the input is a directory."
        ),
    )

    return parser


def _load_service():
    try:
        from bidr_sanitizer.service import (
            BIDRSanitizerService,
        )
    except ModuleNotFoundError as exc:
        missing = (
            exc.name
            or "an optional runtime dependency"
        )

        raise RuntimeError(
            "\n"
            "BIDR Sanitizer's complete runtime "
            "dependencies are not installed.\n\n"
            f"Missing dependency: {missing}\n\n"
            "Install the complete runtime with:\n\n"
            '    python -m pip install '
            '"bidr-sanitizer[all]"\n'
        ) from exc

    return BIDRSanitizerService


def _resolve_output_directory(
    input_path: Path,
    requested_output: Path | None,
) -> Path:
    if requested_output is not None:
        return (
            requested_output
            .expanduser()
            .resolve()
        )

    if input_path.is_file():
        return input_path.parent

    return (
        input_path.parent
        / f"{input_path.name}_REDACTED"
    )


def collect_files(
    input_path: Path,
    *,
    recursive: bool,
    is_supported: Callable[[Path], bool],
) -> list[Path]:

    if input_path.is_file():
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(
            input_path
        )

    iterator = (
        input_path.rglob("*")
        if recursive
        else input_path.glob("*")
    )

    return sorted(
        path
        for path in iterator
        if (
            path.is_file()
            and is_supported(path)
        )
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = (
        args.input
        .expanduser()
        .resolve()
    )

    requested_output = (
        args.output
        .expanduser()
        .resolve()
        if args.output is not None
        else None
    )

    output_directory = (
        _resolve_output_directory(
            input_path,
            requested_output,
        )
    )

    try:
        service_type = _load_service()
    except RuntimeError as exc:
        parser.error(str(exc))

    service = service_type()

    try:
        files = collect_files(
            input_path,
            recursive=args.recursive,
            is_supported=service.is_supported,
        )

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    if not files:
        print(
            "No supported files found."
        )
        return 0

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Files to process: "
        f"{len(files)}"
    )

    passed_count = 0
    failed_count = 0

    for index, input_file in enumerate(
        files,
        start=1,
    ):

        file_output_path = (
            service.default_output_path(
                input_file,
                output_directory,
            )
        )

        print(
            f"[{index}/{len(files)}] "
            f"{input_file.name}"
        )

        try:
            result = (
                service.sanitize_file(
                    input_file,
                    file_output_path,
                )
            )

            if result.passed:
                passed_count += 1

                print(
                    "  PASSED"
                )

                print(
                    "  ->",
                    file_output_path,
                )

            else:
                failed_count += 1

                print(
                    "  REVIEW REQUIRED"
                )

        except Exception as exc:
            failed_count += 1

            print(
                "  ERROR:",
                exc,
            )

        print()

    print(
        "=== SUMMARY ==="
    )

    print(
        "Passed:",
        passed_count,
    )

    print(
        "Failed / review required:",
        failed_count,
    )

    return (
        0
        if failed_count == 0
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )