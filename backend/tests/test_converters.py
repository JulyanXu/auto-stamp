from pathlib import Path

from app.converters import ConverterRegistry, MacOSOfficeConverter, PdfPassthroughConverter, WindowsOfficeConverter, WpsOfficeConverter


def test_pdf_passthrough_converter_copies_pdf(tmp_path):
    source = tmp_path / "source.pdf"
    target_dir = tmp_path / "out"
    source.write_bytes(b"%PDF-1.4\n%fake\n")

    converter = PdfPassthroughConverter()
    result = converter.convert(source, target_dir)

    assert result.exists()
    assert result.read_bytes() == source.read_bytes()
    assert result.name == "source.pdf"


def test_registry_always_supports_pdf_passthrough():
    registry = ConverterRegistry()

    converter = registry.converter_for(Path("contract.pdf"))

    assert converter.name == "pdf_passthrough"
    assert any(item["name"] == "pdf_passthrough" and item["available"] for item in registry.describe())


def test_registry_returns_no_converter_for_unknown_extension_when_no_optional_engine():
    registry = ConverterRegistry(optional_converters=[])

    assert registry.converter_for(Path("contract.docx")) is None


def test_macos_converter_uses_pages_for_docx_when_word_is_missing():
    converter = MacOSOfficeConverter(
        application_paths={
            "word": None,
            "excel": None,
            "powerpoint": None,
            "pages": Path("/Applications/Pages.app"),
            "numbers": None,
            "keynote": None,
        }
    )

    assert converter.supports(Path("contract.docx"))
    script = converter.script_for(Path("/tmp/contract.docx"), Path("/tmp/contract.pdf"))

    assert 'tell application "/Applications/Pages.app"' in script
    assert 'export front document to POSIX file "/tmp/contract.pdf" as PDF' in script
    assert "format PDF" not in script


def test_windows_converter_exports_docx_with_word_com(tmp_path):
    source = tmp_path / "contract.docx"
    source.write_bytes(b"fake")
    output_dir = tmp_path / "out"
    calls = []

    class FakeDocument:
        def ExportAsFixedFormat(self, output, export_format):
            calls.append(("export", output, export_format))
            Path(output).write_bytes(b"%PDF-1.4\n")

        def Close(self, save_changes):
            calls.append(("close", save_changes))

    class FakeDocuments:
        def Open(self, *args):
            calls.append(("open", *args))
            return FakeDocument()

    class FakeWord:
        Documents = FakeDocuments()

        def __setattr__(self, name, value):
            calls.append(("setattr", name, value))

        def Quit(self):
            calls.append(("quit",))

    converter = WindowsOfficeConverter(system_name="Windows", dispatch_factory=lambda _: FakeWord())

    result = converter.convert(source, output_dir)

    assert result == output_dir / "contract.pdf"
    assert result.exists()
    assert calls == [
        ("setattr", "Visible", False),
        ("setattr", "DisplayAlerts", 0),
        ("setattr", "AutomationSecurity", 3),
        (
            "open",
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
        ),
        ("export", str(result.resolve()), 17),
        ("close", 0),
        ("quit",),
    ]


def test_windows_converter_preserves_primary_word_error_when_close_fails(tmp_path):
    source = tmp_path / "broken.docx"
    source.write_bytes(b"fake")

    class FakeDocument:
        def ExportAsFixedFormat(self, output, export_format):
            raise RuntimeError("export failed")

        def Close(self, save_changes):
            raise RuntimeError("Open.Close")

    class FakeDocuments:
        def Open(self, *args):
            return FakeDocument()

    class FakeWord:
        Documents = FakeDocuments()

        def Quit(self):
            raise RuntimeError("quit failed")

    converter = WindowsOfficeConverter(system_name="Windows", dispatch_factory=lambda _: FakeWord())

    try:
        converter.convert(source, tmp_path / "out")
    except RuntimeError as exc:
        assert str(exc) == "Microsoft Word export failed: export failed"
    else:
        raise AssertionError("Expected conversion to fail.")


def test_wps_converter_exports_docx_with_writer_com(tmp_path):
    source = tmp_path / "contract.docx"
    source.write_bytes(b"fake")
    output_dir = tmp_path / "out"
    calls = []

    class FakeDocument:
        def ExportAsFixedFormat(self, output, export_format):
            calls.append(("export", output, export_format))
            Path(output).write_bytes(b"%PDF-1.4\n")

        def Close(self, save_changes):
            calls.append(("close", save_changes))

    class FakeDocuments:
        def Open(self, path):
            calls.append(("open", path))
            return FakeDocument()

    class FakeWriter:
        Documents = FakeDocuments()

        def __setattr__(self, name, value):
            calls.append(("setattr", name, value))

        def Quit(self):
            calls.append(("quit",))

    converter = WpsOfficeConverter(system_name="Windows", dispatch_factory=lambda prog_id: FakeWriter())

    result = converter.convert(source, output_dir)

    assert result == output_dir / "contract.pdf"
    assert result.exists()
    assert calls == [
        ("setattr", "Visible", False),
        ("setattr", "DisplayAlerts", False),
        ("open", str(source.resolve())),
        ("export", str(result.resolve()), 17),
        ("close", False),
        ("quit",),
    ]


def test_registry_tries_next_converter_when_first_converter_fails(tmp_path):
    source = tmp_path / "contract.docx"
    source.write_bytes(b"fake")
    output_dir = tmp_path / "out"

    class FailingConverter:
        name = "failing"
        label = "Failing converter"
        supported_extensions = {".docx"}
        available = True

        def supports(self, source):
            return True

        def describe(self):
            return {}

        def convert(self, source, output_dir):
            raise RuntimeError("primary failed")

    class WorkingConverter:
        name = "working"
        label = "Working converter"
        supported_extensions = {".docx"}
        available = True

        def supports(self, source):
            return True

        def describe(self):
            return {}

        def convert(self, source, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output = output_dir / "contract.pdf"
            output.write_bytes(b"%PDF-1.4\n")
            return output

    registry = ConverterRegistry(optional_converters=[FailingConverter(), WorkingConverter()])

    result = registry.convert(source, output_dir)

    assert result == output_dir / "contract.pdf"
    assert result.exists()
