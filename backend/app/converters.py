import os
import platform
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
    ".odp",
}


class Converter(ABC):
    name: str
    label: str
    supported_extensions: set[str]

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @property
    def unavailable_reason(self) -> str | None:
        return None if self.available else "Converter is not available in this environment."

    def supports(self, source: Path) -> bool:
        return source.suffix.lower() in self.supported_extensions

    @abstractmethod
    def convert(self, source: Path, output_dir: Path) -> Path:
        raise NotImplementedError

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "available": self.available,
            "supported_extensions": sorted(self.supported_extensions),
            "unavailable_reason": self.unavailable_reason,
        }


class PdfPassthroughConverter(Converter):
    name = "pdf_passthrough"
    label = "PDF passthrough"
    supported_extensions = {".pdf"}

    @property
    def available(self) -> bool:
        return True

    def convert(self, source: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{source.stem}.pdf"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return target


class LibreOfficeConverter(Converter):
    name = "libreoffice"
    label = "LibreOffice headless"
    supported_extensions = OFFICE_EXTENSIONS

    def __init__(self) -> None:
        self.binary = shutil.which("soffice") or shutil.which("libreoffice")

    @property
    def available(self) -> bool:
        return self.binary is not None

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return "LibreOffice is not installed or not found in PATH."

    def convert(self, source: Path, output_dir: Path) -> Path:
        if not self.binary:
            raise RuntimeError(self.unavailable_reason)
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.binary,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(source),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "LibreOffice conversion failed."
            raise RuntimeError(detail)
        output = output_dir / f"{source.stem}.pdf"
        if not output.exists():
            raise RuntimeError("LibreOffice did not produce a PDF output file.")
        return output


class WindowsOfficeConverter(Converter):
    name = "windows_office"
    label = "Microsoft Office COM export"
    supported_extensions = OFFICE_EXTENSIONS

    def __init__(self, system_name: str | None = None, dispatch_factory=None) -> None:
        self.system_name = system_name or platform.system()
        self.dispatch_factory = dispatch_factory

    @property
    def available(self) -> bool:
        if self.system_name != "Windows":
            return False
        if self.dispatch_factory is not None:
            return True
        try:
            import win32com.client  # noqa: F401
        except Exception:
            return False
        return True

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return "Microsoft Office COM automation requires Windows, Office, and pywin32."

    def convert(self, source: Path, output_dir: Path) -> Path:
        if not self.available:
            raise RuntimeError(self.unavailable_reason)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{source.stem}.pdf"
        ext = source.suffix.lower()
        if ext in {".doc", ".docx", ".rtf", ".odt"}:
            self._convert_word(source, output)
        elif ext in {".xls", ".xlsx", ".ods"}:
            self._convert_excel(source, output)
        elif ext in {".ppt", ".pptx", ".odp"}:
            self._convert_powerpoint(source, output)
        else:
            raise RuntimeError(f"Microsoft Office cannot export {source.suffix or 'this file type'} to PDF.")
        if not output.exists():
            raise RuntimeError("Microsoft Office export did not produce a PDF output file.")
        return output

    def _dispatch(self, app_name: str):
        if self.dispatch_factory is not None:
            return self.dispatch_factory(app_name)
        import win32com.client  # noqa: PLC0415

        return win32com.client.DispatchEx(app_name)

    def _convert_word(self, source: Path, output: Path) -> None:
        app = self._dispatch("Word.Application")
        document = None
        error: Exception | None = None
        try:
            app.Visible = False
            app.DisplayAlerts = 0
            app.AutomationSecurity = 3
            document = app.Documents.Open(
                str(source.resolve()),
                False,
                True,
                False,
                "",
                "",
                False,
                "",
                "",
                0,
                False,
                False,
                False,
                False,
                True,
                False,
            )
            document.ExportAsFixedFormat(str(output.resolve()), 17)
        except Exception as exc:
            error = exc
        finally:
            if document is not None:
                self._best_effort(document.Close, 0)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"Microsoft Word export failed: {error}") from error

    def _convert_excel(self, source: Path, output: Path) -> None:
        app = self._dispatch("Excel.Application")
        workbook = None
        error: Exception | None = None
        try:
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(str(source.resolve()), ReadOnly=True)
            workbook.ExportAsFixedFormat(0, str(output.resolve()))
        except Exception as exc:
            error = exc
        finally:
            if workbook is not None:
                self._best_effort(workbook.Close, False)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"Microsoft Excel export failed: {error}") from error

    def _convert_powerpoint(self, source: Path, output: Path) -> None:
        app = self._dispatch("PowerPoint.Application")
        presentation = None
        error: Exception | None = None
        try:
            app.DisplayAlerts = 1
            presentation = app.Presentations.Open(str(source.resolve()), WithWindow=False)
            presentation.SaveAs(str(output.resolve()), 32)
        except Exception as exc:
            error = exc
        finally:
            if presentation is not None:
                self._best_effort(presentation.Close)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"Microsoft PowerPoint export failed: {error}") from error

    def _best_effort(self, func, *args) -> None:
        try:
            func(*args)
        except Exception:
            pass


