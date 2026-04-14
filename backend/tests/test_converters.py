from pathlib import Path

from app.converters import ConverterRegistry, MacOSOfficeConverter, PdfPassthroughConverter


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
