from __future__ import annotations

from pathlib import Path


SUPPORTED_WORD_EXTENSIONS = {
    ".doc",
    ".docx",
}


# Word constants.
WD_EXPORT_FORMAT_PDF = 17
WD_EXPORT_OPTIMIZE_FOR_PRINT = 0
WD_EXPORT_ALL_DOCUMENT = 0
WD_EXPORT_DOCUMENT_CONTENT = 0
WD_DO_NOT_SAVE_CHANGES = 0

# Office constant:
# msoAutomationSecurityForceDisable
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3


class WordCOMConverter:
    """
    Convert DOC/DOCX to PDF using locally installed Microsoft Word.

    Intended for interactive/local Windows workstation use.
    """

    def convert_to_pdf(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ) -> Path:

        input_path = Path(
            input_path
        ).resolve()

        output_path = Path(
            output_path
        ).resolve()

        if not input_path.exists():
            raise FileNotFoundError(
                input_path
            )

        if (
            input_path.suffix.lower()
            not in SUPPORTED_WORD_EXTENSIONS
        ):
            raise ValueError(
                "Supported Word formats are "
                ".doc and .docx."
            )

        if (
            input_path
            == output_path
        ):
            raise ValueError(
                "Input and output paths "
                "must be different."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        import pythoncom
        import win32com.client
        import pywintypes

        pythoncom.CoInitialize()

        word = None
        document = None

        try:
            try:
                word = (
                    win32com.client.DispatchEx(
                        "Word.Application"
                    )
                )

            except pywintypes.com_error as exc:
                raise RuntimeError(
                    "Microsoft Word could not "
                    "be started. Make sure "
                    "Microsoft Word is installed "
                    "and activated."
                ) from exc

            word.Visible = False
            word.DisplayAlerts = 0

            # Important for DOC files in particular:
            # disable macro execution during automation.
            word.AutomationSecurity = (
                MSO_AUTOMATION_SECURITY_FORCE_DISABLE
            )

            try:
                document = (
                    word.Documents.Open(
                        FileName=str(
                            input_path
                        ),
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        Visible=False,
                        OpenAndRepair=False,
                        NoEncodingDialog=True,
                    )
                )

            except pywintypes.com_error as exc:
                raise RuntimeError(
                    "Microsoft Word could not "
                    f"open: {input_path}"
                ) from exc

            document.ExportAsFixedFormat(
                OutputFileName=str(
                    output_path
                ),
                ExportFormat=(
                    WD_EXPORT_FORMAT_PDF
                ),
                OpenAfterExport=False,
                OptimizeFor=(
                    WD_EXPORT_OPTIMIZE_FOR_PRINT
                ),
                Range=(
                    WD_EXPORT_ALL_DOCUMENT
                ),
                Item=(
                    WD_EXPORT_DOCUMENT_CONTENT
                ),

                # We do not need Word metadata in
                # the temporary PDF.
                IncludeDocProps=False,

                # Do not intentionally propagate IRM
                # metadata into the intermediate PDF.
                KeepIRM=False,

                CreateBookmarks=0,
                DocStructureTags=False,
                BitmapMissingFonts=True,
                UseISO19005_1=False,
            )

            if not output_path.exists():
                raise RuntimeError(
                    "Word completed without "
                    "creating the expected PDF."
                )

            return output_path

        finally:
            if document is not None:
                try:
                    document.Close(
                        SaveChanges=(
                            WD_DO_NOT_SAVE_CHANGES
                        )
                    )
                except Exception:
                    pass

            if word is not None:
                try:
                    word.Quit(
                        SaveChanges=(
                            WD_DO_NOT_SAVE_CHANGES
                        )
                    )
                except Exception:
                    pass

            pythoncom.CoUninitialize()