class WpsOfficeConverter(WindowsOfficeConverter):
    name = "wps_office"
    label = "WPS Office COM export"

    writer_prog_ids = ("KWPS.Application", "kwps.Application", "WPS.Application")
    spreadsheet_prog_ids = ("KET.Application", "ket.Application", "ET.Application")
    presentation_prog_ids = ("KWPP.Application", "kwpp.Application", "WPP.Application")

    @property
    def available(self) -> bool:
        if self.system_name != "Windows":
            return False
        if self.dispatch_factory is not None:
            return True
        try:
            import win32com.client  # noqa: F401
        except Exception:
            return False
        return any(
            self._prog_id_registered(prog_id)
            for prog_id in self.writer_prog_ids + self.spreadsheet_prog_ids + self.presentation_prog_ids
        )

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return "WPS Office COM automation is not registered or pywin32 is unavailable."

    def _convert_word(self, source: Path, output: Path) -> None:
        app = self._dispatch_first(self.writer_prog_ids)
        document = None
        error: Exception | None = None
        try:
            app.Visible = False
            app.DisplayAlerts = False
            document = app.Documents.Open(str(source.resolve()))
            document.ExportAsFixedFormat(str(output.resolve()), 17)
        except Exception as exc:
            error = exc
        finally:
            if document is not None:
                self._best_effort(document.Close, False)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"WPS Writer export failed: {error}") from error

    def _convert_excel(self, source: Path, output: Path) -> None:
        app = self._dispatch_first(self.spreadsheet_prog_ids)
        workbook = None
        error: Exception | None = None
        try:
            app.Visible = False
            app.DisplayAlerts = False
            workbook = app.Workbooks.Open(str(source.resolve()))
            workbook.ExportAsFixedFormat(0, str(output.resolve()))
        except Exception as exc:
            error = exc
        finally:
            if workbook is not None:
                self._best_effort(workbook.Close, False)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"WPS Spreadsheets export failed: {error}") from error

    def _convert_powerpoint(self, source: Path, output: Path) -> None:
        app = self._dispatch_first(self.presentation_prog_ids)
        presentation = None
        error: Exception | None = None
        try:
            presentation = app.Presentations.Open(str(source.resolve()), WithWindow=False)
            presentation.SaveAs(str(output.resolve()), 32)
        except Exception as exc:
            error = exc
        finally:
            if presentation is not None:
                self._best_effort(presentation.Close)
            self._best_effort(app.Quit)
        if error is not None:
            raise RuntimeError(f"WPS Presentation export failed: {error}") from error

    def _dispatch_first(self, prog_ids: tuple[str, ...]):
        errors: list[str] = []
        for prog_id in prog_ids:
            try:
                return self._dispatch(prog_id)
            except Exception as exc:
                errors.append(f"{prog_id}: {exc}")
        raise RuntimeError("; ".join(errors) or "No WPS COM application could be created.")

    def _prog_id_registered(self, prog_id: str) -> bool:
        try:
            import winreg  # noqa: PLC0415

            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id):
                return True
        except Exception:
            return False


