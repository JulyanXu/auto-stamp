import fitz

from app.models import StampSettings
from app.stamping import stamp_pdf


def test_stamp_pdf_applies_stamp_to_selected_pages(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    stamp_png = tmp_path / "stamp.png"
    output_pdf = tmp_path / "output.pdf"

    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.new_page(width=200, height=200)
    doc.save(source_pdf)
    doc.close()

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 1)
    pixmap.clear_with(0xFF0000)
    pixmap.save(stamp_png)

    settings = StampSettings(
        x_ratio=0.25,
        y_ratio=0.25,
        width_ratio=0.25,
        height_ratio=0.25,
        page_rule="first",
    )

    stamp_pdf(source_pdf, stamp_png, output_pdf, settings)

    stamped = fitz.open(output_pdf)
    assert len(stamped) == 2
    assert len(stamped[0].get_images(full=True)) == 1
    assert len(stamped[1].get_images(full=True)) == 0
    stamped.close()


def test_stamp_pdf_preserves_page_size(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    stamp_png = tmp_path / "stamp.png"
    output_pdf = tmp_path / "output.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.new_page(width=842, height=595)
    doc.save(source_pdf)
    doc.close()

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), 1)
    pixmap.clear_with(0xFF0000)
    pixmap.save(stamp_png)

    settings = StampSettings(
        x_ratio=0.7,
        y_ratio=0.7,
        width_ratio=0.2,
        height_ratio=0.1,
        page_rule="all",
    )

    stamp_pdf(source_pdf, stamp_png, output_pdf, settings)

    source = fitz.open(source_pdf)
    stamped = fitz.open(output_pdf)
    try:
        assert [page.rect for page in stamped] == [page.rect for page in source]
    finally:
        source.close()
        stamped.close()


def test_stamp_pdf_can_use_fixed_stamp_size_in_mm(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    stamp_png = tmp_path / "stamp.png"
    output_pdf = tmp_path / "output.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(source_pdf)
    doc.close()

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), 1)
    pixmap.clear_with(0xFF0000)
    pixmap.save(stamp_png)

    settings = StampSettings(
        x_ratio=0.1,
        y_ratio=0.1,
        width_ratio=0.5,
        height_ratio=0.5,
        width_mm=40,
        height_mm=20,
        page_rule="first",
    )

    stamp_pdf(source_pdf, stamp_png, output_pdf, settings)

    stamped = fitz.open(output_pdf)
    try:
        image_rects = stamped[0].get_image_rects(stamped[0].get_images(full=True)[0][0])
        assert len(image_rects) == 1
        assert round(image_rects[0].width, 1) == round(40 * 72 / 25.4, 1)
        assert round(image_rects[0].height, 1) == round(20 * 72 / 25.4, 1)
    finally:
        stamped.close()


def test_stamp_pdf_preserves_stamp_image_aspect_ratio(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    stamp_png = tmp_path / "wide_stamp.png"
    output_pdf = tmp_path / "output.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(source_pdf)
    doc.close()

    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 40), 1)
    pixmap.clear_with(0xFF0000)
    pixmap.save(stamp_png)

    settings = StampSettings(
        x_ratio=0.1,
        y_ratio=0.1,
        width_mm=40,
        height_mm=40,
        page_rule="first",
    )

    stamp_pdf(source_pdf, stamp_png, output_pdf, settings)

    stamped = fitz.open(output_pdf)
    try:
        image_rects = stamped[0].get_image_rects(stamped[0].get_images(full=True)[0][0])
        assert len(image_rects) == 1
        assert round(image_rects[0].width / image_rects[0].height, 1) == 2.0
    finally:
        stamped.close()
