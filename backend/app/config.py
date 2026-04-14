from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PREVIEW_DIR = DATA_DIR / "previews"
RESULT_DIR = DATA_DIR / "results"
SETTINGS_DIR = DATA_DIR / "settings"
STAMP_IMAGE_PATH = SETTINGS_DIR / "stamp.png"
STAMP_SETTINGS_PATH = SETTINGS_DIR / "stamp-settings.json"
TEMPLATES_PATH = SETTINGS_DIR / "templates.json"


def ensure_data_dirs() -> None:
    for path in (UPLOAD_DIR, PREVIEW_DIR, RESULT_DIR, SETTINGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
