from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.models import StampSettings
from app.settings_store import save_settings


client = TestClient(app)


def test_converters_endpoint_reports_pdf_passthrough():
    response = client.get("/api/converters")

    assert response.status_code == 200
    assert any(item["name"] == "pdf_passthrough" for item in response.json()["converters"])


def test_settings_round_trip():
    payload = {
        "x_ratio": 0.1,
        "y_ratio": 0.2,
        "width_ratio": 0.3,
        "height_ratio": 0.4,
        "page_rule": "first",
    }

    response = client.put("/api/stamp-settings", json=payload)
    assert response.status_code == 200
    assert response.json()["page_rule"] == "first"

    loaded = client.get("/api/stamp-settings")
    assert loaded.status_code == 200
    assert loaded.json()["x_ratio"] == 0.1
    save_settings(StampSettings())


def test_preview_accepts_pdf(tmp_path):
    source = tmp_path / "sample.pdf"
    _make_pdf(source)

    with source.open("rb") as handle:
        response = client.post("/api/preview", files={"file": ("sample.pdf", handle, "application/pdf")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_url"].endswith(".pdf")
    assert payload["page_count"] == 1
    assert payload["page_image_url"].endswith("/pages/1.png")
    assert payload["pages"][0]["width_mm"] == round(200 * 25.4 / 72, 2)
    assert payload["pages"][0]["height_mm"] == round(200 * 25.4 / 72, 2)


def test_preview_page_image_renders_selected_pdf_page(tmp_path):
    source = tmp_path / "sample.pdf"
    _make_pdf(source)

    with source.open("rb") as handle:
        preview = client.post("/api/preview", files={"file": ("sample.pdf", handle, "application/pdf")}).json()

    image = client.get(preview["page_image_url"])

    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content.startswith(b"\x89PNG")


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((32, 64), "sample")
    doc.save(path)
    doc.close()