class MacOSOfficeConverter(Converter):
    name = "macos_office"
    label = "macOS Office AppleScript export"
    supported_extensions = OFFICE_EXTENSIONS

    def __init__(self, application_paths: dict[str, Path | None] | None = None) -> None:
        self.application_paths = application_paths or {
            "word": Path("/Applications/Microsoft Word.app"),
            "excel": Path("/Applications/Microsoft Excel.app"),
            "powerpoint": Path("/Applications/Microsoft PowerPoint.app"),
            "pages": Path("/Applications/Pages.app"),
            "numbers": Path("/Applications/Numbers.app"),
            "keynote": Path("/Applications/Keynote.app"),
        }

    @property
    def available(self) -> bool:
        if platform.system() != "Darwin":
            return False
        return any(self._app_available(app_key) for app_key in self.application_paths)

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return "No supported macOS Office/iWork application was found."

    def convert(self, source: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{source.stem}.pdf"
        script = self.script_for(source, output)
        self._run_osascript(script)
        if not output.exists():
            raise RuntimeError("macOS Office export did not produce a PDF output file.")
        return output

    def supports(self, source: Path) -> bool:
        if platform.system() != "Darwin":
            return False
        ext = source.suffix.lower()
        if ext in {".doc", ".docx", ".rtf", ".odt"}:
            return self._app_available("word") or self._app_available("pages")
        if ext in {".xls", ".xlsx", ".ods"}:
            return self._app_available("excel") or self._app_available("numbers")
        if ext in {".ppt", ".pptx", ".odp"}:
            return self._app_available("powerpoint") or self._app_available("keynote")
        return False

    def script_for(self, source: Path, output: Path) -> str:
        ext = source.suffix.lower()
        if ext in {".doc", ".docx", ".rtf", ".odt"}:
            if self._app_available("word"):
                return self._word_script(source, output)
            if self._app_available("pages"):
                return self._iwork_script(str(self.application_paths["pages"]), source, output)
        if ext in {".xls", ".xlsx", ".ods"}:
            if self._app_available("excel"):
                return self._excel_script(source, output)
            if self._app_available("numbers"):
                return self._iwork_script(str(self.application_paths["numbers"]), source, output)
        if ext in {".ppt", ".pptx", ".odp"}:
            if self._app_available("powerpoint"):
                return self._powerpoint_script(source, output)
            if self._app_available("keynote"):
                return self._iwork_script(str(self.application_paths["keynote"]), source, output)
        raise RuntimeError(f"No macOS application is available to export {source.suffix or 'this file type'} to PDF.")

    def _app_available(self, app_key: str) -> bool:
        path = self.application_paths.get(app_key)
        return bool(path and path.exists())

    def _run_osascript(self, script: str) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            script_path = handle.name
        try:
            result = subprocess.run(["osascript", script_path], capture_output=True, text=True, check=False, timeout=120)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "AppleScript conversion failed."
                raise RuntimeError(detail)
        finally:
            Path(script_path).unlink(missing_ok=True)

    def _word_script(self, source: Path, output: Path) -> str:
        return f'''
        tell application "Microsoft Word"
          set inputFile to POSIX file "{source}"
          set outputFile to POSIX file "{output}"
          open inputFile
          save as active document file name outputFile file format format PDF
          close active document saving no
        end tell
        '''

    def _excel_script(self, source: Path, output: Path) -> str:
        return f'''
        tell application "Microsoft Excel"
          set inputFile to POSIX file "{source}"
          open inputFile
          save active workbook in POSIX file "{output}" as PDF file format
          close active workbook saving no
        end tell
        '''

    def _powerpoint_script(self, source: Path, output: Path) -> str:
        return f'''
        tell application "Microsoft PowerPoint"
          set inputFile to POSIX file "{source}"
          open inputFile
          save active presentation in "{output}" as save as PDF
          close active presentation
        end tell
        '''

    def _iwork_script(self, app_path: str, source: Path, output: Path) -> str:
        return f'''
        tell application "{app_path}"
          set docsBefore to count of documents
          open POSIX file "{source}"
          set waitCount to 0
          repeat while (count of documents) = docsBefore and waitCount < 30
            delay 1
            set waitCount to waitCount + 1
          end repeat
          delay 2
          export front document to POSIX file "{output}" as PDF
          close front document saving no
        end tell
        '''


class ExternalConverter(Converter):
    name = "external"
    label = "External converter command"
    supported_extensions = OFFICE_EXTENSIONS

    def __init__(self) -> None:
        self.command = os.getenv("AUTOSTAMP_EXTERNAL_CONVERTER")

    @property
    def available(self) -> bool:
        return bool(self.command)

    @property
    def unavailable_reason(self) -> str | None:
        if self.available:
            return None
        return "AUTOSTAMP_EXTERNAL_CONVERTER is not configured."

    def convert(self, source: Path, output_dir: Path) -> Path:
        if not self.command:
            raise RuntimeError(self.unavailable_reason)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{source.stem}.pdf"
        command = self.command.format(input=str(source), output=str(output), output_dir=str(output_dir))
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False, timeout=180)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "External conversion failed."
            raise RuntimeError(detail)
        if not output.exists():
            raise RuntimeError("External converter did not produce the expected PDF output.")
        return output


class ConverterRegistry:
    def __init__(self, optional_converters: list[Converter] | None = None) -> None:
        self.converters: list[Converter] = [PdfPassthroughConverter()]
        if optional_converters is None:
            self.converters.extend(
                [
                    ExternalConverter(),
                    LibreOfficeConverter(),
                    MacOSOfficeConverter(),
                    WindowsOfficeConverter(),
                    WpsOfficeConverter(),
                ]
            )
        else:
            self.converters.extend(optional_converters)

    def describe(self) -> list[dict]:
        return [converter.describe() for converter in self.converters]

    def converter_for(self, source: Path) -> Converter | None:
        converters = self.converters_for(source)
        return converters[0] if converters else None

    def converters_for(self, source: Path) -> list[Converter]:
        return [converter for converter in self.converters if converter.available and converter.supports(source)]

    def convert(self, source: Path, output_dir: Path) -> Path:
        errors: list[str] = []
        for converter in self.converters:
            if converter.available and converter.supports(source):
                try:
                    return converter.convert(source, output_dir)
                except Exception as exc:
                    errors.append(f"{converter.label}: {exc}")
        if errors:
            raise RuntimeError(f"All available converters failed for {source.suffix or 'this file type'}: " + " | ".join(errors))
        raise RuntimeError(f"No available converter for {source.suffix or 'this file type'}.")
