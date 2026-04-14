import re
from pathlib import Path

import fitz

from app.models import StampSettings


def resolve_pages(rule: str, page_count: int) -> list[int]:
    normalized = rule.strip().lower()
    if page_count < 1:
        return []
    if normalized == "all":
        return list(range(page_count))
    if normalized == "first":
        return [0]
    if normalized == "last":
        return [page_count - 1]

    pages: set[int] = set()
    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue
        if re.fullmatch(r"\d+", token):
            page = int(token)
            if page < 1:
                raise ValueError("Page numbers start at 1.")
            if page <= page_count:
                pages.add(page - 1)
            continue
        if re.fullmatch(r"\d+-\d+", token):
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start < 1 or end < 1:
                raise ValueError("Page numbers start at 1.")
            if end < start:
                raise ValueError("Page range end must be greater than start.")
            for page in range(start, min(end, page_count) + 1):
                pages.add(page - 1)
            continue
        raise ValueError(f"Unsupported page rule token: {token}")
    return sorted(pages)


def stamp_pdf(
    source_pdf: Path,
    stamp_image: Path,
    output_pdf: Path,
    settings: StampSettings,
) -> Path:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(source_pdf)
    try:
        for page_index in resolve_pages(settings.page_rule, len(document)):
            page = document[page_index]
            rect = _stamp_rect(page.rect, settings)
            page.insert_image(rect, filename=str(stamp_image), keep_proportion=True, overlay=True)
        document.save(output_pdf, garbage=4, deflate=True)
    finally:
        document.close()
    return output_pdf


def _stamp_rect(page_rect: fitz.Rect, settings: StampSettings) -> fitz.Rect:
    if settings.width_mm and settings.height_mm:
        width = settings.width_mm * 72 / 25.4
        height = settings.height_mm * 72 / 25.4
    else:
        width = page_rect.width * settings.width_ratio
        height = page_rect.height * settings.height_ratio
    x0 = page_rect.x0 + page_rect.width * settings.x_ratio
    y0 = page_rect.y0 + page_rect.height * settings.y_ratio
    x1 = min(x0 + width, page_rect.x1)
    y1 = min(y0 + height, page_rect.y1)
    return fitz.Rect(x0, y0, x1, y1)
